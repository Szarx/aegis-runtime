import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from urllib.request import Request,urlopen
import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.live_server import LiveServer
from tests.fixtures.application_config import ROOT

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class DashboardDemoPostgres(unittest.TestCase):
    def test_ac3502_real_cli_populates_traces_models_events_and_pending_review_only(self):
        schema='test_dashboard_demo_'+uuid.uuid4().hex;store=PostgresSpanStore(DATABASE,schema);store.migrate()
        live=LiveServer(create_app(store,api_token='synthetic-demo-trace',approval_request_token='synthetic-demo-producer',approval_review_token='synthetic-demo-reviewer',approval_execution_token='synthetic-demo-executor')).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                environment={**os.environ,'PYTHONIOENCODING':'utf-8','AEGIS_API_TOKEN':'synthetic-demo-trace','AEGIS_APPROVAL_REQUEST_TOKEN':'synthetic-demo-producer','AEGIS_APPROVAL_EXECUTION_TOKEN':'synthetic-demo-executor'}
                environment.pop('AEGIS_APPROVAL_REVIEW_TOKEN',None)
                result=subprocess.run([sys.executable,'scripts/dashboard_demo.py','--base-url',live.endpoint,'--attempts','5','--with-approvals','--output',str(Path(directory)/'demo')],cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads(result.stdout)
                self.assertEqual(report['status'],'passed');self.assertEqual(len(report['action_ids']),2)
                for value in ('synthetic-demo-trace','synthetic-demo-producer','synthetic-demo-executor','synthetic-demo-value','binding_key'):self.assertNotIn(value,result.stdout)
                def get(path,token='synthetic-demo-trace'):
                    with urlopen(Request(live.endpoint+path,headers={'Authorization':'Bearer '+token}),timeout=10) as response:return json.load(response)
                traces=get('/api/v1/traces');self.assertEqual(traces['total'],6);self.assertEqual(sum(t['span_count'] for t in traces['items']),14)
                self.assertEqual(get('/api/v1/security-events')['total'],6)
                model_trace=next(t for t in traces['items'] if t['span_count']==4);detail=get('/api/v1/traces/'+model_trace['trace_id'])
                models=[s for s in detail['spans'] if s['operation']=='chat'];self.assertEqual(len(models),2)
                self.assertEqual(sum(s['attributes']['gen_ai.usage.input_tokens'] for s in models),14)
                actions=get('/api/v1/reviewed-actions','synthetic-demo-reviewer');self.assertEqual(actions['total'],2)
                for action in actions['items']:
                    self.assertEqual(action['status'],'pending');self.assertEqual(action['execution_state'],'available')
                    self.assertEqual(action['review_arguments']['record_id'],9223372036854775807)
        finally:
            live.close()
            with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
