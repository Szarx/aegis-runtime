import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from fastapi.responses import JSONResponse
import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_runtime.application import Application,load_application
from aegis_runtime.approvals import ApprovalUnavailable
from tests.fixtures.configured_review import write_review_application
from tests.fixtures.application_config import ROOT
from tests.fixtures.live_server import LiveServer
from tests.fixtures.reviewed import client

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class ConfiguredReviewPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_configured_review_'+uuid.uuid4().hex;self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        app=create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor')
        self.lose_complete_ack=False
        @app.middleware('http')
        async def fault(request,call_next):
            response=await call_next(request)
            if self.lose_complete_ack and request.url.path.endswith('/complete') and response.status_code==200:
                self.lose_complete_ack=False
                return JSONResponse({'error':'synthetic acknowledgement unavailable'},503)
            return response
        self.live=LiveServer(app).start()
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
    def tearDown(self):
        self.live.close();self.tmp.cleanup()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def request(self,path,*,token='synthetic-reviewer',payload=None):
        body=None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(self.live.endpoint+path,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=10) as response:return json.load(response)
    def records(self):return self.request('/api/v1/reviewed-actions')['items']
    def record(self,action):return next(r for r in self.records() if r['action_id']==action)
    def decide(self,action,decision='approved'):
        record=self.record(action)
        return self.request('/api/v1/reviewed-actions/'+action+'/decision',payload=dict(decision=decision,review_digest=record['review_digest']))
    def cli(self,code,*args):
        result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8','AEGIS_API_TOKEN':'synthetic-trace',
            'AEGIS_APPROVAL_REQUEST_TOKEN':'synthetic-producer','AEGIS_APPROVAL_EXECUTION_TOKEN':'synthetic-executor',
            'AEGIS_APPROVAL_BINDING_KEY':b'synthetic-reviewed-binding-key-11'.hex()},capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr);return json.loads(result.stdout)
    def host(self,config,calls,command,code=0,*,asynchronous=False,action=None,scenario='success',value='synthetic'):
        return self.cli(code,'examples/configured-review/agent.py',command,'--config',str(config),'--endpoint',self.live.endpoint,'--calls',str(calls),
            '--scenario',scenario,'--value',value,*(['--async'] if asynchronous else []),*(['--action-id',action] if action else []))
    def count(self,path):return len(path.read_text().splitlines()) if path.exists() else 0

    def test_ac2603_sync_async_new_process_approval_reject_tamper_and_governance_export(self):
        approved=[]
        for asynchronous in (False,True):
            folder=self.folder/str(asynchronous);config=write_review_application(folder,endpoint=self.live.endpoint+'/v1/traces');calls=folder/'calls.jsonl'
            action=self.host(config,calls,'prepare',asynchronous=asynchronous)['action_id'];self.assertEqual(self.count(calls),0)
            record=self.record(action);self.assertEqual(record['review_arguments']['record_id'],9223372036854775807)
            self.host(config,calls,'resume',1,asynchronous=asynchronous,action=action);self.assertEqual(self.count(calls),0)
            self.decide(action)
            self.host(config,calls,'resume',1,asynchronous=asynchronous,action=action,value='changed-arguments');self.assertEqual(self.count(calls),0)
            result=self.host(config,calls,'resume',asynchronous=asynchronous,action=action);self.assertEqual(result['confirmation'],'confirmed')
            self.host(config,calls,'resume',1,asynchronous=asynchronous,action=action);self.assertEqual(self.count(calls),1)
            approved.append(action);self.assertEqual(self.record(action)['execution_state'],'completed')
            rejected=self.host(config,calls,'prepare',asynchronous=asynchronous)['action_id'];self.decide(rejected,'rejected')
            self.host(config,calls,'resume',1,asynchronous=asynchronous,action=rejected);self.assertEqual(self.count(calls),1)
        with self.assertRaises(HTTPError) as denied:self.request('/api/v1/reviewed-actions',token='synthetic-trace')
        self.assertEqual(denied.exception.code,401)
        events=self.request('/api/v1/security-events',token='synthetic-trace');self.assertEqual(events['total'],2)
        self.assertEqual({e['action_id'] for e in events['items']},set(approved))
        for event in events['items']:
            detail=self.request('/api/v1/traces/'+event['trace_id'],token='synthetic-trace')
            span=next(s for s in detail['spans'] if s['span_id']==event['span_id'])
            self.assertIsNotNone(span['parent_span_id']);self.assertNotIn('review_arguments',str(detail))
            self.assertNotIn('record_id',str(span['attributes']))
        bundle=self.folder/'export';self.assertEqual(self.cli(0,'scripts/security_export.py','export','--base-url',self.live.endpoint,'--output',str(bundle))['count'],2)
        self.live.close()
        replay=self.cli(0,'scripts/replay_security.py',str(bundle),'--policy',str(self.folder/'False/policy.json'),'--output',str(self.folder/'replay.json'))
        self.assertEqual(replay['counts']['unchanged'],2)

    def test_ac2603_failure_cancellation_expiry_and_tool_version_preserve_consumption(self):
        config=write_review_application(self.folder);calls=self.folder/'calls.jsonl'
        failed=self.host(config,calls,'prepare',scenario='failure')['action_id'];self.decide(failed)
        self.host(config,calls,'resume',2,action=failed,scenario='failure');self.assertEqual(self.count(calls),1)
        self.host(config,calls,'resume',1,action=failed,scenario='failure');self.assertEqual(self.count(calls),1);self.assertEqual(self.record(failed)['execution_state'],'failed')
        cancelled=self.host(config,calls,'prepare',asynchronous=True,scenario='cancel')['action_id'];self.decide(cancelled)
        self.host(config,calls,'resume',3,asynchronous=True,action=cancelled,scenario='cancel');self.assertEqual(self.count(calls),2)
        self.host(config,calls,'resume',1,asynchronous=True,action=cancelled,scenario='cancel');self.assertEqual(self.count(calls),2);self.assertEqual(self.record(cancelled)['execution_state'],'claimed')
        expired=self.host(config,calls,'prepare')['action_id'];self.decide(expired)
        with self.store.connection() as connection:connection.execute(sql.SQL("UPDATE {}.approvals SET created_at=clock_timestamp()-INTERVAL '301 seconds',expires_at=clock_timestamp()-INTERVAL '1 second' WHERE action_id=%s").format(sql.Identifier(self.schema)),[expired])
        self.host(config,calls,'resume',1,action=expired);self.assertEqual(self.count(calls),2)
        changed=self.host(config,calls,'prepare')['action_id'];self.decide(changed)
        original=config.read_text();doc=json.loads(original);doc['tools'][0]['tool_revision']='write-v2';config.write_text(json.dumps(doc))
        self.host(config,calls,'resume',1,action=changed);self.assertEqual(self.count(calls),2)
        config.write_text(original);self.host(config,calls,'resume',action=changed);self.assertEqual(self.count(calls),3)

    def test_ac2603_committed_completion_ack_loss_is_unknown_and_never_reexecutes(self):
        path=write_review_application(self.folder);counter=self.folder/'calls.jsonl'
        action=self.host(path,counter,'prepare')['action_id'];self.decide(action);self.lose_complete_ack=True
        result=self.host(path,counter,'resume',4,action=action);self.assertEqual(result['confirmation'],'unknown')
        self.host(path,counter,'resume',1,action=action);self.assertEqual(self.count(counter),1);self.assertEqual(self.record(action)['execution_state'],'completed')
        config=load_application(path);calls=[]
        connection=client(self.live.endpoint);send=connection._send
        def lose(path,payload,**kwargs):
            result=send(path,payload,**kwargs)
            if path.endswith('/complete'):raise ApprovalUnavailable()
            return result
        connection._send=lose
        with Application(config,subject='demo-agent') as app:
            governed=app.reviewed_tool(lambda record=1:calls.append(record),name='write',client=connection,disclose_arguments=True)
            ticket=governed.prepare({},summary='Synthetic');self.decide(ticket['action_id'])
            self.assertEqual(governed.resume(ticket['action_id'],{},summary='Synthetic').confirmation,'unknown')
            self.assertEqual(self.record(ticket['action_id'])['execution_state'],'completed')
            with self.assertRaises(ApprovalUnavailable):governed.resume(ticket['action_id'],{},summary='Synthetic')
        from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
        async def run_async():
            async with AsyncReviewedClient(self.live.endpoint,token='synthetic-producer',execution_token='synthetic-executor',binding_key=b'synthetic-reviewed-binding-key-11') as transport:
                original=transport._send_async
                async def lost(path,payload,**kwargs):
                    result=await original(path,payload,**kwargs)
                    if path.endswith('/complete'):raise ApprovalUnavailable()
                    return result
                transport._send_async=lost
                with Application(config,subject='demo-agent') as app:
                    async def write(record=1):calls.append(record)
                    governed=app.reviewed_tool(write,client=transport,disclose_arguments=True)
                    ticket=await governed.prepare({},summary='Synthetic');self.decide(ticket['action_id'])
                    self.assertEqual((await governed.resume(ticket['action_id'],{},summary='Synthetic')).confirmation,'unknown')
                    self.assertEqual(self.record(ticket['action_id'])['execution_state'],'completed')
                    with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic')
        asyncio.run(run_async());self.assertEqual(calls,[1,1])
