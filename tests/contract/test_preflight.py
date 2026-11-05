from contextlib import redirect_stdout
from importlib import metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.doctor import ROOT,PROFILES,baseline,inspect_environment,main


class Preflight(unittest.TestCase):
    def setUp(self):self.pins=baseline(ROOT)

    def test_ac1701_profiles_match_without_importing_optional_packages(self):
        for profile,names in PROFILES.items():
            with self.subTest(profile=profile),patch('builtins.__import__',side_effect=AssertionError('application imports forbidden')):
                # baseline already loaded tomllib in setUp; even cached import
                # statements are forbidden, so isolate the metadata-only phase.
                with patch('scripts.doctor.baseline',return_value=self.pins):
                    report=inspect_environment(profile,reader=self.pins.__getitem__)
            self.assertEqual(report['status'],'passed')
            self.assertEqual([row['name'] for row in report['packages']],list(names))
            self.assertEqual(report['reviewed_environment']['status'],'not_run')

    def test_ac1701_missing_mismatch_and_metadata_errors_do_not_echo_values(self):
        def missing(name):raise metadata.PackageNotFoundError('private-path secret-value')
        def broken(name):raise OSError('private-path secret-value')
        for reader,status in ((missing,'missing'),(broken,'unavailable'),(lambda name:'private-path secret-value','mismatch')):
            report=inspect_environment(reader=reader)
            self.assertEqual(report['status'],'failed');self.assertEqual({row['status'] for row in report['packages']},{status})
            self.assertNotIn('private-path',json.dumps(report));self.assertNotIn('secret-value',json.dumps(report))

    def test_ac1701_old_python_and_missing_or_invalid_baseline_fail_closed(self):
        report=inspect_environment(python=(3,10,99),reader=lambda name:self.fail('must not inspect packages'))
        self.assertEqual(report['python_status'],'unsupported');self.assertEqual(report['packages'],[])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=inspect_environment(root=root);self.assertEqual(report['baseline_status'],'unavailable')
            (root/'requirements-dev.lock').write_text('invalid manifest',encoding='utf-8')
            report=inspect_environment(root=root);self.assertEqual(report['status'],'failed')
        for profile,flag in (('unknown',False),('native',True)):
            with self.assertRaises(ValueError):inspect_environment(profile,check_reviewed_env=flag)

    def test_ac1702_explicit_credential_shape_distinctness_and_privacy(self):
        valid={'AEGIS_APPROVAL_REQUEST_TOKEN':'private-producer','AEGIS_APPROVAL_EXECUTION_TOKEN':'private-executor',
            'AEGIS_APPROVAL_BINDING_KEY':'ab'*32,'OPENAI_API_KEY':'model-secret-not-read'}
        for changed in ({},{'AEGIS_APPROVAL_REQUEST_TOKEN':''},{'AEGIS_APPROVAL_EXECUTION_TOKEN':'private-producer'},
            {'AEGIS_APPROVAL_EXECUTION_TOKEN':'bad\ntoken'},{'AEGIS_APPROVAL_BINDING_KEY':'ab'*31},{'AEGIS_APPROVAL_BINDING_KEY':'invalid'}):
            report=inspect_environment('reviewed-async-graph',reader=self.pins.__getitem__,check_reviewed_env=True,environment={**valid,**changed})
            self.assertEqual(report['status'],'failed' if changed else 'passed')
            raw=json.dumps(report)
            for secret in valid.values():self.assertNotIn(secret,raw)
        with patch('scripts.doctor.os.environ',None):
            self.assertEqual(inspect_environment(reader=self.pins.__getitem__)['status'],'passed')

    def test_ac1703_cli_report_is_exclusive_and_errors_are_fixed(self):
        with tempfile.TemporaryDirectory() as directory,patch('scripts.doctor.metadata.version',side_effect=self.pins.__getitem__):
            path=Path(directory)/'report.json'
            first=io.StringIO()
            with redirect_stdout(first):self.assertEqual(main(['--json','--output',str(path)]),0)
            self.assertEqual(json.loads(first.getvalue()),json.loads(path.read_text(encoding='utf-8')))
            original=path.read_bytes();second=io.StringIO()
            with redirect_stdout(second):self.assertEqual(main(['--json','--output',str(path)]),1)
            self.assertEqual(path.read_bytes(),original)
            report=json.loads(second.getvalue());self.assertEqual(report['report_save_status'],'unavailable')
            self.assertNotIn(str(path),second.getvalue())

    def test_ac1703_real_cli_current_stdlib_only_and_isolated_core(self):
        cases=[(Path(sys.executable),[],0),(Path(sys.executable),['-S'],1)]
        isolated=ROOT/'tmp/spec015-final-isolated/Scripts/python.exe'
        if isolated.is_file():cases.append((isolated,[],0))
        evidence=[]
        for python,flags,expected in cases:
            command=[str(python),'-I',*flags,str(ROOT/'scripts/doctor.py'),'--json']
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,expected,result.stderr)
            report=json.loads(result.stdout);self.assertEqual(report['status'],'passed' if expected==0 else 'failed')
            evidence.append({'case':'stdlib-only' if flags else 'current' if python==Path(sys.executable) else 'isolated-core','exit_code':result.returncode,'report':report})
        clean=dict(os.environ)
        for key in ('AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN','AEGIS_APPROVAL_BINDING_KEY'):clean.pop(key,None)
        valid=dict(clean,AEGIS_APPROVAL_REQUEST_TOKEN='synthetic-doctor-producer',AEGIS_APPROVAL_EXECUTION_TOKEN='synthetic-doctor-executor',AEGIS_APPROVAL_BINDING_KEY='ab'*32)
        for profile,check_env,environment,expected in [('langgraph',False,clean,0),('reviewed-async-graph',False,clean,0),
            ('reviewed-async-graph',True,clean,1),('reviewed-async-graph',True,valid,0)]:
            command=[sys.executable,'-I',str(ROOT/'scripts/doctor.py'),'--json','--profile',profile]
            if check_env:command.append('--check-reviewed-env')
            result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,expected,result.stderr)
            for value in ('synthetic-doctor-producer','synthetic-doctor-executor','ab'*32):self.assertNotIn(value,result.stdout)
            evidence.append({'case':profile+('-env-valid' if expected==0 else '-env-missing') if check_env else profile,
                'exit_code':result.returncode,'report':json.loads(result.stdout)})
        path=ROOT/'artifacts/preflight/cli.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
