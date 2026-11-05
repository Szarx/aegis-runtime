from pathlib import Path
import tempfile
import unittest
import json
import subprocess
from unittest.mock import patch
from scripts.check_dashboard import bundle_inventory,validate_test_report,main


class DashboardCheck(unittest.TestCase):
    def test_ac3201_timeout_writes_failed_stage_and_never_runs_later_checks(self):
        with tempfile.TemporaryDirectory() as directory,patch('scripts.check_dashboard.subprocess.run',side_effect=subprocess.TimeoutExpired('synthetic-node',300,output=b'partial output')) as run:
            self.assertEqual(main(['--node','synthetic-node','--output',directory]),1);self.assertEqual(run.call_count,1)
            report=json.loads((Path(directory)/'result.json').read_text());self.assertEqual(report['status'],'failed')
            self.assertTrue(report['steps'][0]['timed_out']);self.assertIn('partial output',(Path(directory)/'check.log').read_text())
    def test_ac3201_report_requires_actual_complete_tests_and_no_skip(self):
        good=dict(success=True,numTotalTests=3,numPassedTests=3,numFailedTests=0,numPendingTests=0)
        self.assertEqual(validate_test_report(good)['run'],3)
        for changes in (dict(success=False),dict(numTotalTests=0,numPassedTests=0),dict(numPendingTests=1),dict(numPassedTests=2),dict(numFailedTests=1),dict(numTodoTests=1),dict(numTotalTests=True)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate_test_report({**good,**changes})
    def test_ac3202_entry_rejects_external_missing_and_traversal_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for source in ('https://example.com/asset.js','/assets/missing.js','/assets/../../outside.js'):
                (root/'index.html').write_text('<script src="'+source+'"></script>')
                with self.subTest(source=source),self.assertRaises(ValueError):bundle_inventory(root)
    def test_ac3202_inventory_hashes_real_assets_and_fails_oversized_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'assets').mkdir();(root/'index.html').write_text('<script src="/assets/main.js"></script><link rel="stylesheet" href="/assets/main.css">')
            (root/'assets/main.js').write_text('export const value=1;');(root/'assets/main.css').write_text('body{margin:0}')
            report=bundle_inventory(root);self.assertTrue(report['passed']);self.assertEqual(len(report['assets']),2)
            self.assertTrue(all(len(row['sha256'])==64 for row in report['assets']))
            (root/'assets/large.js').write_bytes(b'x'*(1300*1024));self.assertFalse(bundle_inventory(root)['passed'])
