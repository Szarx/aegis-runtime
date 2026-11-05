import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.fixtures.configured_review import write_review_application
from tests.fixtures.application_config import ROOT


class ConfiguredReviewCLI(unittest.TestCase):
    def test_ac2601_v2_inspection_declares_review_without_startup_or_credential_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);config=write_review_application(folder)
            result=subprocess.run([sys.executable,'-m','aegis_runtime','inspect',str(config),'--subject','demo-agent'],cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(result.stdout);self.assertEqual(report['schema_version'],'aegis.application-inspection.v2')
            self.assertTrue(report['tools'][0]['requires_review']);self.assertEqual(report['tools'][0]['tool_revision'],'write-v1')
            self.assertFalse((folder/'traces.jsonl').exists());self.assertNotIn(str(folder),result.stdout)
