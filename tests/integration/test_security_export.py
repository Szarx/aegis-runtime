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
from tests.fixtures.governance import governance_request
from tests.fixtures.otlp import combine

ROOT=Path(__file__).resolve().parents[2];DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class SecurityExportPostgres(unittest.TestCase):
    def test_ac2103_real_http_multi_page_filtered_export_and_offline_cli_verify(self):
        schema='test_export_'+uuid.uuid4().hex;store=PostgresSpanStore(DATABASE,schema);store.migrate()
        live=LiveServer(create_app(store,api_token='synthetic-export')).start()
        try:
            request=combine(*[governance_request(trace=i,reason='identity_missing' if i==101 else 'explicit_deny') for i in range(1,102)])
            with urlopen(Request(live.endpoint+'/v1/traces',data=request.SerializeToString(),headers={'Authorization':'Bearer synthetic-export','Content-Type':'application/x-protobuf'}),timeout=10) as response:self.assertEqual(response.status,200)
            with tempfile.TemporaryDirectory() as directory:
                def cli(*args,token='synthetic-export'):
                    result=subprocess.run([sys.executable,'scripts/security_export.py',*args],cwd=ROOT,env={**os.environ,'AEGIS_API_TOKEN':token},capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
                output=Path(directory)/'all'
                self.assertEqual(cli('export','--base-url',live.endpoint,'--output',str(output))['count'],101)
                filtered=Path(directory)/'reader'
                self.assertEqual(cli('export','--base-url',live.endpoint,'--subject','reader','--output',str(filtered))['count'],100)
                manifest=json.loads((output/'manifest.json').read_text());self.assertNotIn('synthetic-export',str(manifest))
                live.close()
                self.assertEqual(cli('verify',str(output),token='')['count'],101)
                self.assertEqual(cli('verify',str(filtered),token='')['count'],100)
        finally:
            live.close()
            with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
