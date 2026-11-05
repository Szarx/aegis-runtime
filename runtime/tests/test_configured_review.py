import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import aegis
from aegis_policy import Policy
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application,ApplicationConfig,ToolBinding,inspect_application,load_application
from aegis_runtime.approvals import ApprovalUnavailable
from runtime.tests.test_reviewed_execution import Transport
from tests.fixtures.reviewed import client
from tests.fixtures.async_reviewed import Transport as AsyncTransport,client as async_client
from tests.fixtures.configured_review import write_review_application
from tests.fixtures.application_config import write_application


class ConfiguredReview(unittest.TestCase):
    def setUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.addCleanup(aegis.shutdown)
        self.folder=Path(self.tmp.name);self.path=write_review_application(self.folder);self.config=load_application(self.path)
        self.client=client();self.transport=Transport();self.client._send=Mock(side_effect=self.transport.send)

    def test_ac2601_v1_shape_and_v2_mode_are_explicit_in_inspection_and_status(self):
        legacy=load_application(write_application(self.folder/'legacy'))
        self.assertEqual(inspect_application(legacy,subject='reader')['schema_version'],'aegis.application-inspection.v1')
        self.assertNotIn('execution',inspect_application(legacy,subject='reader')['tools'][0])
        report=inspect_application(self.config,subject='demo-agent');self.assertEqual(report['schema_version'],'aegis.application-inspection.v2')
        self.assertTrue(report['tools'][0]['requires_review']);self.assertEqual(report['tools'][0]['decision']['effect'],'allow')
        with Application(self.config,subject='demo-agent') as app:
            self.assertEqual(app.status()['tool_modes']['write'],dict(execution='reviewed',tool_revision='write-v1'))
        self.assertNotIn('synthetic-producer',json.dumps(app.status()))

    def test_ac2601_v2_unknown_incomplete_or_downgraded_fields_are_rejected(self):
        original=json.loads(self.path.read_text())
        for changes in (dict(execution='unknown'),dict(tool_revision=None),dict(execution='direct'),dict(disclose_arguments=True)):
            value=json.loads(json.dumps(original));value['tools'][0].update(changes);self.path.write_text(json.dumps(value))
            with self.subTest(changes=changes),self.assertRaises(ValueError):load_application(self.path)
        value=json.loads(json.dumps(original));value['schema_version']='aegis.application.v1';self.path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):load_application(self.path)
        with self.assertRaises(ValueError):replace(self.config,schema_version='aegis.application.v1')
        self.path.write_text(json.dumps(original))

    def test_ac2601_reviewed_and_direct_binding_modes_cannot_be_mixed(self):
        def write(record=1):return record
        with Application(self.config,subject='demo-agent') as app:
            with self.assertRaises(ValueError):app.tool(write)
            with self.assertRaises(ValueError):app.reviewed_tool(write,client=self.client,disclose_arguments=False)
            governed=app.reviewed_tool(write,client=self.client,disclose_arguments=True)
            with self.assertRaises(TypeError):governed(record=1)
            with self.assertRaises(ValueError):app.reviewed_tool(write,client=self.client,disclose_arguments=True)
            with self.assertRaises(ValueError):app.tool(write)
        direct=load_application(write_application(self.folder/'direct'))
        with Application(direct,subject='reader') as app:
            with self.assertRaises(ValueError):app.reviewed_tool(write,name='lookup_order',client=self.client,disclose_arguments=True)

    def test_ac2602_pending_then_approved_resumes_once_and_handles_expire_with_application(self):
        calls=[];sentinel=object()
        def write(record=1):calls.append(record);return sentinel
        with Application(self.config,subject='demo-agent') as app:
            governed=app.reviewed_tool(write,client=self.client,disclose_arguments=True)
            ticket=governed.prepare({},summary='Synthetic configured write')
            self.assertEqual(ticket['review_arguments'],{'record':1})
            with self.assertRaises(ApprovalUnavailable):governed.resume(ticket['action_id'],{},summary='Synthetic configured write')
            self.assertEqual(calls,[]);self.transport.approve()
            outcome=governed.resume(ticket['action_id'],{},summary='Synthetic configured write')
            self.assertIs(outcome.value,sentinel);self.assertEqual(outcome.confirmation,'confirmed')
            with self.assertRaises(ApprovalUnavailable):governed.resume(ticket['action_id'],{},summary='Synthetic configured write')
            self.assertEqual(app.status()['active_calls'],0)
        requests=len(self.transport.calls)
        for action in (lambda:governed.prepare({},summary='Synthetic'),lambda:governed.resume(ticket['action_id'],{},summary='Synthetic')):
            with self.assertRaises(RuntimeError):action()
        self.assertEqual(len(self.transport.calls),requests);self.assertEqual(calls,[1])

    def test_ac2602_local_policy_deny_occurs_before_any_approval_network(self):
        denied=replace(self.config,policy=Policy('deny',()))
        with Application(denied,subject='demo-agent') as app:
            governed=app.reviewed_tool(lambda record=1:None,name='write',client=self.client,disclose_arguments=True)
            with self.assertRaises(ActionDenied):governed.prepare({},summary='Synthetic')
        self.assertEqual(self.transport.calls,[])

    def test_ac2602_unknown_confirmation_does_not_retry_or_release_claim(self):
        calls=[]
        with Application(self.config,subject='demo-agent') as app:
            governed=app.reviewed_tool(lambda record=1:calls.append(record),name='write',client=self.client,disclose_arguments=True)
            ticket=governed.prepare({},summary='Synthetic');self.transport.approve();self.transport.fault='lost-complete'
            result=governed.resume(ticket['action_id'],{},summary='Synthetic');self.assertEqual(result.confirmation,'unknown')
            with self.assertRaises(ApprovalUnavailable):governed.resume(ticket['action_id'],{},summary='Synthetic')
        self.assertEqual(calls,[1]);self.assertEqual(self.transport.record['execution_state'],'claimed')

    def test_ac2602_business_error_identity_and_failed_state_remain_original(self):
        original=ValueError('private business failure');calls=[]
        def write(record=1):calls.append(record);raise original
        with Application(self.config,subject='demo-agent') as app:
            governed=app.reviewed_tool(write,client=self.client,disclose_arguments=True)
            ticket=governed.prepare({},summary='Synthetic');self.transport.approve()
            with self.assertRaises(ValueError) as caught:governed.resume(ticket['action_id'],{},summary='Synthetic')
            self.assertIs(caught.exception,original);self.assertEqual(app.status()['active_calls'],0)
        self.assertEqual(calls,[1]);self.assertEqual(self.transport.record['execution_state'],'failed')

    def test_ac2602_entire_claim_and_execution_hold_application_lease(self):
        def during_claim():
            self.assertEqual(app.status()['active_calls'],1)
            with self.assertRaises(RuntimeError):app.close()
        self.transport.on_claim=during_claim
        with Application(self.config,subject='demo-agent') as app:
            governed=app.reviewed_tool(lambda record=1:record,name='write',client=self.client,disclose_arguments=True)
            ticket=governed.prepare({},summary='Synthetic');self.transport.approve()
            self.assertEqual(governed.resume(ticket['action_id'],{},summary='Synthetic').value,1)
        self.assertEqual(app.status()['state'],'closed')


class ConfiguredAsyncReview(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.config=load_application(write_review_application(self.folder))
    async def asyncTearDown(self):aegis.shutdown();self.tmp.cleanup()

    async def test_ac2602_async_client_is_borrowed_and_prepare_resume_stay_in_task(self):
        transport=AsyncTransport();calls=[];tasks=[]
        async with async_client(transport) as connection:
            with Application(self.config,subject='demo-agent') as app:
                async def write(record=1):calls.append(record);tasks.append(asyncio.current_task());return 'synthetic'
                governed=app.reviewed_tool(write,client=connection,disclose_arguments=True)
                ticket=await governed.prepare({},summary='Synthetic');transport.approve(ticket['action_id'])
                result=await governed.resume(ticket['action_id'],{},summary='Synthetic')
                self.assertEqual(result.value,'synthetic');self.assertIs(tasks[0],asyncio.current_task())
                with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic')
            self.assertFalse(transport.closed)
            with self.assertRaises(RuntimeError):await governed.prepare({},summary='Synthetic')
        self.assertTrue(transport.closed);self.assertEqual(calls,[1])

    async def test_ac2602_cancellation_after_committed_claim_releases_lease_not_action(self):
        transport=AsyncTransport();calls=[]
        async with async_client(transport) as connection:
            with Application(self.config,subject='demo-agent') as app:
                async def write(record=1):calls.append(record)
                governed=app.reviewed_tool(write,client=connection,disclose_arguments=True)
                ticket=await governed.prepare({},summary='Synthetic');transport.approve(ticket['action_id'])
                async def cancel(record):raise asyncio.CancelledError('synthetic after commit')
                transport.hooks['claim']=cancel
                with self.assertRaises(asyncio.CancelledError):await governed.resume(ticket['action_id'],{},summary='Synthetic')
                self.assertEqual(app.status()['active_calls'],0);transport.hooks.clear()
                with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic')
        self.assertEqual(calls,[]);self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'claimed')

    async def test_ac2602_business_cancel_can_have_partial_effect_and_is_not_confirmed_failed(self):
        transport=AsyncTransport();calls=[]
        async with async_client(transport) as connection:
            with Application(self.config,subject='demo-agent') as app:
                async def write(record=1):
                    calls.append(record)
                    with self.assertRaises(RuntimeError):app.close()
                    raise asyncio.CancelledError('synthetic partial effect')
                governed=app.reviewed_tool(write,client=connection,disclose_arguments=True)
                ticket=await governed.prepare({},summary='Synthetic');transport.approve(ticket['action_id'])
                with self.assertRaises(asyncio.CancelledError):await governed.resume(ticket['action_id'],{},summary='Synthetic')
                self.assertEqual(app.status()['active_calls'],0)
        self.assertEqual(calls,[1]);self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'claimed')

    async def test_ac2601_wrong_client_mode_fails_before_binding_and_direct_downgrade(self):
        async with async_client(AsyncTransport()) as connection:
            with Application(self.config,subject='demo-agent') as app:
                async def asynchronous(record=1):return record
                def synchronous(record=1):return record
                with self.assertRaises(ValueError):app.reviewed_tool(asynchronous,name='write',client=client(),disclose_arguments=True)
                with self.assertRaises(ValueError):app.reviewed_tool(synchronous,name='write',client=connection,disclose_arguments=True)
                self.assertEqual(app.status()['bound_tools'],[])
