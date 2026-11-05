import copy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

from aegis_policy import Decision, Policy
from aegis_runtime import Runtime, ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.reviewed_execution import ReviewedTool, reviewed_snapshot
from tests.fixtures.reviewed import client, tool, payload


class Transport:
    def __init__(self): self.claimed=False; self.calls=[]; self.fault=None; self.record=None; self.on_claim=lambda:None
    def send(self, path, data, **kwargs):
        self.calls.append((path, copy.deepcopy(data), kwargs))
        if path == "/api/v1/reviewed-actions":
            now=datetime.now(timezone.utc)
            self.record={**copy.deepcopy(data), "status":"pending", "created_at":now.isoformat(), "expires_at":(now+timedelta(seconds=data["ttl_seconds"])).isoformat(), "decided_at":None,"reviewer":None,
                         "execution_state":"available","claim_id":None,"executor":None,"claimed_at":None,"finished_at":None}
            return copy.deepcopy(self.record)
        if path.endswith("/claim"):
            if self.claimed or self.record["status"] != "approved": raise ApprovalUnavailable()
            self.claimed=True; self.on_claim()
            self.record.update(execution_state="claimed",claim_id=data["claim_id"],executor="local-executor",claimed_at=datetime.now(timezone.utc).isoformat())
            if self.fault=="lost-claim": raise ApprovalUnavailable()
            return {**copy.deepcopy(self.record),"remaining_ms":0 if self.fault=="late" else 200000}
        if self.fault=="lost-complete": raise ApprovalUnavailable()
        self.record.update(execution_state=data["outcome"],finished_at=datetime.now(timezone.utc).isoformat())
        return copy.deepcopy(self.record)
    def approve(self):
        self.record.update(status="approved",reviewer="local-reviewer",decided_at=datetime.now(timezone.utc).isoformat())


class ReviewedExecution(unittest.TestCase):
    def setup_tool(self, fn, **changes):
        connection=client(); transport=Transport(); connection._send=Mock(side_effect=transport.send)
        return tool(fn,connection,**changes),connection,transport

    def test_ac1101_requires_explicit_disclosure_and_regular_named_sync_function(self):
        def write(record="demo"): pass
        async def asynchronous(): pass
        def generator(): yield 1
        def variadic(**kwargs): pass
        def positional(value, /): pass
        for fn in (asynchronous,generator,variadic,positional):
            with self.assertRaises(TypeError): tool(fn)
        with self.assertRaises(ValueError): tool(write,disclose_arguments=False)
        with self.assertRaises(ValueError): tool(write,disclose_arguments=1)
        with self.assertRaises(ValueError): tool(write).prepare({},summary="demo",action_id="")

    def test_ac1101_snapshot_defaults_signature_types_and_cross_service_digest(self):
        from aegis_collector.api.reviewed import review_digest
        def write(record, value=1): pass
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({"record":["demo"]},summary="Synthetic change")
        self.assertEqual(ticket["review_arguments"],{"record":["demo"],"value":1})
        self.assertEqual(ticket["review_digest"],review_digest(ticket["review_arguments"]))
        for arguments in ({}, {"record":1,"other":2}, {"record":1.0}, {"record":"x\x00"}, {"record":["x"*2048]*2}):
            with self.subTest(arguments_type=type(arguments).__name__), self.assertRaises((ValueError,TypeError)): governed.prepare(arguments,summary="demo")
        class CustomKey(str): pass
        with self.assertRaises(ValueError): governed.prepare({CustomKey('record'):1},summary='demo')
        for value in ({"v":True},{"v":1},{"v":None},{"v":["中文",r"\u0000"]}):
            snapshot,digest=reviewed_snapshot(value);self.assertEqual(digest,review_digest(snapshot))

    def test_ac1104_pending_denied_and_policy_deny_execute_zero(self):
        calls=[]
        def write(record=1): calls.append(1)
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo")
        with self.assertRaises(ApprovalUnavailable): governed.resume(ticket["action_id"],{},summary="demo")
        self.assertEqual(calls,[])
        denied=tool(write,connection,policy=Policy("denied",()))
        before=connection._send.call_count
        with self.assertRaises(ActionDenied): denied.prepare({},summary="demo")
        with self.assertRaises(ActionDenied): denied.resume(ticket["action_id"],{},summary="demo")
        self.assertEqual(connection._send.call_count,before)

    def test_ac1104_success_once_preserves_value_and_uses_isolated_snapshot(self):
        calls=[]; result=object(); original={"record":["approved"]}
        def write(record, value=1): calls.append((record,value)); return result
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare(original,summary="demo");transport.approve()
        transport.on_claim=lambda:original["record"].append("mutation")
        outcome=governed.resume(ticket["action_id"],original,summary="demo")
        self.assertIs(outcome.value,result);self.assertEqual(outcome.confirmation,"confirmed")
        self.assertEqual(calls,[(["approved"],1)])
        self.assertEqual(transport.record["execution_state"],"completed")
        with self.assertRaises(ApprovalUnavailable): governed.resume(ticket["action_id"],{"record":["approved"]},summary="demo")
        self.assertEqual(len(calls),1)

    def test_ac1104_lost_claim_or_deadline_consumes_without_execution(self):
        for fault in ("lost-claim","late"):
            calls=[]
            def write(value=1): calls.append(1)
            governed,connection,transport=self.setup_tool(write)
            ticket=governed.prepare({},summary="demo");transport.approve();transport.fault=fault
            with self.assertRaises(ApprovalUnavailable): governed.resume(ticket["action_id"],{},summary="demo")
            self.assertTrue(transport.claimed);self.assertEqual(calls,[])
            with self.assertRaises(ApprovalUnavailable): governed.resume(ticket["action_id"],{},summary="demo")
            self.assertEqual(calls,[])
        # An instrumentation hook can delay entry after the first deadline
        # check. The final check must still prevent the business call.
        from contextlib import contextmanager
        calls=[];clock=[0.0]
        def write(value=1):calls.append(1)
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo");transport.approve()
        @contextmanager
        def delayed_span(*args,**kwargs):
            clock[0]=201.0
            yield
        with patch('aegis_runtime.reviewed_execution.time.monotonic',side_effect=lambda:clock[0]), patch('aegis_runtime.reviewed_execution.governed_tool_span',delayed_span), self.assertRaises(ApprovalUnavailable):
            governed.resume(ticket['action_id'],{},summary='demo')
        self.assertEqual(calls,[]);self.assertEqual(transport.record['execution_state'],'claimed')

    def test_ac1104_completion_failure_returns_unknown_and_never_repeats_business(self):
        calls=[]
        def write(value=1): calls.append(1);return calls
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo");transport.approve();transport.fault="lost-complete"
        outcome=governed.resume(ticket["action_id"],{},summary="demo")
        self.assertIs(outcome.value,calls);self.assertEqual(outcome.confirmation,"unknown")
        self.assertEqual(transport.record["execution_state"],"claimed")
        with self.assertRaises(ApprovalUnavailable): governed.resume(ticket["action_id"],{},summary="demo")
        self.assertEqual(calls,[1])

    def test_ac1104_original_business_error_and_failed_confirmation(self):
        original=ValueError("private synthetic error")
        def write(value=1): raise original
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo");transport.approve()
        with self.assertRaises(ValueError) as context: governed.resume(ticket["action_id"],{},summary="demo")
        self.assertIs(context.exception,original);self.assertEqual(transport.record["execution_state"],"failed")
        self.assertNotIn("private",repr(transport.calls))

    def test_ac1104_rechecks_policy_after_claim_before_function(self):
        calls=[]
        def write(value=1): calls.append(1)
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo");transport.approve()
        allow=Decision("allow","explicit_allow","review-v1","permit")
        deny=Decision("deny","no_match","review-v1")
        with patch.object(Runtime,"_decide",side_effect=[allow,deny]), self.assertRaises(ActionDenied): governed.resume(ticket["action_id"],{},summary="demo")
        self.assertTrue(transport.claimed);self.assertEqual(calls,[])

    def test_ac1104_bad_claim_response_and_fixed_network_failures(self):
        calls=[]
        def write(value=1): calls.append(1)
        governed,connection,transport=self.setup_tool(write)
        ticket=governed.prepare({},summary="demo");transport.approve()
        original=transport.send
        def corrupt(path,data,**kwargs):
            value=original(path,data,**kwargs)
            if path.endswith('/claim'):value['tool_revision']='changed'
            return value
        connection._send.side_effect=corrupt
        with self.assertRaises(ApprovalUnavailable): governed.resume(ticket['action_id'],{},summary='demo')
        self.assertEqual(calls,[])
        actual=client();actual._opener=Mock();actual._opener.open.side_effect=TimeoutError('private credential')
        with self.assertRaisesRegex(ApprovalUnavailable,'^approval service unavailable$'): actual.prepare_reviewed(payload())
        self.assertEqual(actual._opener.open.call_count,1)
        with self.assertRaises(ValueError):actual.claim({**payload(),'action_id':'../other'})
        with self.assertRaises(ValueError):actual.complete(payload(),'0'*32,'completed')
