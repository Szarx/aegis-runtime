import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import TypedDict
import unittest
from unittest.mock import patch
import uuid
from urllib.request import Request,urlopen
import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_runtime.application import Application,load_application
from langgraph.graph import StateGraph,START,END
from tests.fixtures.application_config import ROOT
from tests.fixtures.managed_graph import write_managed_graph_application
from tests.fixtures.live_server import LiveServer

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class ManagedGraphPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_managed_graph_'+uuid.uuid4().hex;self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        self.live=LiveServer(create_app(self.store,api_token='synthetic-managed-graph')).start()
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.config=write_managed_graph_application(self.folder,endpoint=self.live.endpoint+'/v1/traces')
    def tearDown(self):
        self.live.close();self.tmp.cleanup()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def cli(self,*args):
        result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**os.environ,'AEGIS_API_TOKEN':'synthetic-managed-graph','PYTHONIOENCODING':'utf-8'},
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)
    def get(self,path):
        with urlopen(Request(self.live.endpoint+path,headers={'Authorization':'Bearer synthetic-managed-graph'}),timeout=10) as response:return json.load(response)

    def test_ac2803_all_modes_allow_deny_handled_failure_early_close_tokens_and_export(self):
        profiles=[]
        for mode in ('invoke','ainvoke','stream','astream'):
            for subject in ('reader','blocked'):
                for fail in (False,True):
                    report=self.cli('examples/managed-graph/run.py','--config',str(self.config),'--mode',mode,'--subject',subject,'--model-delay-ms','50',*(['--fail-tool'] if fail else []))
                    self.assertEqual((report['model_calls'],report['business_calls']),(2,int(subject=='reader')));profiles.append(report)
        for mode in ('stream','astream'):
            for subject in ('reader','blocked'):
                report=self.cli('examples/managed-graph/run.py','--config',str(self.config),'--mode',mode,'--subject',subject,'--early-close','--model-delay-ms','50')
                self.assertEqual((report['model_calls'],report['business_calls']),(1,0));profiles.append(report)
        traces=self.get('/api/v1/traces?limit=100');self.assertEqual(traces['total'],20)
        self.assertEqual(sum(t['graph_outcome']=='completed' for t in traces['items']),8)
        self.assertEqual(sum(t['graph_outcome']=='closed' for t in traces['items']),4)
        events=self.get('/api/v1/security-events?limit=100');self.assertEqual(events['total'],16)
        self.assertEqual(sum(e['effect']=='deny' for e in events['items']),8)
        for summary in traces['items']:
            detail=self.get('/api/v1/traces/'+summary['trace_id']);self.assertEqual(detail['missing_parent_ids'],[])
            spans=detail['spans'];root=next(s for s in spans if s['operation']=='invoke_agent')
            models=[s for s in spans if s['operation']=='chat'];closed=summary['graph_outcome']=='closed'
            self.assertEqual(len(models),1 if closed else 2);self.assertEqual(len(spans),2 if closed else 4)
            self.assertGreater(summary['duration_ns'],0)
            for span in spans:
                # A tiny synthetic tool can start/end in the same Windows wall-clock tick.
                self.assertGreaterEqual(span['end_time_unix_nano']-span['start_time_unix_nano'],0)
                if span is not root:self.assertEqual(span['parent_span_id'],root['span_id'])
            self.assertEqual(sum(s['attributes']['gen_ai.usage.input_tokens'] for s in models),7*len(models))
            self.assertTrue(all(s['end_time_unix_nano']>s['start_time_unix_nano'] for s in models))
            self.assertEqual(sum(s['attributes']['gen_ai.usage.output_tokens'] for s in models),3*len(models))
            self.assertNotIn('synthetic-private-content',str(detail));self.assertNotIn('synthetic private business failure',str(detail));self.assertNotIn('demo-order',str(detail))
            for event in (e for e in events['items'] if e['trace_id']==summary['trace_id']):
                self.assertTrue(any(s['span_id']==event['span_id'] and s['operation']=='execute_tool' for s in spans))
        bundle=self.folder/'bundle';self.assertEqual(self.cli('scripts/security_export.py','export','--base-url',self.live.endpoint,'--output',str(bundle))['count'],16)
        self.live.close();self.assertEqual(self.cli('scripts/security_export.py','verify',str(bundle))['count'],16)

    def test_ac2803_unhandled_error_and_async_cancellation_reach_platform(self):
        class State(TypedDict):value:int
        error=ValueError('private-unhandled-error')
        def fail(state):raise error
        graph=StateGraph(State).add_node('step',fail).add_edge(START,'step').add_edge('step',END).compile()
        with patch.dict(os.environ,{'AEGIS_API_TOKEN':'synthetic-managed-graph'}):
            with Application(load_application(self.config),subject='reader') as app:
                with self.assertRaises(ValueError) as caught:list(app.graph(graph,name='error-graph').stream({'value':1}))
                self.assertIs(caught.exception,error);self.assertEqual(app.status()['active_calls'],0)
            async def run():
                started=asyncio.Event()
                async def wait(state):started.set();await asyncio.Event().wait()
                graph=StateGraph(State).add_node('step',wait).add_edge(START,'step').add_edge('step',END).compile()
                with Application(load_application(self.config),subject='reader') as app:
                    stream=app.graph(graph,name='cancelled-graph').astream({'value':1});task=asyncio.create_task(stream.__anext__())
                    await asyncio.wait_for(started.wait(),5);task.cancel()
                    with self.assertRaises(asyncio.CancelledError):await task
                    self.assertEqual(app.status()['active_calls'],0);await stream.aclose()
            asyncio.run(run())
        summaries=self.get('/api/v1/traces')['items'];self.assertEqual(len(summaries),2)
        self.assertEqual({s['graph_outcome'] for s in summaries},{'error','cancelled'})
        for summary in summaries:
            self.assertEqual(summary['status'],'ERROR');self.assertEqual(summary['span_count'],1)
            self.assertNotIn('private-unhandled-error',str(self.get('/api/v1/traces/'+summary['trace_id'])))
