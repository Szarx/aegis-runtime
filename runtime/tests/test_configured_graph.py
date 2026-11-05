import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import aegis
from aegis_runtime.application import Application,GraphBinding,inspect_application,load_application
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import GraphBindingError
from tests.fixtures.configured_graph import write_graph_application
from tests.fixtures.configured_review import write_review_application
from tests.fixtures.graph_reviewed import Transport,build,config,initial
from tests.fixtures.reviewed import client
from tests.fixtures.async_reviewed import Transport as AsyncTransport,client as async_client


class ConfiguredGraph(unittest.TestCase):
    def setUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.addCleanup(aegis.shutdown)
        self.folder=Path(self.tmp.name);self.path=write_graph_application(self.folder);self.settings=load_application(self.path)
        self.connection=client();self.transport=Transport();self.connection._send=Mock(side_effect=self.transport.send)

    def test_ac2701_v3_is_strict_and_old_versions_reject_graph_mode(self):
        original=json.loads(self.path.read_text())
        for changes in ({'graph':None},{'graph':{'id':'demo','revision':'v1'}},{'execution':'reviewed'},{'tool_revision':None},
                        {'graph':{'id':'demo','revision':'v1','node':'review','extra':True}}):
            value=json.loads(json.dumps(original));value['tools'][0].update(changes);self.path.write_text(json.dumps(value))
            with self.subTest(changes=changes),self.assertRaises(ValueError):load_application(self.path)
        for version in ('v1','v2'):
            with self.assertRaises(ValueError):replace(self.settings,schema_version='aegis.application.'+version)
            value={**original,'schema_version':'aegis.application.'+version};self.path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load_application(self.path)
        report=inspect_application(self.settings,subject='demo-agent')
        self.assertEqual(report['schema_version'],'aegis.application-inspection.v3');self.assertTrue(report['tools'][0]['requires_review'])
        self.assertEqual(report['tools'][0]['graph'],dict(id='configured-demo',revision='graph-v1',node='review'))

    def test_ac2701_binding_cannot_downgrade_or_duplicate_or_disclose_implicitly(self):
        def write(record=1):return record
        with Application(self.settings,subject='demo-agent') as app:
            with self.assertRaises(ValueError):app.tool(write)
            with self.assertRaises(ValueError):app.reviewed_tool(write,client=self.connection,disclose_arguments=True)
            with self.assertRaises(ValueError):app.reviewed_graph_tool(write,client=self.connection)
            self.assertEqual(app.status()['bound_tools'],[])
            gate=app.reviewed_graph_tool(write,client=self.connection,disclose_arguments=True)
            with self.assertRaises(TypeError):gate(record=1)
            with self.assertRaises(ValueError):app.reviewed_graph_tool(write,client=self.connection,disclose_arguments=True)
            self.assertEqual(app.status()['schema_version'],'aegis.application-status.v3')
            self.assertEqual(app.status()['tool_modes']['write']['graph']['revision'],'graph-v1')
        with Application(load_application(write_review_application(self.folder/'old')),subject='demo-agent') as app:
            with self.assertRaises(ValueError):app.reviewed_graph_tool(write,client=self.connection,disclose_arguments=True)

    def test_ac2702_sync_pause_is_pure_approval_once_and_closed_node_cannot_run(self):
        calls=[]
        with Application(self.settings,subject='demo-agent') as app:
            gate=app.reviewed_graph_tool(lambda record=1:calls.append(record),name='write',client=self.connection,disclose_arguments=True)
            graph=build(gate);cfg=config();graph.invoke(initial(),cfg,durability='sync')
            self.assertEqual(calls,[]);self.assertEqual(self.transport.calls,[])
            ticket=gate.prepare(graph,cfg,summary='Synthetic configured graph')
            with self.assertRaises(ApprovalUnavailable):gate.resume(graph,cfg,ticket)
            self.transport.approve(ticket);invoke=graph.invoke;continued=[]
            def continuation(*args,**kwargs):
                continued.append(True);self.assertGreater(app.status()['active_calls'],0)
                with self.assertRaises(RuntimeError):app.close()
                return invoke(*args,**kwargs)
            graph.invoke=continuation;result=app.agent(gate.resume)(graph,cfg,ticket);graph.invoke=invoke
            self.assertEqual(continued,[True])
            self.assertEqual((result.confirmation,result.continuation),('confirmed','resumed'))
            self.assertEqual(graph.get_state(cfg).values['aegis_reviewed']['action_id'],ticket['action_id'])
            with self.assertRaises(GraphBindingError):gate.resume(graph,cfg,ticket)
        for operation in (lambda:gate.prepare(graph,cfg,summary='Synthetic'),lambda:gate.resume(graph,cfg,ticket),lambda:graph.invoke(initial(),config('new'))):
            with self.assertRaises(RuntimeError):operation()
        self.assertEqual(calls,[1])

    def test_ac2702_exact_snapshot_and_argument_tampering_fail_before_claim(self):
        with Application(self.settings,subject='demo-agent') as app:
            gate=app.reviewed_graph_tool(lambda record=1:None,name='write',client=self.connection,disclose_arguments=True)
            graph=build(gate);cfg=config();graph.invoke(initial(),cfg);ticket=gate.prepare(graph,cfg,summary='Synthetic')
            self.transport.approve(ticket);before=len(self.transport.calls)
            with self.assertRaises(GraphBindingError):gate.resume(graph,cfg,{**ticket,'arguments':{'record':2}})
            graph.update_state(cfg,initial());graph.invoke(None,cfg)
            with self.assertRaises(GraphBindingError):gate.resume(graph,cfg,ticket)
            self.assertEqual(len(self.transport.calls),before)

    def test_ac2702_graph_revision_change_cannot_reuse_checkpoint(self):
        from langgraph.checkpoint.memory import InMemorySaver
        saver=InMemorySaver()
        with Application(self.settings,subject='demo-agent') as app:
            gate=app.reviewed_graph_tool(lambda record=1:None,name='write',client=self.connection,disclose_arguments=True)
            graph=build(gate,saver);cfg=config();graph.invoke(initial(),cfg);ticket=gate.prepare(graph,cfg,summary='Synthetic');self.transport.approve(ticket)
        binding=replace(self.settings.tools[0],graph=GraphBinding('configured-demo','graph-v2','review'))
        with Application(replace(self.settings,tools=(binding,)),subject='demo-agent') as app:
            changed=app.reviewed_graph_tool(lambda record=1:None,name='write',client=self.connection,disclose_arguments=True)
            with self.assertRaises(GraphBindingError):changed.resume(build(changed,saver),cfg,ticket)
        self.assertEqual(self.transport.records[ticket['action_id']]['execution_state'],'available')

    def test_ac2702_lease_covers_claim_business_and_continuation_unknown_never_retries(self):
        calls=[]
        with Application(self.settings,subject='demo-agent') as app:
            def busy():
                self.assertGreater(app.status()['active_calls'],0)
                with self.assertRaises(RuntimeError):app.close()
            def write(record=1):busy();calls.append(record);return record
            self.transport.on_claim=busy
            gate=app.reviewed_graph_tool(write,client=self.connection,disclose_arguments=True);graph=build(gate);cfg=config()
            graph.invoke(initial(),cfg);ticket=gate.prepare(graph,cfg,summary='Synthetic');self.transport.approve(ticket)
            self.transport.fault='lost-complete';result=gate.resume(graph,cfg,ticket)
            self.assertEqual((result.confirmation,result.continuation),('unknown','not_resumed'));self.assertTrue(graph.get_state(cfg).interrupts)
            with self.assertRaises(ApprovalUnavailable):gate.resume(graph,cfg,ticket)
            self.assertEqual(app.status()['active_calls'],0)
        self.assertEqual(calls,[1])


class ConfiguredAsyncGraph(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.settings=load_application(write_graph_application(Path(self.tmp.name)))
    async def asyncTearDown(self):aegis.shutdown();self.tmp.cleanup()

    async def test_ac2702_async_whole_resume_stays_in_task_and_client_is_borrowed(self):
        calls=[];transport=AsyncTransport();origin=asyncio.current_task()
        async with async_client(transport) as connection:
            with Application(self.settings,subject='demo-agent') as app:
                async def write(record=1):
                    self.assertIs(asyncio.current_task(),origin);calls.append(record)
                    with self.assertRaises(RuntimeError):app.close()
                    return 'synthetic'
                gate=app.reviewed_graph_tool(write,client=connection,disclose_arguments=True);graph=build(gate);cfg=config()
                await graph.ainvoke(initial(),cfg,durability='sync');ticket=await gate.prepare(graph,cfg,summary='Synthetic')
                transport.approve(ticket['action_id']);result=await app.agent(gate.resume)(graph,cfg,ticket)
                self.assertEqual(result.continuation,'resumed');self.assertEqual(result.value,'synthetic')
                self.assertEqual(app.status()['active_calls'],0)
            self.assertFalse(transport.closed)
            for operation in (lambda:gate.prepare(graph,cfg,summary='Synthetic'),lambda:gate.resume(graph,cfg,ticket),lambda:graph.ainvoke(initial(),config('new'))):
                with self.assertRaises(RuntimeError):await operation()
        self.assertTrue(transport.closed);self.assertEqual(calls,[1])

    async def test_ac2702_async_cancel_partial_effect_keeps_claim_and_graph_paused(self):
        calls=[];transport=AsyncTransport()
        async with async_client(transport) as connection:
            with Application(self.settings,subject='demo-agent') as app:
                async def write(record=1):calls.append(record);raise asyncio.CancelledError()
                gate=app.reviewed_graph_tool(write,client=connection,disclose_arguments=True);graph=build(gate);cfg=config()
                await graph.ainvoke(initial(),cfg,durability='sync');ticket=await gate.prepare(graph,cfg,summary='Synthetic');transport.approve(ticket['action_id'])
                with self.assertRaises(asyncio.CancelledError):await gate.resume(graph,cfg,ticket)
                with self.assertRaises(ApprovalUnavailable):await gate.resume(graph,cfg,ticket)
                self.assertEqual(app.status()['active_calls'],0);self.assertTrue((await graph.aget_state(cfg)).interrupts)
        self.assertEqual(calls,[1]);self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'claimed')

    async def test_ac2701_wrong_client_mode_does_not_register_graph(self):
        async with async_client(AsyncTransport()) as connection:
            with Application(self.settings,subject='demo-agent') as app:
                async def asynchronous(record=1):return record
                with self.assertRaises(ValueError):app.reviewed_graph_tool(asynchronous,name='write',client=client(),disclose_arguments=True)
                with self.assertRaises(ValueError):app.reviewed_graph_tool(lambda record=1:record,name='write',client=connection,disclose_arguments=True)
                self.assertEqual(app.status()['bound_tools'],[])
