import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.request import Request, urlopen
import uuid
import psycopg
from psycopg import sql
import aegis
from aegis_policy import Policy, Rule
from aegis_runtime import Runtime, ActionDenied
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from opentelemetry import trace
from tests.fixtures.live_server import LiveServer

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')
ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(DATABASE, 'dedicated PostgreSQL required')
class PlatformDiagnosticsPostgres(unittest.TestCase):
    def test_ac4204_real_sdk_governance_readonly_auth_missing_and_stopped_service(self):
        schema='test_platform_check_'+uuid.uuid4().hex
        store=PostgresSpanStore(DATABASE,schema);store.migrate()
        live=LiveServer(create_app(store,api_token='synthetic-platform-token')).start()
        def cli(*args, token='synthetic-platform-token', code=0):
            result=subprocess.run([sys.executable,'-S','scripts/platform_check.py','--base-url',live.endpoint,'--timeout-seconds','1',*args],cwd=ROOT,
                env={**os.environ,'AEGIS_API_TOKEN':token},capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,code,result.stdout+result.stderr)
            self.assertNotIn(token,result.stdout);return json.loads(result.stdout)
        def get(path):
            with urlopen(Request(live.endpoint+path,headers={'Authorization':'Bearer synthetic-platform-token'}),timeout=3) as response:return json.load(response)
        try:
            self.assertEqual(cli()['trace_total'],0)
            calls=[];trace_id=None
            sdk=aegis.init('synthetic-platform-probe',endpoint=live.endpoint+'/v1/traces',headers={'Authorization':'Bearer synthetic-platform-token'})
            try:
                allow=Runtime(Policy('probe-v1',(Rule('permit','allow',('probe',),('check',),('probe.read',)),)),subject='probe')
                deny=Runtime(Policy('probe-v1',(Rule('refuse','deny',('probe',),('check',),('probe.read',)),)),subject='probe')
                @aegis.observe(name='platform-probe')
                def agent():
                    nonlocal trace_id
                    trace_id=format(trace.get_current_span().get_span_context().trace_id,'032x')
                    allow.tool(lambda: calls.append('allowed'),name='check',permission='probe.read')()
                    try:deny.tool(lambda: calls.append('denied'),name='check',permission='probe.read')()
                    except ActionDenied:pass
                agent();self.assertTrue(sdk.flush())
            finally:self.assertTrue(sdk.shutdown())
            self.assertEqual(calls,['allowed']);before=get('/api/v1/traces?limit=1')['total']
            before_events=get('/api/v1/security-events')['total']
            report=cli('--trace-id',trace_id)
            self.assertEqual((report['span_count'],report['security_total'],report['missing_parent_count']),(3,2,0))
            self.assertEqual(get('/api/v1/traces?limit=1')['total'],before)
            self.assertEqual(get('/api/v1/security-events')['total'],before_events)
            denied=cli(token='synthetic-wrong-token',code=1)
            self.assertEqual(denied['steps'][-1],dict(stage='trace_query',status='failed',category='unauthorized'))
            missing=cli('--trace-id','f'*32,code=1);self.assertEqual(missing['steps'][-1]['category'],'not_found')
            live.close()
            stopped=cli(code=1);self.assertEqual(stopped['steps'][-1]['stage'],'live')
            self.assertIn(stopped['steps'][-1]['category'],('network_unavailable','network_timeout'))
        finally:
            try:live.close()
            finally:
                with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
