import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2];EXAMPLE=ROOT/'examples/policy-workbench'


class WorkbenchCLI(unittest.TestCase):
    def test_ac2203_actual_cli_check_explain_mismatch_errors_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'report.json'
            def cli(args,code):
                result=subprocess.run([sys.executable,'-m','aegis_policy',*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)
                self.assertEqual(result.returncode,code,result.stdout+result.stderr);return result
            result=cli(['check',str(EXAMPLE/'policy.json'),'--cases',str(EXAMPLE/'cases.json'),'--output',str(report)],0)
            self.assertEqual(json.loads(result.stdout)['cases_passed'],7);self.assertEqual(json.loads(report.read_text())['cases_total'],7)
            original=report.read_bytes();cli(['check',str(EXAMPLE/'policy.json'),'--output',str(report)],2);self.assertEqual(report.read_bytes(),original)
            denied=json.loads(cli(['explain',str(EXAMPLE/'policy.json'),'--subject','blocked','--tool','lookup','--permission','orders.read'],0).stdout)
            self.assertEqual(denied['decision']['rule_id'],'deny-blocked')
            cases=json.loads((EXAMPLE/'cases.json').read_text());cases['cases'][0]['expected']=dict(effect='deny',reason='no_match',rule_id=None)
            bad=Path(directory)/'mismatch.json';bad.write_text(json.dumps(cases))
            self.assertEqual(json.loads(cli(['check',str(EXAMPLE/'policy.json'),'--cases',str(bad)],1).stdout)['cases_failed'],1)
            bad.write_text('synthetic-private-invalid-content')
            result=cli(['check',str(bad)],2);self.assertNotIn('synthetic-private',result.stderr);self.assertEqual(result.stdout,'')

    def test_ac2203_actual_example_processes_execute_one_of_seven_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in (False,True):
                output=Path(directory)/('async.jsonl' if mode else 'sync.jsonl')
                result=subprocess.run([sys.executable,str(EXAMPLE/'agent.py'),'--output',str(output),*(['--async'] if mode else [])],cwd=ROOT,
                    env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                report=json.loads(result.stdout);self.assertEqual((report['cases'],report['business_calls']),(7,1))
                self.assertEqual(report['diagnostics']['exported_spans'],14)
                self.assertEqual(len(output.read_text().splitlines()),14)
