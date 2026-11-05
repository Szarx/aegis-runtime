from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import uuid

import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.live_server import LiveServer

ROOT=Path(__file__).resolve().parents[2]
DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class DurableGraphProcesses(unittest.TestCase):
    def setUp(self):
        self.schema='test_durable_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        self.host=LiveServer(create_app(self.store,api_token='spec014-trace',approval_request_token='spec014-producer',
                                       approval_review_token='spec014-review',approval_execution_token='spec014-executor')).start()
        self.temporary=tempfile.TemporaryDirectory(prefix='aegis processes ')
        self.directory=Path(self.temporary.name)
        self.environment=dict(os.environ,AEGIS_APPROVAL_REQUEST_TOKEN='spec014-producer',AEGIS_APPROVAL_EXECUTION_TOKEN='spec014-executor',
                              AEGIS_APPROVAL_BINDING_KEY='14'*32,PYTHONIOENCODING='utf-8',PYTHONPATH=str(ROOT),
                              LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
        self.workers=[];self.scenarios=[];self.passed=False

    def tearDown(self):
        self.host.close()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.temporary.cleanup()
        path=ROOT/'artifacts/durable-graph/process-validation.json';path.parent.mkdir(parents=True,exist_ok=True)
        report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        report[self._testMethodName]=dict(passed=self.passed,workers=self.workers,scenarios=self.scenarios,
                                         actual_http=True,postgres=True,sqlite=True,temporary_schema_and_files_cleaned=True)
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

    def run_child(self,command,state,*,phase=None,expected=0,extra=(),no_credentials=False):
        script=ROOT/('tests/fixtures/durable_worker.py' if phase else 'examples/durable-graph/agent.py')
        arguments=[sys.executable,str(script)]
        if phase:arguments+=['--phase',phase]
        arguments += [command,'--state',str(state),'--endpoint',self.host.endpoint,*extra]
        environment=self.environment.copy()
        if no_credentials:
            for name in ('AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN','AEGIS_APPROVAL_BINDING_KEY'):environment.pop(name,None)
        child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        try:output,error=child.communicate(timeout=20)
        finally:
            if child.poll() is None:child.kill();child.communicate(timeout=5)
        self.workers.append(dict(pid=child.pid,command=command,phase=phase,returncode=child.returncode))
        self.assertEqual(error,'');self.assertEqual(child.returncode,expected,output)
        return json.loads(output) if output.strip() else None

    def row(self,state):
        ticket=json.loads((state/'ticket.json').read_text(encoding='utf-8'))
        return next(row for row in self.store.list_reviewed()['items'] if row['action_id']==ticket['action_id'])

    def decide(self,state,decision='approved'):
        row=self.row(state)
        request=urllib.request.Request(self.host.endpoint+'/api/v1/reviewed-actions/'+row['action_id']+'/decision',
                    data=json.dumps(dict(decision=decision,review_digest=row['review_digest'])).encode(),
                    headers={'Authorization':'Bearer spec014-review','Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=5) as response:self.assertEqual(response.status,200)

    def events(self,state):
        path=state/'tool-calls.jsonl'
        return len(path.read_text(encoding='utf-8').splitlines()) if path.exists() else 0

    def test_ac1402_new_process_restores_exact_pause_and_persists_completion(self):
        state=self.directory/'success'
        start=self.run_child('start',state)
        row=self.row(state);binding=row['review_arguments']['graph_binding']
        status=self.run_child('status',state,no_credentials=True)
        self.assertEqual(status['checkpoint_id'],binding['checkpoint_id']);self.assertTrue(status['pending'])
        self.assertEqual(start['action_id'],row['action_id']);self.assertEqual(self.events(state),0)
        self.decide(state)
        result=self.run_child('resume',state)
        self.assertEqual((result['confirmation'],result['continuation']),('confirmed','resumed'))
        final=self.run_child('status',state,no_credentials=True)
        self.assertTrue(final['completed']);self.assertFalse(final['pending']);self.assertEqual(final['next'],[])
        self.assertNotEqual(status['checkpoint_id'],final['checkpoint_id'])
        self.run_child('resume',state,expected=1)
        self.assertEqual(self.events(state),1);self.assertEqual(self.row(state)['execution_state'],'completed')
        self.assertEqual(self.store.list_reviewed()['total'],1)
        self.scenarios.append(dict(case='independent_start_resume_status',tool_events=1,stable_action=True))
        self.passed=True

    def test_ac1403_actual_process_exit_at_five_boundaries_never_replays_tool(self):
        for phase,exitcode,events,execution in [('pause',70,1,'completed'),('claim',71,0,'claimed'),
                ('write',72,1,'claimed'),('complete',73,1,'completed'),('graph',74,1,'completed')]:
            with self.subTest(phase=phase):
                state=self.directory/phase
                self.run_child('start',state,phase='pause' if phase=='pause' else None,expected=70 if phase=='pause' else 0)
                original=(state/'ticket.json').read_bytes();self.decide(state)
                if phase=='pause':self.run_child('resume',state)
                else:self.run_child('resume',state,phase=phase,expected=exitcode)
                status=self.run_child('status',state,no_credentials=True)
                self.assertEqual(status['completed'],phase in ('pause','graph'))
                self.run_child('resume',state,expected=1)
                self.assertEqual(self.events(state),events)
                self.assertEqual(self.row(state)['execution_state'],execution)
                self.assertEqual((state/'ticket.json').read_bytes(),original)
                self.scenarios.append(dict(case=phase,crash_returncode=exitcode,tool_events=events,
                                           execution_state=execution,checkpoint_completed=status['completed'],duplicate_extra_events=0))
        self.assertEqual(self.store.list_reviewed()['total'],5)
        self.passed=True

    def test_ac1404_pending_rejected_expired_and_damaged_files_fail_closed(self):
        for scenario in ('pending','rejected','expired','arguments','version','profile','missing','duplicate','oversize'):
            with self.subTest(scenario=scenario):
                state=self.directory/scenario;self.run_child('start',state)
                if scenario=='rejected':self.decide(state,'rejected')
                elif scenario!='pending':self.decide(state)
                if scenario=='expired':
                    with self.store.connection() as connection:
                        connection.execute(sql.SQL("UPDATE {}.approvals SET created_at=clock_timestamp()-INTERVAL '601 seconds',expires_at=clock_timestamp()-INTERVAL '1 second' WHERE action_id=%s").format(sql.Identifier(self.schema)),[self.row(state)['action_id']])
                elif scenario in ('arguments','version'):
                    path=state/'ticket.json';ticket=json.loads(path.read_text(encoding='utf-8'))
                    if scenario=='arguments':ticket['arguments']['value']='changed'
                    else:ticket['graph_binding']['tool_revision']='changed'
                    path.write_text(json.dumps(ticket),encoding='utf-8')
                elif scenario=='profile':
                    with closing(sqlite3.connect(state/'checkpoint.sqlite3')) as connection:
                        connection.execute("UPDATE aegis_checkpoint_meta SET profile='different'");connection.commit()
                elif scenario=='missing':(state/'checkpoint.sqlite3').rename(state/'retained-checkpoint.sqlite3')
                elif scenario=='duplicate':(state/'ticket.json').write_text('{"schema":"one","schema":"two"}',encoding='utf-8')
                elif scenario=='oversize':(state/'ticket.json').write_bytes(b' '*16385)
                self.run_child('resume',state,expected=1)
                self.assertEqual(self.events(state),0)
                if scenario=='missing':self.assertFalse((state/'checkpoint.sqlite3').exists())
                self.scenarios.append(dict(case=scenario,tool_events=0))
        self.assertEqual(self.store.list_reviewed()['total'],9)
        self.assertEqual({row['execution_state'] for row in self.store.list_reviewed()['items']},{'available'})
        self.passed=True

    def test_ac1404_partial_failure_remains_consumed_and_trace_excludes_body(self):
        state=self.directory/'failure';self.run_child('start',state,extra=('--fail',));self.decide(state)
        result=self.run_child('resume',state,expected=2)
        self.assertEqual(result['business_error'],'SyntheticFailure')
        self.run_child('resume',state,expected=1)
        self.assertEqual(self.events(state),1);self.assertEqual(self.row(state)['execution_state'],'failed')
        status=self.run_child('status',state,no_credentials=True);self.assertTrue(status['pending'])
        telemetry=(state/'traces.jsonl').read_text(encoding='utf-8')
        for value in ('synthetic-durable-write','synthetic partial effect','spec014-producer','spec014-executor','14'*32):self.assertNotIn(value,telemetry)
        self.scenarios.append(dict(case='partial_failure',tool_events=1,duplicate_extra_events=0,trace_privacy=True))
        self.passed=True
