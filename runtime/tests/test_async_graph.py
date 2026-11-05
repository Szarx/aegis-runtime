import asyncio
import copy
import unittest
from unittest.mock import patch

import aegis
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import GraphBindingError
from tests.fixtures.async_reviewed import Transport, client
from tests.fixtures.async_graph import gate, build, config, initial


class AsyncGraph(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self): aegis.shutdown()

    async def paused(self, function, connection, transport):
        governed=gate(function, connection);graph=build(governed);cfg=config()
        await graph.ainvoke(initial(), cfg, durability='sync')
        ticket=await governed.prepare(graph, cfg, summary='Synthetic async graph')
        transport.approve(ticket['action_id'])
        return governed,graph,cfg,ticket

    async def test_ac1501_lazy_async_only_and_root_binding(self):
        transport=Transport()
        async with client(transport) as connection:
            def sync(): pass
            with self.assertRaises(TypeError):gate(sync,connection)
            async def write(value=1): return value
            governed=gate(write,connection);graph=build(governed)
            prepare=governed.prepare(graph,config(),summary='demo');resume=governed.resume(graph,config(),{})
            self.assertIsNone(governed._loop);self.assertEqual(transport.requests,[])
            prepare.close();resume.close()
            task=asyncio.create_task(governed.prepare(graph,config(),summary='demo'));task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(transport.requests,[])
            await graph.ainvoke(initial(),config(),durability='sync')
            for cfg in ({'configurable':{'thread_id':'demo-thread','checkpoint_id':'history'}},config('other')):
                with self.assertRaises(GraphBindingError):await governed.prepare(graph,cfg,summary='demo')
            with patch.object(governed,'_loop',object()),self.assertRaises(ValueError):
                await governed.prepare(graph,config(),summary='demo')
            self.assertEqual(transport.requests,[])

    async def test_ac1501_native_success_identity_agent_parent_and_privacy(self):
        transport=Transport();calls=[];value=object();exporter=InMemorySpanExporter()
        aegis.init('async-graph-test',exporter=exporter)
        async def write(value='private-graph-argument'):
            calls.append(trace.get_current_span().get_span_context().span_id)
            await asyncio.sleep(0);return returned
        returned=value
        async with client(transport) as connection:
            governed,graph,cfg,ticket=await self.paused(write,connection,transport)
            @aegis.observe(name='async-graph-host')
            async def resume():return await governed.resume(graph,cfg,ticket)
            with patch.object(graph,'get_state',side_effect=AssertionError('sync read forbidden')):
                result=await resume()
            self.assertIs(result.value,value);self.assertEqual((result.confirmation,result.continuation),('confirmed','resumed'))
            self.assertEqual((await graph.aget_state(cfg)).next,());self.assertEqual(len(calls),1)
            with self.assertRaises(GraphBindingError):await governed.resume(graph,cfg,ticket)
        self.assertTrue(aegis.flush());spans=exporter.get_finished_spans()
        tool=next(span for span in spans if span.attributes.get('aegis.action.id')==ticket['action_id'])
        parent=next(span for span in spans if span.attributes.get('gen_ai.operation.name')=='invoke_agent')
        self.assertEqual(tool.parent.span_id,parent.context.span_id)
        self.assertEqual(calls,[tool.context.span_id]);self.assertNotIn('private-graph',str([(s.attributes,s.events) for s in spans]))

    async def test_ac1501_mutated_ticket_or_checkpoint_fails_before_claim(self):
        transport=Transport();calls=[]
        async def write(value=1):calls.append(value)
        async with client(transport) as connection:
            governed,graph,cfg,ticket=await self.paused(write,connection,transport)
            changed=copy.deepcopy(ticket);changed['arguments']['value']=True
            with self.assertRaises(GraphBindingError):await governed.resume(graph,cfg,changed)
            await graph.aupdate_state(cfg,initial({'value':2}))
            with self.assertRaises(GraphBindingError):await governed.resume(graph,cfg,ticket)
            self.assertEqual(calls,[]);self.assertEqual(len(transport.requests),1)

    async def test_ac1502_cancel_claim_body_and_confirmation_preserves_original(self):
        for phase,expected_calls,execution in [('claim',0,'claimed'),('body',1,'claimed'),('complete',1,'completed')]:
            with self.subTest(phase=phase):
                transport=Transport();entered=asyncio.Event();seen=[];calls=[]
                async def hold(*args):
                    entered.set()
                    try:await asyncio.Event().wait()
                    except asyncio.CancelledError as error:seen.append(error);raise
                async def write(value=1):
                    calls.append(value)
                    if phase=='body':await hold()
                    return value
                async with client(transport) as connection:
                    governed,graph,cfg,ticket=await self.paused(write,connection,transport)
                    if phase!='body':transport.hooks[phase]=hold
                    task=asyncio.create_task(governed.resume(graph,cfg,ticket))
                    await asyncio.wait_for(entered.wait(),3);task.cancel('synthetic cancel')
                    with self.assertRaises(asyncio.CancelledError) as error:await task
                    self.assertIs(error.exception,seen[0]);self.assertEqual(len(calls),expected_calls)
                    transport.hooks.clear()
                    with self.assertRaises(ApprovalUnavailable):await governed.resume(graph,cfg,ticket)
                    self.assertEqual(transport.records[ticket['action_id']]['execution_state'],execution)
                    self.assertEqual(len(calls),expected_calls);self.assertTrue((await graph.aget_state(cfg)).interrupts)

    async def test_ac1502_cancel_at_three_checkpoint_reads_and_graph_continue(self):
        for phase in ('initial','guard','post','continue'):
            with self.subTest(phase=phase):
                transport=Transport();calls=[];entered=asyncio.Event();seen=[]
                async def write(value=1):calls.append(value);return value
                async with client(transport) as connection:
                    governed,graph,cfg,ticket=await self.paused(write,connection,transport)
                    native=graph.aget_state;reads=0
                    async def hold():
                        entered.set()
                        try:await asyncio.Event().wait()
                        except asyncio.CancelledError as error:seen.append(error);raise
                    async def capture(*args,**kwargs):
                        nonlocal reads
                        reads+=1
                        if reads=={'initial':1,'guard':2,'post':3}.get(phase):await hold()
                        return await native(*args,**kwargs)
                    async def continuing(*args,**kwargs):await hold()
                    with patch.object(graph,'aget_state',side_effect=capture),patch.object(graph,'ainvoke',side_effect=continuing):
                        task=asyncio.create_task(governed.resume(graph,cfg,ticket))
                        await asyncio.wait_for(entered.wait(),3);task.cancel(phase)
                        with self.assertRaises(asyncio.CancelledError) as error:await task
                    self.assertIs(error.exception,seen[0])
                    self.assertEqual(len(calls),int(phase in ('post','continue')))
                    state=transport.records[ticket['action_id']]['execution_state']
                    self.assertEqual(state,{'initial':'available','guard':'claimed','post':'completed','continue':'completed'}[phase])
                    self.assertFalse(any(path.endswith('/complete') for path,_,_ in transport.requests) if phase=='guard' else False)
                    if phase!='initial':
                        with self.assertRaises(ApprovalUnavailable):await governed.resume(graph,cfg,ticket)

    async def test_ac1502_checkpoint_wait_cannot_extend_claim_deadline(self):
        transport=Transport();transport.remaining_ms=10;calls=[]
        async def write(value=1):calls.append(value)
        async with client(transport) as connection:
            governed,graph,cfg,ticket=await self.paused(write,connection,transport)
            native=graph.aget_state;reads=0
            async def slow(*args,**kwargs):
                nonlocal reads
                reads+=1
                if reads==2:await asyncio.sleep(.03)
                return await native(*args,**kwargs)
            with patch.object(graph,'aget_state',side_effect=slow),self.assertRaises(ApprovalUnavailable):
                await governed.resume(graph,cfg,ticket)
            self.assertEqual(calls,[])

    async def test_ac1502_error_identity_confirmation_fault_and_changed_post_snapshot(self):
        for phase in ('error','confirm','changed','graph-error'):
            transport=Transport();original=ValueError('private business');calls=[];value=object()
            async def write(record=1):
                calls.append(record)
                if phase=='error':raise original
                return value
            async with client(transport) as connection:
                governed,graph,cfg,ticket=await self.paused(write,connection,transport)
                async def complete(record):
                    if phase in ('error','confirm'):raise OSError('private confirmation')
                    if phase=='changed':await graph.aupdate_state(cfg,initial({'record':2}))
                transport.hooks['complete']=complete
                if phase=='error':
                    with self.assertRaises(ValueError) as error:await governed.resume(graph,cfg,ticket)
                    self.assertIs(error.exception,original)
                else:
                    native=graph.ainvoke
                    with patch.object(graph,'ainvoke',side_effect=OSError('private graph') if phase=='graph-error' else native):
                        result=await governed.resume(graph,cfg,ticket)
                    self.assertIs(result.value,value)
                    self.assertEqual(result.continuation,{'confirm':'not_resumed','changed':'blocked','graph-error':'unknown'}[phase])
                self.assertEqual(calls,[1])
