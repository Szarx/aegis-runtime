import os
import unittest
import uuid
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.otlp import request_for,combine
from tests.fixtures.governance import governance_request

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'set AEGIS_TEST_DATABASE_URL to dedicated PostgreSQL')
class GovernancePostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_gov_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
    def tearDown(self):
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.schema)))
    def test_decisions_persist_deduplicate_and_preserve_legacy_query_shape(self):
        with TestClient(create_app(self.store)) as client:
            for trace,(effect,reason) in enumerate([('allow','explicit_allow'),('deny','explicit_deny'),('deny','no_match')],1):
                request=combine(request_for(trace=trace),governance_request(trace=trace,effect=effect,reason=reason))
                for _ in range(2):
                    response=client.post('/v1/traces',content=request.SerializeToString(),headers={'content-type':'application/x-protobuf'})
                    self.assertEqual(response.status_code,200)
                detail=client.get('/api/v1/traces/'+f'{trace:032x}').json()
                self.assertEqual(detail['trace']['span_count'],2)
                self.assertEqual(detail['trace']['status'],'UNSET' if effect=='allow' else 'ERROR')
                self.assertIsNone(detail['trace']['graph_outcome'])
                step=next(span for span in detail['spans'] if span['operation']=='execute_tool')
                self.assertEqual(step['attributes']['aegis.decision.reason'],reason)
                self.assertEqual(step['parent_span_id'],f'{1:016x}')
            self.assertEqual(client.get('/api/v1/traces?status=ERROR').json()['total'],2)
            self.assertEqual(client.get('/api/v1/traces?status=UNSET').json()['total'],1)
