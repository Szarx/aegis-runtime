"""Real PostgreSQL schema1 upgrade and model metadata persistence."""

import concurrent.futures
from importlib.resources import files
import os
import unittest
import uuid

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
import aegis
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from aegis_collector.api import create_app
from aegis_collector.ingestion.otlp import decode
from aegis_collector.storage import PostgresSpanStore, StorageError
from tests.fixtures.llm import llm_request
from tests.fixtures.otlp import request_for

DATABASE = os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE, 'set AEGIS_TEST_DATABASE_URL to a dedicated test database')
class LLMPostgres(unittest.TestCase):
    def setUp(self):
        self.schema = 'test_llm_' + uuid.uuid4().hex
        self.store = PostgresSpanStore(DATABASE, self.schema)
    def tearDown(self):
        aegis.shutdown()
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.schema)))

    def legacy(self):
        script = files('aegis_collector.storage').joinpath('migrations/001_initial.sql').read_text()
        with self.store.connection() as connection:
            connection.execute(sql.SQL(script).format(schema=sql.Identifier(self.schema)))
            connection.execute(sql.SQL('INSERT INTO {}.schema_version VALUES (1)').format(sql.Identifier(self.schema)))
        self.store.insert(decode(request_for().SerializeToString())[0])

    def test_ac406_upgrade_preserves_native_and_adds_typed_model_span(self):
        self.legacy()
        with self.assertRaises(StorageError): self.store.ping()
        self.store.migrate(); self.store.migrate()
        self.store.ping()
        records, _ = decode(llm_request().SerializeToString())
        self.assertEqual(self.store.insert(records), 1)
        self.assertEqual(self.store.insert(records), 0)
        with TestClient(create_app(self.store)) as client:
            detail = client.get('/api/v1/traces/' + f'{1:032x}').json()
        self.assertEqual(detail['trace']['span_count'], 2)
        model = next(span for span in detail['spans'] if span['operation'] == 'chat')
        self.assertEqual(model['attributes']['gen_ai.usage.input_tokens'], 7)
        self.assertEqual(model['attributes']['gen_ai.usage.output_tokens'], 0)
        self.assertIs(type(model['attributes']['gen_ai.usage.output_tokens']), int)

    def test_ac406_unknown_migration_rolls_back_and_concurrent_upgrade_is_safe(self):
        self.legacy()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.store.migrate(), range(3)))
        with self.store.connection() as connection:
            versions = connection.execute(sql.SQL('SELECT version FROM {}.schema_version ORDER BY version').format(sql.Identifier(self.schema))).fetchall()
            self.assertEqual([row['version'] for row in versions], [1, 2, 3, 4])
            connection.execute(sql.SQL('INSERT INTO {}.schema_version VALUES (99)').format(sql.Identifier(self.schema)))
        with self.assertRaises(StorageError): self.store.migrate()
        self.assertEqual(self.store.list_traces()['total'], 1)

    def test_ac407_official_sdk_fixture_otlp_encoding_database_and_query(self):
        from aegis.openai import AegisOpenAI
        from examples.openai.offline import Fixture, PRIVATE_TEXT
        from examples.openai.agent import run_agent
        self.store.migrate()
        exporter = InMemorySpanExporter()
        aegis.init('integration-openai', exporter=exporter)
        with AegisOpenAI(api_key='offline-key', http_client=Fixture().http_client(), max_retries=0) as client:
            self.assertEqual(run_agent(client)['status'], 'shipped')
        self.assertTrue(aegis.flush())
        payload = encode_spans(exporter.get_finished_spans()).SerializeToString()
        with TestClient(create_app(self.store)) as client:
            response = client.post('/v1/traces', content=payload, headers={'content-type':'application/x-protobuf'})
            self.assertEqual(response.status_code, 200)
            listing = client.get('/api/v1/traces').json()
            detail = client.get('/api/v1/traces/' + listing['items'][0]['trace_id']).json()
        self.assertEqual(detail['trace']['span_count'], 3)
        model = next(span for span in detail['spans'] if span['operation'] == 'chat')
        root = next(span for span in detail['spans'] if span['operation'] == 'invoke_agent')
        self.assertEqual(model['parent_span_id'], root['span_id'])
        self.assertEqual(model['attributes']['gen_ai.usage.output_tokens'], 3)
        self.assertNotIn(PRIVATE_TEXT, str(detail))
        self.assertNotIn('offline-key', str(detail))

    def test_ac503_deepseek_official_sdk_to_database_with_provider_and_tokens(self):
        from aegis.deepseek import AegisDeepSeek
        from examples.deepseek.offline import Fixture, PRIVATE_TEXT
        from examples.deepseek.agent import run_tool_agent
        self.store.migrate()
        exporter = InMemorySpanExporter()
        aegis.init('integration-deepseek',exporter=exporter)
        with AegisDeepSeek(api_key='synthetic-secret',http_client=Fixture().http_client(),max_retries=0) as client:
            self.assertEqual(run_tool_agent(client,model='offline-deepseek')['tool_calls'],1)
        self.assertTrue(aegis.flush())
        payload = encode_spans(exporter.get_finished_spans()).SerializeToString()
        with TestClient(create_app(self.store)) as client:
            self.assertEqual(client.post('/v1/traces',content=payload,headers={'content-type':'application/x-protobuf'}).status_code,200)
            listing = client.get('/api/v1/traces').json()
            detail = client.get('/api/v1/traces/' + listing['items'][0]['trace_id']).json()
        self.assertEqual(detail['trace']['span_count'],4)
        models = [span for span in detail['spans'] if span['operation']=='chat']
        self.assertEqual(len(models),2)
        self.assertTrue(all(span['attributes']['gen_ai.provider.name']=='deepseek' for span in models))
        self.assertTrue(all(span['attributes']['gen_ai.usage.input_tokens']==7 for span in models))
        self.assertNotIn(PRIVATE_TEXT,str(detail))
        self.assertNotIn('synthetic-secret',str(detail))

    def test_ac605_real_langgraph_toolnode_to_database_preserves_parent_and_privacy(self):
        from openai import OpenAI
        from examples.deepseek.offline import Fixture,PRIVATE_TEXT
        from examples.langgraph.agent import build_agent,initial_state
        self.store.migrate()
        exporter=InMemorySpanExporter()
        aegis.init('integration-langgraph',exporter=exporter)
        with OpenAI(api_key='offline-framework-key',http_client=Fixture().http_client(),max_retries=0) as client:
            graph,counts=build_agent(client,traced=True)
            graph.invoke(initial_state())
        self.assertEqual(counts,{'model_calls':2,'tool_calls':1})
        self.assertTrue(aegis.flush())
        payload=encode_spans(exporter.get_finished_spans()).SerializeToString()
        with TestClient(create_app(self.store)) as client:
            self.assertEqual(client.post('/v1/traces',content=payload,headers={'content-type':'application/x-protobuf'}).status_code,200)
            listing=client.get('/api/v1/traces').json()
            detail=client.get('/api/v1/traces/'+listing['items'][0]['trace_id']).json()
        self.assertEqual(detail['trace']['span_count'],4)
        root=next(s for s in detail['spans'] if s['operation']=='invoke_agent')
        self.assertTrue(all(s['parent_span_id']==root['span_id'] for s in detail['spans'] if s is not root))
        self.assertEqual(len([s for s in detail['spans'] if s['operation']=='chat']),2)
        for value in (PRIVATE_TEXT,'offline-framework-key','Look up synthetic order'):
            self.assertNotIn(value,str(detail))
