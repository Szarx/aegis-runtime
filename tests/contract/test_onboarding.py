"""Failure and data-integrity checks for the standard-library quickstart."""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.quickstart import AcceptanceError, child_environment, main, run_stage, validate_traces


def records(profile='native'):
    def span(trace, identifier, operation, parent=None, status='UNSET'):
        return {'trace_id':f'{trace:032x}', 'span_id':f'{identifier:016x}', 'parent_span_id':None if parent is None else f'{parent:016x}',
                'status':status, 'start_time_unix_nano':100, 'end_time_unix_nano':200,
                'scope':{'name':'aegis'}, 'attributes':{'gen_ai.operation.name':operation}}
    if profile == 'native':
        return [span(1,1,'invoke_agent'), span(1,2,'execute_tool',1),
                span(2,3,'invoke_agent',status='ERROR'), span(2,4,'execute_tool',3,'ERROR')]
    rows = [span(1,1,'invoke_agent'), span(1,2,'chat',1), span(1,3,'execute_tool',1), span(1,4,'chat',1)]
    for row in (rows[1],rows[3]):
        row['attributes'].update({'gen_ai.provider.name':'deepseek','gen_ai.usage.input_tokens':7,'gen_ai.usage.output_tokens':3})
    return rows


def output(profile='native'):
    diagnostic = {'accepted_spans':4,'exported_spans':4,'failed_spans':0,'dropped_spans':0,'pending_spans':0,'export_failures':0,'instrumentation_failures':0}
    lines = [{'diagnostics':diagnostic,'flush':True,'shutdown':True}]
    if profile == 'langgraph':
        lines.insert(0,{'equivalent':True,'before_counts':{'model_calls':2,'tool_calls':1},'after_counts':{'model_calls':2,'tool_calls':1}})
    return '\n'.join(json.dumps(line) for line in lines)


class OnboardingAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='aegis onboarding ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'traces.jsonl'

    def write(self, rows):
        self.path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')

    def test_accepts_both_realistic_shapes_without_copying_payloads(self):
        for profile in ('native','langgraph'):
            rows = records(profile)
            for row in rows:
                row['untrusted_output'] = 'private arbitrary value'
            self.write(rows)
            result = validate_traces(self.path, profile, output(profile))
            self.assertEqual(result['span_count'],4)
            self.assertNotIn('private',json.dumps(result))
            if profile == 'native': self.assertIsNone(result['business_comparison_verified'])
        self.assertTrue(result['business_comparison_verified'])

    def test_rejects_incomplete_duplicates_and_invalid_parentage(self):
        original = records()
        cases = [original[:-1],original + [original[0]]]
        bad_parent = copy.deepcopy(original)
        bad_parent[1]['parent_span_id'] = 'f'*16
        cases.append(bad_parent)
        duplicate = copy.deepcopy(original)
        duplicate[1]['span_id'] = duplicate[0]['span_id']
        cases.append(duplicate)
        for rows in cases:
            self.write(rows)
            with self.assertRaisesRegex(AcceptanceError,'^trace_validation_failed$'):
                validate_traces(self.path,'native',output())

    def test_rejects_bad_business_comparison_usage_and_export_diagnostics(self):
        for mutate in ('usage','comparison','diagnostic','shutdown'):
            rows = records('langgraph')
            summaries = [json.loads(line) for line in output('langgraph').splitlines()]
            if mutate == 'usage': rows[1]['attributes']['gen_ai.usage.input_tokens'] = 0
            if mutate == 'comparison': summaries[0]['after_counts']['model_calls'] = 3
            if mutate == 'diagnostic': summaries[1]['diagnostics']['dropped_spans'] = 1
            if mutate == 'shutdown': summaries[1]['shutdown'] = False
            self.write(rows)
            with self.assertRaises(AcceptanceError):
                validate_traces(self.path,'langgraph','\n'.join(json.dumps(row) for row in summaries))

    def test_corrupt_or_missing_file_is_fixed_failure_without_payload(self):
        for value in (None,'private malformed input',json.dumps({'private':'body'})):
            if value is not None: self.path.write_text(value,encoding='utf-8')
            with self.assertRaisesRegex(AcceptanceError,'^trace_validation_failed$'):
                validate_traces(self.path,'native',output())

    def test_environment_is_detached_without_mutating_host(self):
        values = {'OPENAI_API_KEY':'private','DEEPSEEK_API_KEY':'private','AEGIS_API_TOKEN':'private',
                  'PYTHONPATH':'private','PYTHONHOME':'private','LANGSMITH_API_KEY':'private'}
        with patch.dict(os.environ,values):
            environment = child_environment()
            self.assertTrue(all(key not in environment for key in values))
            self.assertEqual(os.environ['OPENAI_API_KEY'],'private')
            self.assertEqual(environment['LANGSMITH_TRACING'],'false')

    def test_real_process_failure_does_not_copy_command_or_stderr(self):
        receipt = {'stages':[]}
        with patch('sys.stdout',new_callable=io.StringIO):
            with self.assertRaisesRegex(AcceptanceError,'^process_failed$'):
                run_stage(receipt,'fixture',[sys.executable,'-I','-c',"import sys;print('private stderr',file=sys.stderr);sys.exit(7)"],
                          environment=child_environment(),timeout=5,cwd=self.root)
        self.assertEqual(receipt['stages'][0]['exit_code'],7)
        self.assertNotIn('private',json.dumps(receipt))

    def test_timeout_and_launch_error_are_bounded_fixed_failures(self):
        for failure, category in ((subprocess.TimeoutExpired('private command',1,output='private body'),'process_timeout'),
                                  (OSError('private system detail'),'process_unavailable')):
            receipt = {'stages':[]}
            with patch('scripts.quickstart.subprocess.run',side_effect=failure),patch('sys.stdout',new_callable=io.StringIO):
                with self.assertRaisesRegex(AcceptanceError,'^'+category+'$'):
                    run_stage(receipt,'fixture',['unused'],environment={},timeout=1)
            self.assertEqual(receipt['stages'][0]['status'],'failed')
            self.assertNotIn('private',json.dumps(receipt))
        with patch('sys.stdout',new_callable=io.StringIO):
            with self.assertRaisesRegex(AcceptanceError,'^process_timeout$'):
                run_stage({'stages':[]},'real-timeout',[sys.executable,'-I','-c','import time; time.sleep(30)'],
                          environment=child_environment(),timeout=0.1,cwd=self.root)

    def test_failure_stops_before_example_and_preserves_prior_runs(self):
        old = self.root / 'prior-run'
        old.mkdir()
        (old / 'keep.txt').write_text('keep',encoding='utf-8')
        with patch('scripts.quickstart.subprocess.run',side_effect=OSError('private')),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(main(['--runs-dir',str(self.root)]),1)
            self.assertEqual(main(['--runs-dir',str(self.root)]),1)
        receipts = list(self.root.glob('native-*/receipt.json'))
        self.assertEqual(len(receipts),2)
        for path in receipts:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual([stage['name'] for stage in receipt['stages']],['venv'])
            self.assertEqual(receipt['error_category'],'process_unavailable')
            self.assertNotIn('first_valid_trace_ms',receipt)
            self.assertNotIn('private',json.dumps(receipt))
        self.assertEqual((old / 'keep.txt').read_text(),'keep')


if __name__ == '__main__':
    unittest.main()
