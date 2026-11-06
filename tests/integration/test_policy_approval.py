import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import uuid
import psycopg
from psycopg import sql
from fastapi.responses import JSONResponse
import aegis
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_policy import Policy,Rule
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.policy_tool import PolicyTool,AsyncPolicyTool,PendingReview
from aegis_runtime.reviewed_execution import ReviewedTool
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from tests.fixtures.live_server import LiveServer
from tests.fixtures.reviewed import client

ROOT=Path(__file__).resolve().parents[2];DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


def policy(effect='require_approval',revision='policy-v2'):
    return Policy(revision,(Rule('rule',effect,('agent',),('write',),('records.write',)),),'aegis.policy.v2')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class PolicyApprovalPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_policy_approval_'+uuid.uuid4().hex;self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        app=create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor')
        self.lose=None
        @app.middleware('http')
        async def acknowledgement(request,call_next):
            response=await call_next(request)
            phase='claim' if request.url.path.endswith('/claim') else 'complete' if request.url.path.endswith('/complete') else 'prepare' if request.url.path=='/api/v1/reviewed-actions' and request.method=='POST' else None
            if self.lose is not None and phase==self.lose and response.status_code==200:
                self.lose=None;return JSONResponse({'error':'synthetic acknowledgement unavailable'},503)
            return response
        self.live=LiveServer(app).start();self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
    def tearDown(self):
        aegis.shutdown();self.live.close();self.tmp.cleanup()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def request(self,path,payload=None,token='synthetic-reviewer'):
        with urlopen(Request(self.live.endpoint+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=5) as response:return json.load(response)
    def record(self,action):return next(row for row in self.request('/api/v1/reviewed-actions?limit=100')['items'] if row['action_id']==action)
    def decide(self,record,value='approved'):
        return self.request('/api/v1/reviewed-actions/'+record['action_id']+'/decision',dict(decision=value,review_digest=record['review_digest']))
    def governed(self,function,**changes):
        return PolicyTool(function,**{**dict(client=client(self.live.endpoint),policy=policy(),subject='agent',permission='records.write',tool='write',tool_revision='v1',disclose_arguments=True),**changes})
    def cli(self,code,*args):
        result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8','AEGIS_API_TOKEN':'synthetic-trace',
            'AEGIS_APPROVAL_REQUEST_TOKEN':'synthetic-producer','AEGIS_APPROVAL_EXECUTION_TOKEN':'synthetic-executor','AEGIS_APPROVAL_BINDING_KEY':b'synthetic-reviewed-binding-key-11'.hex()},
            capture_output=True,text=True,encoding='utf-8',timeout=35)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr);return json.loads(result.stdout)

    def test_full_native_langgraph_sync_async_new_process_and_offline_export_replay(self):
        for mode in ('native','langgraph'):
            for asynchronous in (False,True):
                for subject in ('reader','reviewer','blocked'):
                    folder=self.folder/(mode+str(asynchronous)+subject);folder.mkdir()
                    config=json.loads((ROOT/'examples/policy-approval/application.json').read_text(encoding='utf-8'))
                    config['policy_file']=str(ROOT/'examples/policy-approval/policy.json');config['telemetry']=dict(mode='otlp',endpoint=self.live.endpoint+'/v1/traces',token_env='AEGIS_API_TOKEN')
                    path=folder/'application.json';path.write_text(json.dumps(config));ticket=folder/'ticket.json';calls=folder/'calls.jsonl'
                    def host(command,code=0,*extra):
                        return self.cli(code,'examples/policy-approval/agent.py',command,'--config',str(path),'--endpoint',self.live.endpoint,'--subject',subject,
                            '--ticket',str(ticket),'--calls',str(calls),'--mode',mode,*(['--async'] if asynchronous else []),*extra)
                    report=host('request',1 if subject=='blocked' else 0)
                    if subject=='reviewer':
                        self.assertEqual(report['status'],'pending_review');self.assertFalse(calls.exists())
                        saved=json.loads(ticket.read_text());record=saved['record'];host('resume',2)
                        self.decide(record);host('resume',2,'--value','tampered')
                        self.assertEqual(self.record(record['action_id'])['execution_state'],'available')
                        self.assertEqual(host('resume')['confirmation'],'confirmed');host('resume',2)
                    self.assertEqual(len(calls.read_text().splitlines()) if calls.exists() else 0,int(subject!='blocked'))
        events=self.request('/api/v1/security-events?limit=100',token='synthetic-trace')
        self.assertEqual(events['total'],16)
        review=[row for row in events['items'] if row['effect']=='require_approval'];self.assertEqual(len(review),8)
        self.assertEqual(sum(row['outcome']=='awaiting_approval' for row in review),4)
        listed = self.request('/api/v1/traces?limit=100', token='synthetic-trace')
        signals = {row['trace_id']: row['governance_signal'] for row in listed['items']}
        expected = {'denied': 'denied', 'awaiting_approval': 'approval_requested', 'completed': 'review_tool_returned'}
        for event in events['items']:
            self.assertEqual(signals[event['trace_id']], expected.get(event['outcome']) if event['effect'] != 'allow' else None)
        for event in review:
            detail=self.request('/api/v1/traces/'+event['trace_id'],token='synthetic-trace')
            self.assertEqual(detail['trace']['governance_signal'], signals[event['trace_id']])
            self.assertNotIn('synthetic-private-value',str(detail));self.assertEqual(event['rule_id'],'review')
            selected=next(s for s in detail['spans'] if s['span_id']==event['span_id'])
            self.assertEqual(selected['attributes']['aegis.mapping.version'],'aegis.governance.v2')
        bundle=self.folder/'events'
        self.assertEqual(self.cli(0,'scripts/security_export.py','export','--base-url',self.live.endpoint,'--effect','require_approval','--output',str(bundle))['count'],8)
        self.live.close();self.assertEqual(self.cli(0,'scripts/security_export.py','verify',str(bundle))['count'],8)
        candidate=self.folder/'candidate.json';doc=json.loads((ROOT/'examples/policy-approval/policy.json').read_text());doc['rules'][1]['effect']='allow';candidate.write_text(json.dumps(doc))
        replay=self.cli(1,'scripts/replay_security.py',str(bundle),'--policy',str(candidate),'--output',str(self.folder/'replay.json'))
        self.assertEqual(replay['counts']['widened'],8);self.assertEqual(replay['recorded_outcomes'],{'awaiting_approval':4,'completed':4})

    def test_ac4703_exact_lookup_outside_first_page_requires_reviewer(self):
        calls = []
        tool = self.governed(lambda value=1: calls.append(value))
        record = tool.invoke({}, summary='Target action').record
        for _ in range(20):
            tool.invoke({}, summary='Later synthetic action')
        root = '/api/v1/reviewed-actions'
        action_id = record['action_id']
        self.assertNotIn(action_id, {row['action_id'] for row in self.request(root)['items']})
        exact = root + '?limit=1&offset=0&action_id=' + action_id
        for token in ('synthetic-trace', 'synthetic-producer', 'synthetic-executor'):
            with self.assertRaises(HTTPError) as error:
                self.request(exact, token=token)
            self.assertEqual(error.exception.code, 401)
        pending = self.request(exact)
        self.assertEqual((pending['total'], pending['items'][0]['action_id']), (1, action_id))
        self.assertEqual(pending['items'][0]['status'], 'pending')
        self.decide(record)
        self.assertEqual(self.request(exact)['items'][0]['execution_state'], 'available')
        self.assertEqual(calls, [])
        self.assertEqual(tool.resume(record, {}, summary='Target action').confirmation, 'confirmed')
        confirmed = self.request(exact)['items'][0]
        self.assertEqual((confirmed['status'], confirmed['execution_state'], calls), ('approved', 'completed', [1]))
        self.assertEqual(self.request(root + '?action_id=' + 'f' * 32)['items'], [])
        with self.assertRaises(HTTPError) as error:
            self.request(root + '?action_id=' + '0' * 32)
        self.assertEqual(error.exception.code, 400)

    def test_pending_reject_expiry_tamper_policy_and_forced_review_floor(self):
        calls=[]
        def write(value=1):calls.append(value)
        governed=self.governed(write)
        for case in ('pending','rejected','expired','arguments','policy','tool'):
            record=governed.invoke({},summary='Synthetic').record
            if case!='pending':self.decide(record,'rejected' if case=='rejected' else 'approved')
            if case=='expired':
                with self.store.connection() as connection:connection.execute(sql.SQL("UPDATE {}.approvals SET created_at=clock_timestamp()-interval '301 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE action_id=%s").format(sql.Identifier(self.schema)),[record['action_id']])
            target=self.governed(write,policy=policy('allow')) if case=='policy' else self.governed(write,tool_revision='v2') if case=='tool' else governed
            with self.assertRaises(ApprovalUnavailable):target.resume(record,{'value':2} if case=='arguments' else {},summary='Synthetic')
            self.assertEqual(calls,[])
        forced=ReviewedTool(write,client=client(self.live.endpoint),policy=policy('allow'),subject='agent',permission='records.write',tool='write',tool_revision='v1',disclose_arguments=True)
        record=forced.prepare({},summary='Synthetic')
        with self.assertRaises(ApprovalUnavailable):forced.resume(record['action_id'],{},summary='Synthetic')
        self.assertEqual(calls,[])

    def test_concurrent_once_and_lost_prepare_claim_completion_acknowledgements(self):
        calls=[]
        def write(value=1):calls.append(value);return value
        governed=self.governed(write);record=governed.invoke({},summary='Synthetic').record;self.decide(record)
        def resume():
            try:return governed.resume(record,{},summary='Synthetic').confirmation
            except ApprovalUnavailable:return 'unavailable'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(lambda _:resume(),range(2))),['confirmed','unavailable'])
        self.assertEqual(calls,[1])
        sdk=aegis.init('policy-ack-test',endpoint=self.live.endpoint+'/v1/traces',headers={'Authorization':'Bearer synthetic-trace'})
        try:
            self.lose='prepare';action=uuid.uuid4().hex
            with self.assertRaises(ApprovalUnavailable):governed.invoke({},summary='Synthetic',action_id=action)
            record=governed.invoke({},summary='Synthetic',action_id=action).record
            self.assertEqual(record['action_id'],action);self.assertEqual(calls,[1]);self.decide(record)
            self.lose='claim'
            with self.assertRaises(ApprovalUnavailable):governed.resume(record,{},summary='Synthetic')
            self.assertEqual(self.record(action)['execution_state'],'claimed')
            with self.assertRaises(ApprovalUnavailable):governed.resume(record,{},summary='Synthetic')
            self.assertEqual(calls,[1])
            record=governed.invoke({},summary='Synthetic').record;self.decide(record);self.lose='complete'
            self.assertEqual(governed.resume(record,{},summary='Synthetic').confirmation,'unknown')
            self.assertEqual(self.record(record['action_id'])['execution_state'],'completed')
            with self.assertRaises(ApprovalUnavailable):governed.resume(record,{},summary='Synthetic')
            self.assertEqual(calls,[1,1]);self.assertTrue(sdk.flush())
        finally:sdk.shutdown()

    def test_async_partial_failure_cancellation_and_unknown_never_retry(self):
        async def run():
            calls=[];entered=asyncio.Event()
            async with AsyncReviewedClient(self.live.endpoint,token='synthetic-producer',execution_token='synthetic-executor',binding_key=b'synthetic-reviewed-binding-key-11') as transport:
                def governed(function,**changes):return AsyncPolicyTool(function,**{**dict(client=transport,policy=policy(),subject='agent',permission='records.write',tool='write',tool_revision='v1',disclose_arguments=True),**changes})
                async def failing(value=1):calls.append(value);raise ValueError('synthetic partial failure')
                target=governed(failing);record=(await target.invoke({},summary='Synthetic')).record;self.decide(record)
                with self.assertRaises(ValueError):await target.resume(record,{},summary='Synthetic')
                self.assertEqual(self.record(record['action_id'])['execution_state'],'failed')
                with self.assertRaises(ApprovalUnavailable):await target.resume(record,{},summary='Synthetic')
                async def cancelled(value=1):calls.append(value);entered.set();await asyncio.Event().wait()
                target=governed(cancelled);record=(await target.invoke({},summary='Synthetic')).record;self.decide(record)
                task=asyncio.create_task(target.resume(record,{},summary='Synthetic'));await asyncio.wait_for(entered.wait(),3);task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
                self.assertEqual(self.record(record['action_id'])['execution_state'],'claimed')
                with self.assertRaises(ApprovalUnavailable):await target.resume(record,{},summary='Synthetic')
                async def successful(value=1):calls.append(value);return value
                target=governed(successful);record=(await target.invoke({},summary='Synthetic')).record;self.decide(record);self.lose='complete'
                self.assertEqual((await target.resume(record,{},summary='Synthetic')).confirmation,'unknown')
                with self.assertRaises(ApprovalUnavailable):await target.resume(record,{},summary='Synthetic')
                self.assertEqual(calls,[1,1,1])
                before=self.request('/api/v1/reviewed-actions')['total'];task=asyncio.create_task(target.invoke({},summary='Synthetic'));task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
                self.assertEqual(self.request('/api/v1/reviewed-actions')['total'],before)
        asyncio.run(run())
