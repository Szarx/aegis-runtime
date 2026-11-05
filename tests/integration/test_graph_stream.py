import os
import unittest
import uuid

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.graph_stream import graph_request
from tests.fixtures.otlp import request_for

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'set AEGIS_TEST_DATABASE_URL to dedicated PostgreSQL')
class GraphStreamPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_graph_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema)
        self.store.migrate()
    def tearDown(self):
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.schema)))

    def test_ac705_live_ingestion_summary_lifecycle_priority_and_legacy_null(self):
        with TestClient(create_app(self.store)) as client:
            for i,outcome in enumerate(('completed','closed','cancelled','error'),1):
                request=graph_request(trace=i,outcome=outcome)
                response=client.post('/v1/traces',content=request.SerializeToString(),headers={'content-type':'application/x-protobuf'})
                self.assertEqual(response.status_code,200)
                detail=client.get('/api/v1/traces/'+f'{i:032x}').json()
                self.assertEqual(detail['trace']['graph_outcome'],outcome)
                self.assertEqual(detail['trace']['status'],'ERROR' if outcome in ('error','cancelled') else 'UNSET')
            native=request_for(trace=5)
            client.post('/v1/traces',content=native.SerializeToString(),headers={'content-type':'application/x-protobuf'})
            self.assertIsNone(client.get('/api/v1/traces/'+f'{5:032x}').json()['trace']['graph_outcome'])
            # Derived lifecycle uses all graph spans, independent of insertion order.
            for span,outcome in [(2,'closed'),(3,'cancelled'),(4,'error')]:
                request=graph_request(trace=1,span=span,outcome=outcome)
                client.post('/v1/traces',content=request.SerializeToString(),headers={'content-type':'application/x-protobuf'})
                self.assertEqual(client.get('/api/v1/traces/'+f'{1:032x}').json()['trace']['graph_outcome'],outcome)
            items=client.get('/api/v1/traces').json()['items']
            self.assertEqual(len(items),5)
            no_error=client.get('/api/v1/traces?status=UNSET').json()['items']
            self.assertEqual({item['graph_outcome'] for item in no_error},{None,'closed'})
