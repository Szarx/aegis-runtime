import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import snapshot_check as check
from scripts import check as python_check


def python_report():
    return dict(passed=True,postgres=True,run=6,failures=0,errors=0,skipped=0,suites=[dict(suite=name,run=1,passed=True,failures=0,errors=0,skipped=0) for name in check.FOLDERS])


def dashboard_report():
    return dict(status='passed',steps=[dict(step=name,returncode=0) for name in ('tests','types','build')],tests=dict(run=2,passed=True,failures=0,skipped=0),bundle=dict(passed=True,limits=dict(entry_js_gzip=51200,all_js=1228800,all_css=65536),sizes=dict(entry_js_gzip=100,all_js=200,all_css=100),assets=[dict(path='assets/synthetic.js')]))


class SnapshotCheck(unittest.TestCase):
    def setUp(self):
        node=patch('scripts.snapshot_check.shutil.which',return_value='synthetic')
        node.start();self.addCleanup(node.stop)
    def test_database_preflight_fails_before_suites_and_does_not_echo_private_exception(self):
        output=io.StringIO()
        with patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-private-url'}),patch('psycopg.connect',side_effect=RuntimeError('synthetic-private-diagnostic')),patch('sys.stdout',output),patch('scripts.check.subprocess.run') as run:
            self.assertEqual(python_check.main(['--postgres']),2);run.assert_not_called()
        self.assertIn('preflight failed',output.getvalue());self.assertNotIn('synthetic-private',output.getvalue())
    def test_missing_python_receipt_fails_without_running_frontend(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-only'}),patch.object(check,'fingerprint',return_value=dict(files=1,sha256='a'*64)):
            folder=Path(directory)/'artifacts/run'
            def stage(name,command,output,report,timeout):
                report['steps'].append(dict(stage=name,status='passed',returncode=0))
                if name=='repository':(output/'repository.stdout.log').write_text(json.dumps(dict(status='passed',candidate_files=1,issues=[])))
            with patch.object(check,'run_stage',side_effect=stage) as run:
                self.assertEqual(check.main(['--postgres','--node','synthetic','--output',str(folder)]),1)
                self.assertEqual(run.call_count,3)
            self.assertEqual(json.loads((folder/'result.json').read_text())['steps'][-1]['status'],'failed')
    def test_python_receipt_requires_all_suites_exact_totals_and_no_skips(self):
        self.assertEqual(check.validate_python(python_report()),6)
        for change in (dict(run=7),dict(skipped=1),dict(postgres=False),dict(run=True),dict(suites=python_report()['suites'][:-1])):
            with self.subTest(change=change),self.assertRaises(ValueError):check.validate_python({**python_report(),**change})
    def test_dashboard_requires_types_build_complete_tests_and_fixed_budget(self):
        self.assertEqual(check.validate_dashboard(dashboard_report()),2)
        for key in ('steps','tests','bundle'):
            value=dashboard_report()
            if key=='steps':value[key].pop()
            elif key=='tests':value[key]['skipped']=1
            else:value[key]['sizes']['all_js']=1228801
            with self.subTest(key=key),self.assertRaises(ValueError):check.validate_dashboard(value)
    def test_preflight_and_existing_output_do_not_start_checks_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch.dict(os.environ,{},clear=True),patch.object(check,'run_stage') as run:
            self.assertEqual(check.main([]),2);run.assert_not_called()
            folder=Path(directory)/'artifacts/existing';folder.mkdir(parents=True);(folder/'keep').write_text('original')
            with patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-only'}):self.assertEqual(check.main(['--postgres','--node','synthetic','--output',str(folder)]),2)
            self.assertEqual((folder/'keep').read_text(),'original');run.assert_not_called()
            with patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-only'}),patch('scripts.snapshot_check.shutil.which',return_value=None):
                self.assertEqual(check.main(['--postgres','--node','missing-node','--output',str(Path(directory)/'artifacts/new')]),2)
                self.assertFalse((Path(directory)/'artifacts/new').exists());run.assert_not_called()
    def test_timeout_preserves_logs_and_failed_stage(self):
        with tempfile.TemporaryDirectory() as directory,patch('scripts.snapshot_check.subprocess.run',side_effect=subprocess.TimeoutExpired('synthetic-private-command',1)):
            report=dict(steps=[])
            with self.assertRaises(subprocess.TimeoutExpired):check.run_stage('synthetic',['synthetic-private-command'],Path(directory),report,1)
            self.assertEqual(report['steps'][0]['status'],'timed_out')
            self.assertTrue((Path(directory)/'synthetic.stderr.log').is_file())
    def test_failed_process_stops_before_later_stages_without_private_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-only'}),patch.object(check,'fingerprint',return_value=dict(files=1,sha256='a'*64)),patch.object(check,'run_stage',side_effect=RuntimeError('synthetic-private-diagnostic')) as run:
            folder=Path(directory)/'artifacts/run'
            self.assertEqual(check.main(['--postgres','--node','synthetic','--output',str(folder)]),1)
            self.assertEqual(run.call_count,1);self.assertNotIn('synthetic-private-diagnostic',(folder/'result.json').read_text())
    def test_success_requires_fresh_receipts_and_unchanged_source_bytes(self):
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch.dict(os.environ,{'AEGIS_TEST_DATABASE_URL':'synthetic-only'}),patch.object(check,'fingerprint',side_effect=[dict(files=1,sha256='a'*64),dict(files=1,sha256=('b' if changed else 'a')*64)]):
                folder=Path(directory)/'artifacts/run'
                def stage(name,command,output,report,timeout):
                    report['steps'].append(dict(stage=name,status='passed',returncode=0))
                    if name=='repository':(output/'repository.stdout.log').write_text(json.dumps(dict(status='passed',candidate_files=1,issues=[])))
                    if name in ('python','dashboard'):
                        child=output/name;child.mkdir();(child/'result.json').write_text(json.dumps(python_report() if name=='python' else dashboard_report()))
                with patch.object(check,'run_stage',side_effect=stage),patch.object(check,'bundle_inventory',return_value=dashboard_report()['bundle']):self.assertEqual(check.main(['--postgres','--node','synthetic','--output',str(folder)]),1 if changed else 0)
                report=json.loads((folder/'result.json').read_text());self.assertEqual(report['python_tests'],6);self.assertEqual(report['frontend_tests'],2)
    def test_fingerprint_changes_for_actual_candidate_bytes(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch('scripts.snapshot_check.subprocess.check_output',return_value=b'one.txt\0'):
            path=Path(directory)/'one.txt';path.write_text('one');first=check.fingerprint();path.write_text('two')
            self.assertNotEqual(first,check.fingerprint())
