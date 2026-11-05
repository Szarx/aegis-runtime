"""SPEC-006: actual StateGraph/ToolNode, synthetic provider transport."""

import asyncio
import os
from typing import TypedDict
import unittest
from unittest.mock import patch

import aegis
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    from aegis.langgraph import observe_graph
    from examples.langgraph.agent import build_agent,initial_state,business_view
    from examples.deepseek.offline import Fixture,PRIVATE_TEXT
    from langchain_core.callbacks import BaseCallbackHandler
    from langgraph.graph import StateGraph,START,END
    from langgraph.runtime import Runtime
    from openai import OpenAI,AsyncOpenAI
    AVAILABLE=True
except ImportError:
    AVAILABLE=False


@unittest.skipUnless(AVAILABLE,'install SDK langgraph and deepseek extras')
class LangGraphAcceptance(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'})
        self.environment.start()
        aegis.shutdown()
        self.exporter=InMemorySpanExporter()
        self.sdk=aegis.init('langgraph-tests',exporter=self.exporter)
    def tearDown(self):
        aegis.shutdown()
        self.environment.stop()
    def spans(self):
        self.assertTrue(aegis.flush())
        return self.exporter.get_finished_spans()
    def client(self):
        return OpenAI(api_key='synthetic-langgraph-key',http_client=Fixture().http_client(),max_retries=0)

    def test_ac601_ac603_real_graph_before_after_same_result_and_no_duplicate_spans(self):
        with self.client() as client:
            before,bc=build_agent(client)
            after,ac=build_agent(client,traced=True)
            self.assertEqual(business_view(before.invoke(initial_state())),business_view(after.invoke(initial_state())))
        self.assertEqual(bc,{'model_calls':2,'tool_calls':1})
        self.assertEqual(ac,bc)
        spans=self.spans()
        self.assertEqual(len(spans),4)
        root=next(s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent')
        self.assertTrue(all(s.parent.span_id==root.context.span_id for s in spans if s is not root))
        self.assertEqual(len([s for s in spans if s.attributes['gen_ai.operation.name']=='chat']),2)

    def test_ac602_config_callbacks_forwarding_and_response_identity(self):
        class State(TypedDict): value:int
        class Context(TypedDict): secret:str
        class Callback(BaseCallbackHandler):
            def __init__(self): self.starts=0
            def on_chain_start(self,*args,**kwargs): self.starts+=1
        callback=Callback()
        seen=[]
        def node(state,config,runtime:Runtime[Context]):
            seen.append(config['metadata']['private-test-value'])
            self.assertEqual(runtime.context['secret'],PRIVATE_TEXT)
            return {'value':state['value']+1}
        raw=StateGraph(State,context_schema=Context).add_node('step',node).add_edge(START,'step').add_edge('step',END).compile()
        graph=observe_graph(raw,name='config-agent')
        config={'callbacks':[callback],'tags':['private-tag'],'metadata':{'private-test-value':PRIVATE_TEXT},'recursion_limit':5}
        runtime_context={'secret':PRIVATE_TEXT}
        original=raw.invoke
        captured=[]
        def invoke(*args,**kwargs):
            self.assertIs(kwargs['config'],config)
            self.assertIs(kwargs['context'],runtime_context)
            result=original(*args,**kwargs);captured.append(result);return result
        with patch.object(raw,'invoke',invoke):
            result=graph.invoke({'value':1},config=config,context=runtime_context)
        self.assertIs(result,captured[0])
        self.assertEqual(result,{'value':2})
        self.assertTrue(callback.starts>0)
        self.assertEqual(seen,[PRIVATE_TEXT])
        bound=graph.with_config(metadata={'private-test-value':PRIVATE_TEXT})
        self.assertEqual(bound.invoke({'value':2},context=runtime_context),{'value':3})
        self.assertIsNone(raw.config)
        self.assertEqual(config['tags'],['private-tag'])
        payload=encode_spans(self.spans()).SerializeToString()
        for text in (PRIVATE_TEXT,'private-tag','private-test-value'): self.assertNotIn(text.encode(),payload)

    def test_ac602_idempotent_wrap_validation_and_out_of_scope_delegation(self):
        with self.client() as client:
            raw,_=build_agent(client)
            graph=observe_graph(raw,name='same-agent')
            self.assertIs(observe_graph(graph),graph)
            self.assertIs(observe_graph(graph,name='same-agent'),graph)
            with self.assertRaises(ValueError):observe_graph(graph,name='different')
            with self.assertRaises(ValueError):observe_graph(raw,name='bad\x00name')
            with self.assertRaises(TypeError):observe_graph(object())
            self.assertIs(graph.batch.__self__,raw)
            list(raw.stream(initial_state()))
        self.assertEqual(self.spans(),())

    def test_ac603_async_concurrent_real_graphs_keep_context_separate(self):
        async def execute():
            async with AsyncOpenAI(api_key='synthetic',http_client=Fixture(asynchronous=True).http_client()) as client:
                graph,counts=build_agent(client,traced=True,asynchronous=True)
                results=await asyncio.gather(graph.ainvoke(initial_state()),graph.ainvoke(initial_state()))
                self.assertEqual(counts,{'model_calls':4,'tool_calls':2})
                self.assertEqual(business_view(results[0]),business_view(results[1]))
        asyncio.run(execute())
        spans=self.spans()
        roots=[s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent']
        self.assertEqual(len(spans),8)
        self.assertEqual(len({s.context.trace_id for s in roots}),2)
        for root in roots:
            children=[s for s in spans if s.context.trace_id==root.context.trace_id and s is not root]
            self.assertEqual(len(children),3)
            self.assertTrue(all(s.parent.span_id==root.context.span_id for s in children))

    def test_ac603_nested_upstream_agent_preserved(self):
        with self.client() as client:
            graph,_=build_agent(client,traced=True)
            @aegis.observe(name='outer-agent')
            def outer():return graph.invoke(initial_state())
            outer()
        spans=self.spans()
        outer=next(s for s in spans if s.name=='invoke_agent outer-agent')
        graph_span=next(s for s in spans if s.name=='invoke_agent langgraph-order-agent')
        self.assertEqual(graph_span.parent.span_id,outer.context.span_id)
        self.assertEqual(len(spans),5)

    def test_ac604_framework_handled_tool_error_keeps_agent_behavior(self):
        with self.client() as client:
            before,bc=build_agent(client,fail_tool=True,handle_tool_errors=True)
            after,ac=build_agent(client,traced=True,fail_tool=True,handle_tool_errors=True)
            self.assertEqual(business_view(before.invoke(initial_state())),business_view(after.invoke(initial_state())))
        spans=self.spans()
        self.assertEqual(bc,ac)
        self.assertEqual(next(s for s in spans if s.attributes['gen_ai.operation.name']=='execute_tool').status.status_code.name,'ERROR')
        self.assertEqual(next(s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent').status.status_code.name,'UNSET')
        self.assertNotIn(b'synthetic private tool failure',encode_spans(spans).SerializeToString())

    def test_ac604_unhandled_tool_error_preserves_exception_identity(self):
        error=ValueError(PRIVATE_TEXT)
        with self.client() as client:
            graph,counts=build_agent(client,traced=True,fail_tool=True,tool_error=error)
            with self.assertRaises(ValueError) as raised:graph.invoke(initial_state())
        self.assertIs(raised.exception,error)
        self.assertEqual(counts,{'model_calls':1,'tool_calls':1})
        spans=self.spans()
        self.assertEqual(len(spans),3)
        self.assertEqual(sum(s.status.status_code.name=='ERROR' for s in spans),2)

    def test_ac604_real_async_cancellation_finishes_and_restores_context(self):
        async def execute():
            class State(TypedDict): value:int
            started=asyncio.Event();captured=[]
            async def node(state):
                started.set()
                try:await asyncio.Event().wait()
                except asyncio.CancelledError as error:
                    captured.append(error);raise
            raw=StateGraph(State).add_node('wait',node).add_edge(START,'wait').add_edge('wait',END).compile()
            task=asyncio.create_task(observe_graph(raw).ainvoke({'value':1}))
            await started.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError) as raised:await task
            self.assertIs(raised.exception,captured[0])
        asyncio.run(execute())
        spans=self.spans()
        self.assertEqual(len(spans),1)
        self.assertEqual(spans[0].status.status_code.name,'ERROR')
        self.assertIn('CancelledError',spans[0].attributes['error.type'])

    def test_ac604_disabled_and_instrumentation_failure_preserve_business(self):
        with self.client() as client:
            graph,counts=build_agent(client,traced=True)
            with patch.object(self.sdk.tracer,'start_span',side_effect=RuntimeError('tracing only')):
                result=graph.invoke(initial_state())
            self.assertEqual(counts,{'model_calls':2,'tool_calls':1})
            self.assertTrue(self.sdk.diagnostics()['instrumentation_failures']>0)
            self.assertEqual(self.spans(),())
            aegis.shutdown()
            other,other_counts=build_agent(client,traced=True)
            self.assertEqual(business_view(other.invoke(initial_state())),business_view(result))
            self.assertEqual(other_counts,counts)
