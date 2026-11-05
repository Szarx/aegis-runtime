import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import check


class CheckRunner(unittest.TestCase):
    def test_timeout_preserves_partial_evidence_and_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(check,'ROOT',Path(directory)),patch.object(check,'FOLDERS',('synthetic','integration')),patch('scripts.check.subprocess.run',side_effect=subprocess.TimeoutExpired('synthetic',900,output=b'partial stdout',stderr=b'partial stderr')):
            self.assertEqual(check.main([]),1)
            folder=Path(directory)/'artifacts/check'
            report=json.loads((folder/'result.json').read_text())
            self.assertFalse(report['passed']);self.assertEqual(report['suites'][0]['runner_error'],'TimeoutExpired')
            raw=(folder/'tests.log').read_text()
            self.assertIn('partial stdout',raw);self.assertIn('partial stderr',raw)
