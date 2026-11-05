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
from tests.fixtures.configured_graph import write_graph_application
from tests.fixtures.application_config import ROOT
from tests.fixtures.live_server import LiveServer

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class ConfiguredGraphPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_configured_graph_'+uuid.uuid4().hex;self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        app=create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor')
        self.lose_complete_ack=False
        @app.middleware('http')
        async def fault(request,call_next):
            response=await call_next(request)
            if self.lose_complete_ack and request.url.path.endswith('/complete') and response.status_code==200:
                self.lose_complete_ack=False;return JSONResponse({'error':'synthetic acknowledgement unavailable'},503)
            return response
        self.live=LiveServer(app).start();self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
    def tearDown(self):
        self.live.close();self.tmp.cleanup()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def request(self,path,*,token='synthetic-reviewer',payload=None):
        body=None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(self.live.endpoint+path,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=10) as response:return json.load(response)
    def record(self,action):return next(r for r in self.request('/api/v1/reviewed-actions')['items'] if r['action_id']==action)
    def decide(self,action,decision='approved'):
        record=self.record(action)
        return self.request('/api/v1/reviewed-actions/'+action+'/decision',payload=dict(decision=decision,review_digest=record['review_digest']))
    def cli(self,code,*args,credentials=True):
        environment={**os.environ,'PYTHONIOENCODING':'utf-8','AEGIS_API_TOKEN':'synthetic-trace',
            'AEGIS_APPROVAL_REQUEST_TOKEN':'synthetic-producer','AEGIS_APPROVAL_EXECUTION_TOKEN':'synthetic-executor',
            'AEGIS_APPROVAL_BINDING_KEY':b'synthetic-reviewed-binding-key-11'.hex()}
        environment.pop('AEGIS_APPROVAL_REVIEW_TOKEN',None)
        if not credentials:
            for key in ('AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN','AEGIS_APPROVAL_BINDING_KEY','AEGIS_API_TOKEN'):environment.pop(key,None)
        result=subprocess.run([sys.executable,*args],cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=40)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr)
        self.assertNotIn('synthetic-configured-write',result.stdout);return json.loads(result.stdout)
    def host(self,config,state,command,code=0,*,asynchronous=False,scenario='success'):
        return self.cli(code,'examples/configured-graph/agent.py',command,'--config',str(config),'--state',str(state),
            '--endpoint',self.live.endpoint if command!='status' else 'http://127.0.0.1:9',
            *(['--async'] if asynchronous else []),*(['--scenario',scenario] if command=='start' else []),credentials=command!='status')
    def count(self,state):
        path=state/'tool-calls.jsonl';return len(path.read_text().splitlines()) if path.exists() else 0

    def test_ac2703_sync_async_durable_approval_tamper_reject_trace_and_export(self):
        approved=[]
        for asynchronous in (False,True):
            folder=self.folder/str(asynchronous);config=write_graph_application(folder,endpoint=self.live.endpoint+'/v1/traces');state=folder/'state'
            action=self.host(config,state,'start',asynchronous=asynchronous)['action_id'];approved.append(action)
            ticket=state/'ticket.json';original=ticket.read_text()
            self.assertEqual(self.record(action)['review_arguments']['arguments']['record_id'],9223372036854775807)
            before=self.host(config,state,'status',asynchronous=asynchronous);self.assertTrue(before['pending']);self.assertEqual(self.count(state),0)
            self.host(config,state,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(state),0)
            self.decide(action)
            changed=json.loads(original);changed['arguments']['value']='tampered';ticket.write_text(json.dumps(changed))
            self.host(config,state,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(state),0);ticket.write_text(original)
            result=self.host(config,state,'resume',asynchronous=asynchronous);self.assertEqual(result['continuation'],'resumed')
            after=self.host(config,state,'status',asynchronous=asynchronous);self.assertTrue(after['completed']);self.assertFalse(after['pending'])
            self.assertNotEqual(before['checkpoint_id'],after['checkpoint_id']);self.assertEqual(self.count(state),1)
            self.host(config,state,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(state),1)
            rejected=folder/'rejected';other=self.host(config,rejected,'start',asynchronous=asynchronous)['action_id'];self.decide(other,'rejected')
            self.host(config,rejected,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(rejected),0)
        with self.assertRaises(HTTPError) as denied:self.request('/api/v1/reviewed-actions',token='synthetic-trace')
        self.assertEqual(denied.exception.code,401)
        events=self.request('/api/v1/security-events',token='synthetic-trace');self.assertEqual(events['total'],2)
        self.assertEqual({e['action_id'] for e in events['items']},set(approved))
        for event in events['items']:
            detail=self.request('/api/v1/traces/'+event['trace_id'],token='synthetic-trace')
            span=next(s for s in detail['spans'] if s['span_id']==event['span_id']);self.assertIsNotNone(span['parent_span_id'])
            self.assertNotIn('synthetic-configured-write',str(detail));self.assertNotIn('review_arguments',str(detail));self.assertNotIn('record_id',str(span['attributes']))
        bundle=self.folder/'bundle';self.assertEqual(self.cli(0,'scripts/security_export.py','export','--base-url',self.live.endpoint,'--output',str(bundle))['count'],2)
        self.live.close();self.assertEqual(self.cli(0,'scripts/security_export.py','verify',str(bundle))['count'],2)

    def test_ac2703_failure_cancel_and_revision_mismatch_never_repeat_or_continue(self):
        config=write_graph_application(self.folder)
        for asynchronous,scenario,exit_code,server_state in ((False,'failure',2,'failed'),(True,'cancel',3,'claimed')):
            state=self.folder/scenario;action=self.host(config,state,'start',asynchronous=asynchronous,scenario=scenario)['action_id'];self.decide(action)
            self.host(config,state,'resume',exit_code,asynchronous=asynchronous);self.assertEqual(self.count(state),1)
            self.assertTrue(self.host(config,state,'status',asynchronous=asynchronous)['pending'])
            self.host(config,state,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(state),1)
            self.assertEqual(self.record(action)['execution_state'],server_state)
        state=self.folder/'revision';action=self.host(config,state,'start')['action_id'];self.decide(action);original=config.read_text()
        doc=json.loads(original);doc['tools'][0]['graph']['revision']='graph-v2';config.write_text(json.dumps(doc))
        self.host(config,state,'resume',1);self.assertEqual(self.count(state),0);self.assertEqual(self.record(action)['execution_state'],'available')
        config.write_text(original);self.host(config,state,'resume');self.assertEqual(self.count(state),1)

    def test_ac2703_sync_async_committed_completion_ack_loss_keeps_graph_paused(self):
        for asynchronous in (False,True):
            folder=self.folder/str(asynchronous);config=write_graph_application(folder);state=folder/'state'
            action=self.host(config,state,'start',asynchronous=asynchronous)['action_id'];self.decide(action);self.lose_complete_ack=True
            result=self.host(config,state,'resume',4,asynchronous=asynchronous)
            self.assertEqual((result['confirmation'],result['continuation']),('unknown','not_resumed'))
            self.assertEqual(self.record(action)['execution_state'],'completed');self.assertEqual(self.count(state),1)
            self.assertTrue(self.host(config,state,'status',asynchronous=asynchronous)['pending'])
            self.host(config,state,'resume',1,asynchronous=asynchronous);self.assertEqual(self.count(state),1)
