import asyncio
import inspect
import os
import unittest
from unittest.mock import patch

import aegis
from aegis_policy import Policy
from aegis_runtime import Runtime, ActionDenied
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from aegis.exporters.jsonl import span_record


def policy():
    return Policy.from_dict({'schema_version':'aegis.policy.v1','revision':'v1','rules':[
        {'id':'allow','effect':'allow','subjects':['reader'],'tools':['lookup'],'permissions':['orders.read']},
        {'id':'deny','effect':'deny','subjects':['blocked'],'tools':['lookup'],'permissions':['orders.read']}]})


class RuntimeAcceptance(unittest.TestCase):
    def setUp(self):
        environment=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'})
        environment.start();self.addCleanup(environment.stop)
        aegis.shutdown()
        self.exporter=InMemorySpanExporter()
        self.sdk=aegis.init('runtime-tests',exporter=self.exporter)
    def tearDown(self): aegis.shutdown()

    def test_allow_once_deny_never_signature_result_and_unique_actions(self):
        calls=[];sentinel=object()
        def lookup(value:int,*,subject='fake')->object:
            calls.append(value);return sentinel
        allow=Runtime(policy(),subject='reader').tool(lookup,permission='orders.read')
        self.assertEqual(inspect.signature(allow),inspect.signature(lookup))
        self.assertIs(allow(1),sentinel)
        for subject,reason in [('blocked','explicit_deny'),('other','no_match')]:
            blocked=Runtime(policy(),subject=subject).tool(lookup,permission='orders.read')
            with self.assertRaises(ActionDenied) as caught: blocked(2,subject='reader')
            self.assertEqual(caught.exception.decision.reason,reason)
            with self.assertRaises(AttributeError): caught.exception.action_id='changed'
        self.assertEqual(calls,[1])
        aegis.flush()
        spans=self.exporter.get_finished_spans()
        self.assertEqual(len(spans),3)
        self.assertEqual(len({span.attributes['aegis.action.id'] for span in spans}),3)
        self.assertEqual([span.attributes['aegis.action.outcome'] for span in spans],['completed','denied','denied'])

    def test_missing_identity_permission_policy_and_evaluation_failure_are_closed(self):
        count=[]
        def lookup():count.append(1)
        cases=[(Runtime(policy()),'orders.read','identity_missing'),(Runtime(policy(),subject='reader'),None,'permission_missing'),(Runtime(subject='reader'),'orders.read','policy_unavailable')]
        for runtime,permission,reason in cases:
            with self.assertRaises(ActionDenied) as caught: runtime.tool(lookup,permission=permission)()
            self.assertEqual(caught.exception.decision.reason,reason)
        for failure in (RuntimeError('private evaluation failure'),None):
            context=patch.object(Policy,'evaluate',side_effect=failure) if isinstance(failure,Exception) else patch.object(Policy,'evaluate',return_value=None)
            with context,self.assertRaises(ActionDenied) as caught:
                Runtime(policy(),subject='reader').tool(lookup,permission='orders.read')()
            self.assertEqual(caught.exception.decision.reason,'policy_error')
        self.assertEqual(count,[])
        aegis.flush()
        self.assertNotIn('private',str([span_record(span) for span in self.exporter.get_finished_spans()]))

    def test_business_error_identity_and_privacy(self):
        original=ValueError('private business failure')
        @Runtime(policy(),subject='reader').tool(name='lookup',permission='orders.read')
        def broken(secret):raise original
        with self.assertRaises(ValueError) as caught: broken('private argument')
        self.assertIs(caught.exception,original)
        aegis.flush()
        record=span_record(self.exporter.get_finished_spans()[0])
        self.assertEqual(record['schema_version'],'aegis.span.v4')
        self.assertEqual(record['attributes']['aegis.decision.effect'],'allow')
        self.assertEqual(record['attributes']['aegis.action.outcome'],'error')
        self.assertNotIn('private',str(record))

    def test_no_sdk_shutdown_and_trace_failure_never_bypass_or_repeat(self):
        count=[]
        def lookup():count.append(1);return 9
        allow=Runtime(policy(),subject='reader').tool(lookup,permission='orders.read')
        deny=Runtime(policy(),subject='blocked').tool(lookup,permission='orders.read')
        with patch.object(self.sdk.tracer,'start_span',side_effect=RuntimeError('private trace failure')):
            self.assertEqual(allow(),9)
            with self.assertRaises(ActionDenied):deny()
        aegis.shutdown()
        self.assertEqual(allow(),9)
        with self.assertRaises(ActionDenied):deny()
        self.assertEqual(count,[1,1])
        from opentelemetry.sdk.trace.export import SpanExporter
        class BrokenExporter(SpanExporter):
            def export(self,spans):raise RuntimeError('private exporter failure')
            def shutdown(self):pass
        failed_sdk=aegis.init('runtime-export-failure',exporter=BrokenExporter())
        self.assertEqual(allow(),9)
        with self.assertRaises(ActionDenied):deny()
        aegis.flush()
        self.assertGreaterEqual(failed_sdk.diagnostics()['failed_spans'],2)
        self.assertEqual(count,[1,1,1])

    def test_async_allow_deny_concurrency_parentage_and_cancellation(self):
        count=[]
        @Runtime(policy(),subject='reader').tool(name='lookup',permission='orders.read')
        async def lookup(value):
            count.append(value);await asyncio.sleep(0);return value
        @Runtime(policy(),subject='blocked').tool(name='lookup',permission='orders.read')
        async def blocked():count.append('forbidden')
        @aegis.observe
        async def agent(value):
            self.assertEqual(await lookup(value),value)
            with self.assertRaises(ActionDenied):await blocked()
        async def run():await asyncio.gather(agent(1),agent(2))
        asyncio.run(run())
        self.assertCountEqual(count,[1,2])
        aegis.flush()
        spans=self.exporter.get_finished_spans()
        parents={span.context.span_id:span for span in spans if span.name.startswith('invoke_agent')}
        self.assertEqual(len(parents),2)
        for span in spans:
            if span.name.startswith('execute_tool'):
                self.assertIn(span.parent.span_id,parents)
                self.assertEqual(span.context.trace_id,parents[span.parent.span_id].context.trace_id)
        original=asyncio.CancelledError('private cancel')
        @Runtime(policy(),subject='reader').tool(name='lookup',permission='orders.read')
        async def cancel():raise original
        async def cancelled():
            try:await cancel()
            except asyncio.CancelledError as error:self.assertIs(error,original)
            else:self.fail('expected cancellation')
        asyncio.run(cancelled());aegis.flush()
        self.assertEqual(self.exporter.get_finished_spans()[-1].attributes['aegis.action.outcome'],'cancelled')

    def test_generator_and_invalid_configuration_rejected_before_execution(self):
        runtime=Runtime(policy(),subject='reader')
        def generator():yield 1
        async def async_generator():yield 1
        for fn in (generator,async_generator):
            with self.assertRaises(TypeError):runtime.tool(fn,permission='orders.read')
        for constructor in (lambda:Runtime(object(),subject='reader'),lambda:Runtime(policy(),subject='*'),lambda:runtime.tool(permission='*')):
            with self.assertRaises(ValueError):constructor()

    def test_actual_langgraph_toolnode_catches_denial_without_running_tool(self):
        try:
            from langchain_core.messages import AIMessage
            from langchain_core.tools import StructuredTool
            from langgraph.prebuilt import ToolNode
            from langgraph.graph import StateGraph, MessagesState, START, END
        except ImportError:
            self.skipTest('optional LangGraph integration dependencies not installed')
        count=[]
        def lookup(value:str)->str:
            """Return a fixed synthetic value."""
            count.append(value);return value
        message=AIMessage(content='',tool_calls=[{'name':'lookup','args':{'value':'synthetic'},'id':'call-demo','type':'tool_call'}])
        for subject in ('reader','blocked'):
            fn=Runtime(policy(),subject=subject).tool(lookup,permission='orders.read')
            node=ToolNode([StructuredTool.from_function(fn)],handle_tool_errors=True)
            graph=StateGraph(MessagesState).add_node('tools',node).add_edge(START,'tools').add_edge('tools',END).compile()
            result=graph.invoke({'messages':[message]})
            self.assertEqual(result['messages'][-1].status,'success' if subject=='reader' else 'error')
        self.assertEqual(count,['synthetic'])


if __name__=='__main__':unittest.main()
