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
from tests.fixtures.application_config import ROOT,write_application
from tests.fixtures.live_server import LiveServer

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class ConfiguredApplicationPostgres(unittest.TestCase):
    def test_ac2504_real_configured_eight_profiles_query_export_and_offline_replay(self):
        schema='test_application_'+uuid.uuid4().hex;store=PostgresSpanStore(DATABASE,schema);store.migrate()
        live=LiveServer(create_app(store,api_token='synthetic-onboarding')).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory);config=write_application(folder,endpoint=live.endpoint+'/v1/traces')
                def cli(code,*args):
                    result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'SYNTHETIC_TRACE_TOKEN':'synthetic-onboarding','AEGIS_API_TOKEN':'synthetic-onboarding',
                        'PYTHONIOENCODING':'utf-8','LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'},capture_output=True,text=True,encoding='utf-8',timeout=30)
                    self.assertEqual(result.returncode,code,result.stdout+result.stderr);return json.loads(result.stdout)
                for framework in ('native','langgraph'):
                    for asynchronous in (False,True):
                        for subject in ('reader','blocked'):
                            report=cli(0,'examples/configured-agent/run.py','--config',str(config),'--framework',framework,'--subject',subject,*(['--async'] if asynchronous else []))
                            self.assertEqual(report['business_calls'],int(subject=='reader'));self.assertEqual(report['application']['diagnostics']['exported_spans'],2)
                def get(path):
                    with urlopen(Request(live.endpoint+path,headers={'Authorization':'Bearer synthetic-onboarding'}),timeout=10) as response:return json.load(response)
                events=get('/api/v1/security-events');self.assertEqual(events['total'],8);self.assertEqual(get('/api/v1/traces')['total'],8)
                self.assertEqual(get('/api/v1/security-events?effect=deny')['total'],4)
                for event in events['items']:
                    detail=get('/api/v1/traces/'+event['trace_id']);self.assertEqual(len(detail['spans']),2)
                    self.assertTrue(any(s['span_id']==event['span_id'] for s in detail['spans']))
                bundle=folder/'export';self.assertEqual(cli(0,'scripts/security_export.py','export','--base-url',live.endpoint,'--output',str(bundle))['count'],8)
                live.close()
                same=cli(0,'scripts/replay_security.py',str(bundle),'--policy',str(folder/'policy.json'),'--output',str(folder/'same.json'))
                self.assertEqual(same['counts']['unchanged'],8)
                candidate=json.loads((folder/'policy.json').read_text());candidate['rules']=[dict(id='allow-read',effect='allow',subjects=['reader','blocked'],tools=['lookup_order'],permissions=['orders.read'])]
                changed=folder/'candidate.json';changed.write_text(json.dumps(candidate))
                replay=cli(1,'scripts/replay_security.py',str(bundle),'--policy',str(changed),'--output',str(folder/'changed.json'))
                self.assertEqual(replay['counts'],dict(widened=4,narrowed=0,decision_changed=0,unchanged=4))
        finally:
            live.close()
            with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
