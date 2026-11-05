import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.fixtures.application_config import ROOT
from tests.fixtures.managed_graph import write_managed_graph_application


class ManagedGraphCLI(unittest.TestCase):
    def test_ac2803_sync_async_stream_modes_versions_match_business_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            config=write_managed_graph_application(Path(directory))
            for mode in ('stream','astream'):
                for stream_mode in ('updates','values','combined'):
                    for version in ('v1','v2'):
                        with self.subTest(mode=mode,stream_mode=stream_mode,version=version):
                            result=subprocess.run([sys.executable,'examples/managed-graph/run.py','--config',str(config),'--mode',mode,
                                '--stream-mode',stream_mode,'--version',version],cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},
                                capture_output=True,text=True,encoding='utf-8',timeout=30)
                            self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads(result.stdout)
                            self.assertTrue(report['equivalent_to_baseline']);self.assertEqual((report['model_calls'],report['business_calls']),(2,1))
                            self.assertEqual(report['application']['active_calls'],0);self.assertNotIn('synthetic-private',result.stdout)
