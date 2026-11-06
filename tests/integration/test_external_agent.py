import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
import uuid

import psycopg
from psycopg import sql
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.live_server import LiveServer

ROOT = Path(__file__).resolve().parents[2]
DATABASE = os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE, 'dedicated PostgreSQL required')
class ExternalAgent(unittest.TestCase):
    def test_ac4802_pinned_template_matrix_and_independent_review(self):
        schema = 'test_external_' + uuid.uuid4().hex
        store = PostgresSpanStore(DATABASE, schema)
        store.migrate()
        app = create_app(store, api_token='synthetic-trace', approval_request_token='synthetic-producer',
                         approval_review_token='synthetic-reviewer', approval_execution_token='synthetic-executor')
        live = LiveServer(app).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                env = {**os.environ, 'LANGSMITH_TRACING': 'false', 'LANGCHAIN_TRACING_V2': 'false',
                       'AEGIS_API_TOKEN': 'synthetic-trace', 'AEGIS_APPROVAL_REQUEST_TOKEN': 'synthetic-producer',
                       'AEGIS_APPROVAL_EXECUTION_TOKEN': 'synthetic-executor', 'AEGIS_APPROVAL_BINDING_KEY': '11' * 32}

                def command(mode, output):
                    return [sys.executable, 'examples/external_react_agent/run.py', '--mode', mode,
                            '--output', str(output), '--endpoint', live.endpoint]

                reports = {}
                for mode in ('baseline', 'observe', 'allow', 'deny'):
                    target = folder / mode
                    result = subprocess.run(command(mode, target), cwd=ROOT, env=env, capture_output=True,
                                            text=True, encoding='utf-8', timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    reports[mode] = json.loads((target / 'report.json').read_text())
                for mode in ('observe', 'allow'):
                    self.assertEqual(reports[mode]['business_sha256'], reports['baseline']['business_sha256'])
                    self.assertEqual(reports[mode]['counts'], {'model_calls': 2, 'tool_calls': 1})
                self.assertEqual(reports['deny']['status'], 'denied')
                self.assertEqual(reports['deny']['counts']['tool_calls'], 0)

                for decision in ('approved', 'rejected'):
                    target = folder / decision
                    with (folder / (decision + '.log')).open('w', encoding='utf-8') as log:
                        child = subprocess.Popen(command('approval', target), cwd=ROOT, env=env, stdout=log, stderr=log)
                        try:
                            deadline = time.monotonic() + 25
                            while not (target / 'pending.json').exists():
                                if child.poll() is not None or time.monotonic() > deadline:
                                    self.fail('External template did not reach a safe interrupt')
                                time.sleep(.1)
                            action = json.loads((target / 'pending.json').read_text())['action_id']
                            record = store.list_reviewed(action_id=action)['items'][0]
                            self.assertEqual((record['status'], record['execution_state']), ('pending', 'available'))
                            body = json.dumps({'decision': decision, 'review_digest': record['review_digest']}).encode()
                            with urlopen(Request(live.endpoint + '/api/v1/reviewed-actions/' + action + '/decision',
                                    data=body, headers={'Authorization': 'Bearer synthetic-reviewer',
                                                        'Content-Type': 'application/json'}), timeout=5) as response:
                                self.assertEqual(response.status, 200)
                            self.assertEqual(store.list_reviewed(action_id=action)['items'][0]['execution_state'], 'available')
                            (target / 'resume').touch()
                            self.assertEqual(child.wait(timeout=25), 0 if decision == 'approved' else 1)
                            report = json.loads((target / 'report.json').read_text())
                            self.assertEqual(report['counts']['tool_calls'], int(decision == 'approved'))
                            if decision == 'approved':
                                self.assertEqual(report['business_sha256'], reports['baseline']['business_sha256'])
                                self.assertEqual(store.list_reviewed(action_id=action)['items'][0]['execution_state'], 'completed')
                        finally:
                            if child.poll() is None:
                                child.kill()
                                child.wait(timeout=5)
                traces = store.list_traces(limit=100)['items']
                self.assertEqual(len(traces), 7)
                self.assertIn('approval_requested', {row['governance_signal'] for row in traces})
                self.assertIn('review_tool_returned', {row['governance_signal'] for row in traces})
                for trace in traces:
                    detail = store.trace_detail(trace['trace_id'])
                    self.assertNotIn('synthetic-order', str(detail))
                    self.assertTrue(all(span['parent_span_id'] == detail['spans'][0]['span_id']
                                        for span in detail['spans'][1:]))
        finally:
            try:
                live.close()
            finally:
                with psycopg.connect(DATABASE) as connection:
                    connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
