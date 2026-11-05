import copy
import time
import unittest
from unittest.mock import Mock, patch

import aegis
from aegis_policy import Policy
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import GraphBindingError
from langgraph.graph import StateGraph,START,END
from langgraph.types import Command
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.fixtures.reviewed import client
from tests.fixtures.graph_reviewed import Transport,State,gate,build,config,initial


class ReviewedGraph(unittest.TestCase):
    def tearDown(self):aegis.shutdown()

    def setup_graph(self,function,**changes):
        connection=client();transport=Transport();connection._send=Mock(side_effect=transport.send)
        governed=gate(function,connection,**changes);graph=build(governed);cfg=config()
        return governed,graph,cfg,transport

    def prepared(self,function,**changes):
        governed,graph,cfg,transport=self.setup_graph(function,**changes)
        graph.invoke(initial(),cfg)
        ticket=governed.prepare(graph,cfg,summary='Synthetic graph change')
        return governed,graph,cfg,transport,ticket

    def test_ac1301_pause_and_repeat_are_pure_and_prepare_is_stable(self):
        calls=[]
        def write(record='private-default'):calls.append(record)
        governed,graph,cfg,transport=self.setup_graph(write)
        result=graph.invoke(initial(),cfg)
        self.assertEqual(calls,[]);self.assertEqual(transport.calls,[])
        self.assertEqual(result['__interrupt__'][0].value['arguments'],{'record':'private-default'})
        ticket=governed.prepare(graph,cfg,summary='Synthetic graph change')
        self.assertEqual(governed.prepare(graph,cfg,summary='Synthetic graph change'),ticket)
        self.assertEqual(len(transport.records),1);self.assertEqual(calls,[])

    def test_ac1301_configuration_and_unsupported_graphs_are_rejected(self):
        def write(record=1):pass
        async def asynchronous():pass
        for fn in (asynchronous,lambda **kwargs:None):
            with self.assertRaises(TypeError):gate(fn)
        with self.assertRaises(ValueError):gate(write,disclose_arguments=False)
        governed,graph,cfg,transport=self.setup_graph(write)
        graph.invoke(initial(),cfg)
        for changed in ({}, {'configurable':{'thread_id':'demo-thread','checkpoint_id':'old'}},
                        {'configurable':{'thread_id':'demo-thread','checkpoint_ns':'sub'}},
                        {'configurable':{'thread_id':True}}, {**cfg,'callbacks':[]}):
            with self.assertRaises((GraphBindingError,ValueError)):governed.prepare(graph,changed,summary='demo')
        with self.assertRaises(GraphBindingError):governed.prepare(object(),cfg,summary='demo')
        parallel=StateGraph(State)
        parallel.add_node('review',governed.node);parallel.add_node('other',governed.node)
        parallel.add_edge(START,'review');parallel.add_edge(START,'other')
        from langgraph.checkpoint.memory import InMemorySaver
        compiled=parallel.compile(checkpointer=InMemorySaver());compiled.invoke(initial(),cfg)
        with self.assertRaises(GraphBindingError):governed.prepare(compiled,cfg,summary='demo')
        self.assertEqual(transport.calls,[])

    def test_ac1302_strict_call_and_ticket_tampering_never_reaches_network(self):
        def write(record=1):pass
        governed,graph,cfg,transport,ticket=self.prepared(write)
        for change in ({'schema':'other'},{'action_id':'2'*32},{'arguments':{'record':True}},
                       {'graph_binding':{**ticket['graph_binding'],'interrupt_id':'2'*32}},{'extra':1}):
            before=len(transport.calls)
            with self.assertRaises(GraphBindingError):governed.resume(graph,cfg,{**ticket,**change})
            self.assertEqual(len(transport.calls),before)
        for arguments in ({'record':1.2},{'record':'x\x00'},{'unknown':1}):
            g=build(governed)
            with self.assertRaises((ValueError,TypeError)):g.invoke(initial(arguments),cfg)

    def test_ac1302_thread_revision_and_policy_bindings_cannot_reuse_approval(self):
        calls=[]
        def write(record=1):calls.append(record)
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        graph.invoke(initial(),config('other-thread'))
        other=governed.prepare(graph,config('other-thread'),summary='Synthetic graph change')
        self.assertNotEqual(ticket['action_id'],other['action_id'])
        with self.assertRaises(GraphBindingError):governed.resume(graph,config('other-thread'),ticket)
        for changes in ({'graph_revision':'v2'},{'tool_revision':'v2'}):
            changed=gate(write,governed._reviewed._client,**changes)
            with self.assertRaises(GraphBindingError):changed.resume(graph,cfg,ticket)
        changed=gate(write,governed._reviewed._client,policy=Policy('different',governed._reviewed._runtime.policy.rules))
        with self.assertRaises(ApprovalUnavailable):changed.resume(graph,cfg,ticket)
        with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,{**ticket,'summary':'changed'})
        self.assertEqual(calls,[])

    def test_ac1302_checkpoint_edit_invalidates_ticket_without_new_action(self):
        def write(record=1):pass
        governed,graph,cfg,transport,ticket=self.prepared(write)
        graph.update_state(cfg,initial());graph.invoke(None,cfg)
        binding,arguments,action_id=governed._capture(graph,cfg)
        self.assertEqual(action_id,ticket['action_id'])
        self.assertNotEqual(binding['checkpoint_id'],ticket['graph_binding']['checkpoint_id'])
        with self.assertRaises(GraphBindingError):governed.resume(graph,cfg,ticket)
        with self.assertRaises(ApprovalUnavailable):governed.prepare(graph,cfg,summary='Synthetic graph change')
        self.assertEqual(len(transport.records),1)

    def test_ac1303_pending_rejected_and_changed_after_claim_have_zero_business_calls(self):
        for status in ('pending','rejected','approved'):
            calls=[]
            def write(record=1):calls.append(record)
            governed,graph,cfg,transport,ticket=self.prepared(write)
            if status!='pending':transport.approve(ticket,status)
            if status=='approved':transport.on_claim=lambda:graph.update_state(cfg,initial())
            with self.assertRaises((ApprovalUnavailable,GraphBindingError)):governed.resume(graph,cfg,ticket)
            self.assertEqual(calls,[])
            self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'failed' if status=='approved' else 'available')
            self.assertIsNone(governed._context.get())

    def test_ac1303_approved_once_preserves_value_context_and_privacy(self):
        calls=[];value=object();exporter=InMemorySpanExporter();aegis.init('graph-reviewed',exporter=exporter)
        def write(record='private-argument'):calls.append(record);return value
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        @aegis.observe(name='graph-host')
        def host():return governed.resume(graph,cfg,ticket)
        result=host()
        self.assertIs(result.value,value);self.assertEqual((result.confirmation,result.continuation),('confirmed','resumed'))
        self.assertEqual(result.graph_state['aegis_reviewed'],{'action_id':ticket['action_id'],'status':'completed'})
        self.assertEqual(graph.get_state(cfg).next,())
        with self.assertRaises(GraphBindingError):governed.resume(graph,cfg,ticket)
        self.assertEqual(calls,['private-argument']);self.assertTrue(aegis.flush())
        spans=exporter.get_finished_spans();self.assertEqual(len(spans),2)
        child=next(s for s in spans if s.attributes['gen_ai.operation.name']=='execute_tool')
        parent=next(s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent')
        self.assertEqual(child.parent.span_id,parent.context.span_id)
        self.assertNotIn('private-',repr([dict(s.attributes) for s in spans]))
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)

    def test_ac1303_business_exception_keeps_identity_and_does_not_resume_graph(self):
        original=ValueError('private failure');calls=[]
        def write(record=1):calls.append(record);raise original
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        with self.assertRaises(ValueError) as context:governed.resume(graph,cfg,ticket)
        self.assertIs(context.exception,original)
        self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'failed')
        self.assertEqual(len(graph.get_state(cfg).interrupts),1)
        with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
        self.assertEqual(calls,[1])

    def test_ac1303_lost_claim_or_confirmation_never_repeats_or_advances_graph(self):
        for fault in ('lost-claim','lost-complete'):
            calls=[];value=object()
            def write(record=1):calls.append(record);return value
            governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket);transport.fault=fault
            if fault=='lost-claim':
                with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
                self.assertEqual(calls,[])
            else:
                result=governed.resume(graph,cfg,ticket);self.assertIs(result.value,value)
                self.assertEqual((result.confirmation,result.continuation),('unknown','not_resumed'))
            self.assertEqual(len(graph.get_state(cfg).interrupts),1)
            with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
            self.assertEqual(len(calls),0 if fault=='lost-claim' else 1)

    def test_ac1304_post_execution_checkpoint_change_blocks_continuation(self):
        value=object();calls=[]
        def write(record=1):calls.append(record);graph.update_state(cfg,initial());return value
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        result=governed.resume(graph,cfg,ticket)
        self.assertIs(result.value,value);self.assertEqual((result.confirmation,result.continuation),('confirmed','blocked'))
        self.assertEqual(calls,[1]);self.assertIsNone(result.graph_state)

    def test_ac1303_slow_checkpoint_read_cannot_extend_claim_deadline(self):
        calls=[]
        def write(record=1):calls.append(record)
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        transport.remaining_ms=50
        native=graph.get_state;reads=[]
        def slow(config):
            reads.append(1)
            snapshot=native(config)
            if len(reads)==2:time.sleep(.07)
            return snapshot
        with patch.object(graph,'get_state',side_effect=slow):
            with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
        self.assertEqual(len(reads),2);self.assertEqual(calls,[])
        self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'failed')

    def test_ac1304_graph_continuation_error_retains_business_value_without_retry(self):
        calls=[];value=object()
        def write(record=1):calls.append(record);return value
        governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
        with patch.object(graph,'invoke',side_effect=ValueError('private graph error')) as invoke:
            result=governed.resume(graph,cfg,ticket)
        self.assertIs(result.value,value);self.assertEqual((result.confirmation,result.continuation),('confirmed','unknown'))
        self.assertEqual(invoke.call_count,1)
        with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
        self.assertEqual(calls,[1])

    def test_ac1302_boolean_forged_and_cross_checkpoint_receipts_are_rejected(self):
        for mutation in ('boolean','mac','thread','checkpoint'):
            def write(record=1):return object()
            governed,graph,cfg,transport,ticket=self.prepared(write);transport.approve(ticket)
            invoke=graph.invoke
            with patch.object(graph,'invoke',return_value={}) as intercepted:governed.resume(graph,cfg,ticket)
            receipt=copy.deepcopy(next(iter(intercepted.call_args.args[0].resume.values())))
            if mutation=='boolean':receipt=True
            elif mutation=='mac':receipt['mac']='0'*64
            else:
                receipt['graph_binding']['thread_id' if mutation=='thread' else 'checkpoint_id']='wrong'
                receipt['mac']=governed._mac({key:value for key,value in receipt.items() if key!='mac'})
            with self.assertRaises(GraphBindingError):invoke(Command(resume={ticket['graph_binding']['interrupt_id']:receipt}),cfg)
