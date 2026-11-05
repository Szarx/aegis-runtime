import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.fixtures.configured_graph import write_graph_application
from tests.fixtures.application_config import ROOT


class ConfiguredGraphCLI(unittest.TestCase):
    def test_ac2701_v3_inspect_is_readonly_and_declares_graph_without_claiming_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);config=write_graph_application(folder);before=set(folder.iterdir())
            result=subprocess.run([sys.executable,'-m','aegis_runtime','inspect',str(config),'--subject','demo-agent'],cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(result.stdout);self.assertEqual(report['schema_version'],'aegis.application-inspection.v3')
            self.assertEqual(report['tools'][0]['graph']['node'],'review');self.assertTrue(report['tools'][0]['requires_review'])
            self.assertIn('graph/checkpoint compatibility and optional graph dependency imports',report['not_checked'])
            self.assertEqual(set(folder.iterdir()),before);self.assertNotIn(str(folder),result.stdout)
