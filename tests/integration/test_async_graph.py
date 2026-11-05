import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

import aiosqlite
import httpx
import psycopg
from psycopg import sql

from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.async_durable_graph import configure_async_reviewed_checkpointer
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from aegis_runtime.durable_graph import open_reviewed_checkpointer
from tests.fixtures.async_graph import gate,build,config,initial
from tests.fixtures.live_server import LiveServer

ROOT=Path(__file__).resolve().parents[2]
DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


class Host:
    def setUp(self):
        self.schema='test_async_graph_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        self.host=LiveServer(create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',
            approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor')).start()
        self.temporary=tempfile.TemporaryDirectory(prefix='aegis async processes ');self.directory=Path(self.temporary.name)

    def tearDown(self):
        self.host.close()
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.temporary.cleanup()

    def client(self, transport=None):
        return AsyncReviewedClient(self.host.endpoint,token='synthetic-producer',execution_token='synthetic-executor',
            binding_key=b'synthetic-async-graph-http-key!!!',transport=transport)

    async def approve(self, action_id):
        row=next(row for row in self.store.list_reviewed()['items'] if row['action_id']==action_id)
        async with httpx.AsyncClient(trust_env=False,timeout=3) as reviewer:
            response=await reviewer.post(self.host.endpoint+'/api/v1/reviewed-actions/'+action_id+'/decision',
                headers={'Authorization':'Bearer synthetic-reviewer'},json={'decision':'approved','review_digest':row['review_digest']})
            self.assertEqual(response.status_code,200)


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class AsyncGraphPostgres(Host,unittest.IsolatedAsyncioTestCase):
    async def test_ac1504_native_sqlite_http_committed_cancel_and_no_retry(self):
        results=[]
        for phase in ('success','claim','body','complete'):
            cfg=config('http-'+phase)
            path=self.directory/(phase+'.sqlite3')
            with open_reviewed_checkpointer(path,create=True):pass
            entered=asyncio.Event();calls=[];seen=[]
            async def hold():
                entered.set()
                try:await asyncio.Event().wait()
                except asyncio.CancelledError as error:seen.append(error);raise
            class HeldResponse(httpx.AsyncBaseTransport):
                def __init__(self):self.native=httpx.AsyncHTTPTransport(retries=0,trust_env=False)
                async def handle_async_request(self,request):
                    response=await self.native.handle_async_request(request)
                    if request.url.path.endswith('/'+phase) and response.status_code==200:
                        await response.aread()
                        try:await hold()
                        except BaseException:await response.aclose();raise
                    return response
                async def aclose(self):await self.native.aclose()
            async def write(value=9223372036854775807):
                calls.append(value)
                if phase=='body':await hold()
                return value
            async with self.client(HeldResponse()) as connection:
                async with aiosqlite.connect(path.as_uri()+'?mode=rw',uri=True) as database:
                    saver=await configure_async_reviewed_checkpointer(database)
                    governed=gate(write,connection);graph=build(governed,saver)
                    await graph.ainvoke(initial(),cfg,durability='sync')
                    ticket=await governed.prepare(graph,cfg,summary='Synthetic HTTP SQLite')
                await self.approve(ticket['action_id'])
                # New native connection, saver, gate and compiled graph.
                async with aiosqlite.connect(path.as_uri()+'?mode=rw',uri=True) as database:
                    worker=database._thread;saver=await configure_async_reviewed_checkpointer(database)
                    governed=gate(write,connection);graph=build(governed,saver)
                    if phase=='success':
                        result=await governed.resume(graph,cfg,ticket)
                        self.assertEqual((result.confirmation,result.continuation),('confirmed','resumed'))
                    else:
                        task=asyncio.create_task(governed.resume(graph,cfg,ticket))
                        await asyncio.wait_for(entered.wait(),3);task.cancel(phase)
                        with self.assertRaises(asyncio.CancelledError) as error:await task
                        self.assertIs(error.exception,seen[0])
                        with self.assertRaises(ApprovalUnavailable):await governed.resume(graph,cfg,ticket)
                    self.assertEqual(len(calls),0 if phase=='claim' else 1)
                    self.assertEqual(bool((await graph.aget_state(cfg)).interrupts),phase!='success')
                worker.join(timeout=2);self.assertFalse(worker.is_alive())
            row=next(row for row in self.store.list_reviewed()['items'] if row['action_id']==ticket['action_id'])
            self.assertEqual(row['execution_state'],'completed' if phase in ('success','complete') else 'claimed')
            results.append(dict(phase=phase,tool_calls=len(calls),execution_state=row['execution_state'],worker_closed=True))
        receipt=ROOT/'artifacts/async-graph/http-sqlite.json';receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class AsyncGraphProcesses(Host,unittest.TestCase):
    def test_ac1504_independent_async_start_resume_status_and_partial_failure(self):
        workers=[];scenarios=[]
        environment=dict(os.environ,AEGIS_APPROVAL_REQUEST_TOKEN='synthetic-producer',AEGIS_APPROVAL_EXECUTION_TOKEN='synthetic-executor',
            AEGIS_APPROVAL_BINDING_KEY='15'*32,PYTHONIOENCODING='utf-8',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
        def child(command,state,expected=0,extra=()):
            env=environment.copy()
            if command=='status':
                for key in ('AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN','AEGIS_APPROVAL_BINDING_KEY'):env.pop(key,None)
            process=subprocess.Popen([sys.executable,str(ROOT/'examples/async-durable-graph/agent.py'),command,
                '--state',str(state),'--endpoint',self.host.endpoint,*extra],cwd=ROOT,env=env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            try:output,error=process.communicate(timeout=25)
            finally:
                if process.poll() is None:process.kill();process.communicate(timeout=5)
            self.assertEqual(process.returncode,expected,output+error);self.assertEqual(error,'')
            workers.append(dict(pid=process.pid,command=command,returncode=process.returncode))
            return json.loads(output)
        for fail in (False,True):
            state=self.directory/('failure' if fail else 'success')
            started=child('start',state,extra=('--fail',) if fail else ())
            paused=child('status',state);self.assertTrue(paused['pending']);self.assertFalse((state/'tool-calls.jsonl').exists())
            asyncio.run(self.approve(started['action_id']))
            result=child('resume',state,expected=2 if fail else 0)
            if fail:self.assertEqual(result['business_error'],'SyntheticFailure')
            else:self.assertEqual((result['confirmation'],result['continuation']),('confirmed','resumed'))
            status=child('status',state);self.assertEqual(status['pending'],fail);self.assertEqual(status['completed'],not fail)
            child('resume',state,expected=1)
            self.assertEqual(len((state/'tool-calls.jsonl').read_text(encoding='utf-8').splitlines()),1)
            row=next(row for row in self.store.list_reviewed()['items'] if row['action_id']==started['action_id'])
            self.assertEqual(row['execution_state'],'failed' if fail else 'completed')
            scenarios.append(dict(partial_failure=fail,tool_calls=1,execution_state=row['execution_state']))
        receipt=ROOT/'artifacts/async-graph/processes.json';receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(dict(workers=workers,scenarios=scenarios),indent=2)+'\n',encoding='utf-8')
