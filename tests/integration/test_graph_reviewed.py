import concurrent.futures
import os
import threading
import unittest
import urllib.request
import json
import uuid

import aegis
import psycopg
from psycopg import sql
from langgraph.checkpoint.memory import InMemorySaver
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans

from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import GraphBindingError
from tests.fixtures.live_server import LiveServer
from tests.fixtures.reviewed import client
from tests.fixtures.graph_reviewed import gate,build,config,initial

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class GraphReviewedPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_graph_reviewed_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        self.host=LiveServer(create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',
                                       approval_review_token='synthetic-review',approval_execution_token='synthetic-executor')).start()

    def tearDown(self):
        aegis.shutdown();self.host.close()
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def http(self,path,body=None,*,token='synthetic-review',content_type='application/json'):
        raw=body if type(body) is bytes else None if body is None else json.dumps(body).encode()
        request=urllib.request.Request(self.host.endpoint+path,data=raw,headers={'Authorization':'Bearer '+token,'Content-Type':content_type})
        with urllib.request.urlopen(request,timeout=5) as response:
            raw=response.read()
            return json.loads(raw) if content_type=='application/json' else raw

    def prepare(self,governed,graph,cfg):
        graph.invoke(initial(),cfg)
        ticket=governed.prepare(graph,cfg,summary='Synthetic graph HTTP')
        row=next(r for r in self.http('/api/v1/reviewed-actions')['items'] if r['action_id']==ticket['action_id'])
        self.http('/api/v1/reviewed-actions/'+ticket['action_id']+'/decision',{'decision':'approved','review_digest':row['review_digest']})
        return ticket

    def test_ac1305_rebuilt_host_and_concurrent_claims_execute_once_with_otlp(self):
        calls=[];value=object();exporter=InMemorySpanExporter();aegis.init('graph-reviewed-http',exporter=exporter)
        def write(record='private-graph-argument'):calls.append(record);return value
        saver=InMemorySaver();governed=gate(write,client(self.host.endpoint));graph=build(governed,saver);cfg=config()
        ticket=self.prepare(governed,graph,cfg)
        fresh=gate(write,client(self.host.endpoint));rebuilt=build(fresh,saver)
        self.assertEqual(graph.get_state(cfg).config,rebuilt.get_state(cfg).config)
        @aegis.observe(name='rebuilt-graph-host')
        def host():return fresh.resume(rebuilt,cfg,json.loads(json.dumps(ticket)))
        result=host();self.assertIs(result.value,value);self.assertEqual(result.continuation,'resumed')
        with self.assertRaises(GraphBindingError):fresh.resume(rebuilt,cfg,ticket)
        self.assertEqual(calls,['private-graph-argument'])
        concurrent_gate=gate(write,client(self.host.endpoint));concurrent_graph=build(concurrent_gate);cfg2=config('concurrent')
        ticket2=self.prepare(concurrent_gate,concurrent_graph,cfg2)
        barrier=threading.Barrier(2)
        def worker():
            barrier.wait(timeout=5)
            try:return concurrent_gate.resume(concurrent_graph,cfg2,ticket2).continuation
            except (ApprovalUnavailable,GraphBindingError):return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker) for _ in range(2)]
            results=[future.result(timeout=10) for future in futures]
        self.assertCountEqual(results,['resumed','blocked']);self.assertEqual(len(calls),2)
        self.assertEqual({row['execution_state'] for row in self.store.list_reviewed()['items']},{'completed'})
        self.assertTrue(aegis.flush());spans=exporter.get_finished_spans()
        self.assertEqual(sum(s.attributes['gen_ai.operation.name']=='execute_tool' for s in spans),2)
        self.assertNotIn('private-',repr([dict(s.attributes) for s in spans]))
        self.http('/v1/traces',encode_spans(spans).SerializeToString(),token='synthetic-trace',content_type='application/x-protobuf')
        listing=self.http('/api/v1/traces',token='synthetic-trace')
        self.assertEqual(listing['total'],2)
        for row in listing['items']:
            self.assertNotIn('private-',str(self.http('/api/v1/traces/'+row['trace_id'],token='synthetic-trace')))

    def test_ac1305_committed_response_losses_and_checkpoint_edits_never_mint_retries(self):
        calls=[]
        for phase in ('claim','complete','business'):
            connection=client(self.host.endpoint)
            def write(record=1):
                calls.append(phase)
                if phase=='business':raise original
                return record
            original=ValueError('private-graph-error')
            governed=gate(write,connection);graph=build(governed);cfg=config(phase)
            ticket=self.prepare(governed,graph,cfg)
            native=connection._send
            def discard(path,payload,**kwargs):
                result=native(path,payload,**kwargs)
                if path.endswith('/'+phase):raise ApprovalUnavailable()
                return result
            connection._send=discard
            if phase=='claim':
                with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
            elif phase=='complete':
                result=governed.resume(graph,cfg,ticket)
                self.assertEqual((result.confirmation,result.continuation),('unknown','not_resumed'))
            else:
                with self.assertRaises(ValueError) as context:governed.resume(graph,cfg,ticket)
                self.assertIs(context.exception,original)
            with self.assertRaises(ApprovalUnavailable):governed.resume(graph,cfg,ticket)
            graph.update_state(cfg,initial());graph.invoke(None,cfg)
            self.assertEqual(governed._capture(graph,cfg)[2],ticket['action_id'])
            with self.assertRaises(ApprovalUnavailable):governed.prepare(graph,cfg,summary='Synthetic graph HTTP')
        self.assertEqual(calls,['complete','business'])
        fresh=PostgresSpanStore(DATABASE,self.schema);fresh.migrate()
        self.assertEqual({row['execution_state'] for row in fresh.list_reviewed()['items']},{'claimed','completed','failed'})
