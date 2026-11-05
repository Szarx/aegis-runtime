import asyncio
import hashlib
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import aegis
from aegis_policy import Policy,Rule,Decision
from aegis_runtime import Runtime,ActionDenied
from aegis_runtime.application import Application,ApplicationConfig,Telemetry,ToolBinding
from aegis_runtime.approvals import ApprovalUnavailable,policy_digest
from aegis_runtime.policy_tool import PolicyTool,AsyncPolicyTool,PendingReview
from tests.fixtures.reviewed import client


def policy(effect='require_approval',revision='policy-v2'):
    return Policy(revision,(Rule('rule',effect,('agent',),('write',),('records.write',)),),'aegis.policy.v2')


def pending(payload):
    now=datetime.now(timezone.utc)
    return dict(**payload,status='pending',created_at=now.isoformat(),expires_at=(now+timedelta(seconds=payload['ttl_seconds'])).isoformat(),decided_at=None,reviewer=None,execution_state='available',claim_id=None,executor=None,claimed_at=None,finished_at=None)


def tool(function,connection=None,**changes):
    return PolicyTool(function,**{**dict(client=connection or client(),policy=policy(),subject='agent',permission='records.write',tool='write',tool_revision='impl-v1',disclose_arguments=True),**changes})


class PolicyRouting(unittest.TestCase):
    def test_legacy_approval_digest_bytes_and_v2_domain_separation(self):
        old=Policy('old',(Rule('permit','allow',('agent',),('write',),('records.write',)),))
        raw=dict(schema_version='aegis.policy.v1',revision='old',rules=[dict(id='permit',effect='allow',subjects=['agent'],tools=['write'],permissions=['records.write'])])
        expected=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(policy_digest(old),expected)
        self.assertNotEqual(policy_digest(policy('allow')),policy_digest(Policy('policy-v2',policy('allow').rules)))

    def test_direct_branch_cannot_execute_if_recheck_now_requires_review(self):
        calls=[];connection=client();connection._send=Mock()
        target=tool(lambda value=1:calls.append(value),connection,policy=policy('allow'))
        allowed=Decision('allow','explicit_allow','policy-v2','rule')
        required=Decision('require_approval','explicit_require_approval','policy-v2','rule')
        with patch.object(Runtime,'_decide',side_effect=[allowed,required,required]):
            with self.assertRaises(ActionDenied):target.invoke({},summary='Synthetic')
        self.assertEqual(calls,[]);connection._send.assert_not_called()

    def test_allow_deny_and_review_are_distinct_and_plain_runtime_fails_closed(self):
        calls=[];connection=client();connection._send=Mock(side_effect=lambda path,data,**kwargs:pending(data))
        def write(value=3):calls.append(value);return value
        self.assertEqual(tool(write,connection,policy=policy('allow')).invoke({},summary='Synthetic'),3)
        connection._send.assert_not_called()
        with self.assertRaises(ActionDenied):tool(write,connection,policy=policy('deny')).invoke({},summary='Synthetic')
        ticket=tool(write,connection).invoke({},summary='Synthetic')
        self.assertIsInstance(ticket,PendingReview);self.assertEqual(ticket.record['review_arguments'],{'value':3})
        self.assertEqual(calls,[3])
        with self.assertRaises(ActionDenied):Runtime(policy(),subject='agent').tool(write,name='write',permission='records.write')()
        self.assertEqual(calls,[3])

    def test_tampered_ticket_arguments_versions_and_policy_fail_before_claim(self):
        connection=client();connection._send=Mock(side_effect=lambda path,data,**kwargs:pending(data))
        def write(value=3):raise AssertionError('no execution')
        governed=tool(write,connection);record=governed.invoke({},summary='Synthetic').record
        before=connection._send.call_count
        for changed in ({**record,'review_digest':'0'*64},{**record,'policy_digest':'0'*64},{**record,'trace_id':'1'*32}):
            with self.assertRaises(ApprovalUnavailable):governed.resume(changed,{},summary='Synthetic')
        for other in (tool(write,connection,tool_revision='changed'),tool(write,connection,policy=policy(revision='changed'))):
            with self.assertRaises(ApprovalUnavailable):other.resume(record,{},summary='Synthetic')
        with self.assertRaises(ApprovalUnavailable):governed.resume(record,{'value':4},summary='Synthetic')
        self.assertEqual(connection._send.call_count,before)

    def test_request_metadata_is_bounded_and_omits_argument_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'spans.jsonl';sdk=aegis.init('policy-tool-test',output_path=path)
            try:
                connection=client();connection._send=Mock(side_effect=lambda path,data,**kwargs:pending(data))
                def write(value='private-argument'):return value
                record=tool(write,connection).invoke({},summary='Synthetic').record
                self.assertIsNone(record['trace_id']);self.assertTrue(sdk.flush())
            finally:sdk.shutdown()
            rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0]['schema_version'],'aegis.span.v5')
            self.assertEqual(rows[0]['attributes']['aegis.action.outcome'],'awaiting_approval')
            self.assertNotIn('private-argument',str(rows));self.assertEqual(rows[0]['status'],'UNSET')

    def test_application_v4_binding_floor_and_closed_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry=Telemetry('jsonl',output_path=Path(directory)/'trace.jsonl')
            binding=ToolBinding('write','records.write','policy','v1')
            for version in ('aegis.application.v1','aegis.application.v2','aegis.application.v3'):
                with self.assertRaises(ValueError):ApplicationConfig('test',policy(),(binding,),telemetry,version)
            config=ApplicationConfig('test',policy('allow'),(binding,),telemetry,'aegis.application.v4')
            with Application(config,subject='agent') as app:
                with self.assertRaises(ValueError):app.tool(lambda:None,name='write')
                governed=app.policy_tool(lambda value=1:value,client=client(),name='write',disclose_arguments=True)
                self.assertEqual(governed.invoke({},summary='Synthetic'),1)
                with self.assertRaises(ValueError):app.policy_tool(lambda:None,client=client(),name='write',disclose_arguments=True)
            with self.assertRaises(RuntimeError):governed.invoke({},summary='Synthetic')

    def test_invalid_or_missing_disclosure_and_clients_never_fall_back(self):
        with self.assertRaises(ValueError):tool(lambda:None,disclose_arguments=False)
        with self.assertRaises(ValueError):tool(lambda:None,client=None)
        with self.assertRaises(TypeError):tool(lambda **kwargs:None)
