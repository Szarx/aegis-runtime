import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


class PolicyApprovalCli(unittest.TestCase):
    def cli(self,code,*args):
        result=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr);return json.loads(result.stdout)
    def test_v2_check_explain_compare_and_case_versions(self):
        path=ROOT/'examples/policy-approval/policy.json'
        explanation=self.cli(0,'-m','aegis_policy','explain',str(path),'--subject','reviewer','--tool','write','--permission','records.write')
        self.assertEqual(explanation['decision']['effect'],'require_approval')
        self.assertEqual(explanation['schema_version'],'aegis.policy-explanation.v2')
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);cases=folder/'cases.json'
            cases.write_text(json.dumps(dict(schema_version='aegis.policy-cases.v2',cases=[dict(id='review',subject='reviewer',tool='write',permission='records.write',expected=dict(effect='require_approval',reason='explicit_require_approval',rule_id='review'))])))
            self.assertEqual(self.cli(0,'-m','aegis_policy','check',str(path),'--cases',str(cases))['cases_passed'],1)
            candidate=folder/'candidate.json';doc=json.loads(path.read_text(encoding='utf-8'));doc['rules'][1]['effect']='allow';candidate.write_text(json.dumps(doc))
            self.assertEqual(self.cli(1,'-m','aegis_policy','compare',str(path),str(candidate),'--cases',str(cases))['counts']['widened'],1)
    def test_v4_inspection_reports_policy_route_without_starting_agent(self):
        path=ROOT/'examples/policy-approval/application.json'
        for subject,expected in [('reader',False),('reviewer',True),('blocked',False)]:
            report=self.cli(0,'-m','aegis_runtime','inspect',str(path),'--subject',subject)
            self.assertEqual(report['schema_version'],'aegis.application-inspection.v4')
            self.assertEqual(report['tools'][0]['execution'],'policy')
            self.assertEqual(report['tools'][0]['requires_review'],expected)
