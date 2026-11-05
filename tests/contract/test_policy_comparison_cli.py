import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2];EXAMPLE=ROOT/'examples/policy-comparison'


class ComparisonCLI(unittest.TestCase):
    def test_ac2303_actual_compare_ci_codes_reports_and_fixed_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'review.json'
            def cli(candidate,code,*extras):
                result=subprocess.run([sys.executable,'-m','aegis_policy','compare',str(EXAMPLE/'before.json'),str(candidate),
                    '--cases',str(EXAMPLE/'cases.json'),*extras],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)
                self.assertEqual(result.returncode,code,result.stdout+result.stderr);return result
            changed=cli(EXAMPLE/'candidate.json',1,'--output',str(output))
            report=json.loads(changed.stdout);self.assertEqual(report['counts'],dict(widened=2,narrowed=1,decision_changed=1,unchanged=4))
            self.assertEqual(json.loads(output.read_text()),report)
            original=output.read_bytes();cli(EXAMPLE/'before.json',2,'--output',str(output));self.assertEqual(output.read_bytes(),original)
            self.assertEqual(json.loads(cli(EXAMPLE/'before.json',0).stdout)['status'],'unchanged')
            invalid=Path(directory)/'invalid.json';invalid.write_text('synthetic-private-invalid-candidate')
            result=cli(invalid,2);self.assertEqual(result.stdout,'');self.assertNotIn('synthetic-private',result.stderr)
