import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.live_server import LiveServer

ROOT=Path(__file__).resolve().parents[2];DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class EventReplayPostgres(unittest.TestCase):
    def test_ac2403_real_sdk_otlp_database_export_then_offline_candidate_replay(self):
        schema='test_event_replay_'+uuid.uuid4().hex;store=PostgresSpanStore(DATABASE,schema);store.migrate()
        live=LiveServer(create_app(store,api_token='synthetic-replay')).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory);bundle=folder/'bundle'
                def cli(code,*args):
                    result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'AEGIS_API_TOKEN':'synthetic-replay','PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8',timeout=30)
                    self.assertEqual(result.returncode,code,result.stdout+result.stderr);return json.loads(result.stdout)
                seed=cli(0,'examples/security-events/agent.py','--endpoint',live.endpoint+'/v1/traces')
                self.assertEqual(seed['counters']['business_calls'],15);self.assertEqual(seed['diagnostics']['exported_spans'],50)
                self.assertEqual(cli(0,'scripts/security_export.py','export','--base-url',live.endpoint,'--output',str(bundle))['count'],25)
                live.close()
                report=folder/'allow.json'
                summary=cli(1,'scripts/replay_security.py',str(bundle),'--policy','examples/event-policy-replay/candidate.json','--output',str(report))
                self.assertEqual(summary['counts'],dict(widened=5,narrowed=0,decision_changed=0,unchanged=20));self.assertEqual(summary['revision_differences'],25)
                self.assertEqual(summary['recorded_outcomes'],dict(completed=5,denied=10,error=5,cancelled=5))
                closed=folder/'deny.json';closed.write_text(json.dumps(dict(schema_version='aegis.policy.v1',revision='demo-policy-v1',rules=[])))
                summary=cli(1,'scripts/replay_security.py',str(bundle),'--policy',str(closed),'--output',str(folder/'deny-report.json'))
                self.assertEqual(summary['counts'],dict(widened=0,narrowed=15,decision_changed=5,unchanged=5))
                data=json.loads(report.read_text());self.assertEqual(len({(r['event']['trace_id'],r['event']['span_id']) for r in data['events']}),25)
        finally:
            live.close()
            with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
