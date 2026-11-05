import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.dashboard_demo import main,validate_target


class DashboardDemo(unittest.TestCase):
    def test_ac3501_target_and_credentials_fail_before_any_request(self):
        for target in ('http://example.com','http://127.0.0.1/','https://user:secret@example.com','http://127.0.0.1:0','https://example.com?token=x'):
            with self.subTest(target=target),self.assertRaises(ValueError):validate_target(target)
        self.assertEqual(validate_target('https://example.com'),'https://example.com')
        with patch.dict(os.environ,{},clear=True),patch('scripts.dashboard_demo.run_example') as run:
            self.assertEqual(main(['--with-approvals']),2);self.assertFalse(run.called)
        with patch.dict(os.environ,{'AEGIS_API_TOKEN':'bad\nvalue'},clear=True),patch('scripts.dashboard_demo.run_example') as run:
            self.assertEqual(main([]),2);self.assertFalse(run.called)
    def test_ac3501_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True),patch('scripts.dashboard_demo.run_example') as run:
            path=Path(directory);(path/'keep.txt').write_text('original')
            self.assertEqual(main(['--output',directory]),2);self.assertEqual((path/'keep.txt').read_text(),'original');self.assertFalse(run.called)
    def test_ac3502_partial_failure_records_completed_stages_without_retry_or_private_error(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True),patch('scripts.dashboard_demo.run_example',side_effect=[dict(flush=True,shutdown=True,diagnostics=dict(exported_spans=10)),RuntimeError('synthetic-private-diagnostic')]) as run:
            output=Path(directory)/'new';self.assertEqual(main(['--attempts','5','--output',str(output)]),1)
            self.assertEqual(run.call_count,2);raw=(output/'report.json').read_text();report=json.loads(raw)
            self.assertEqual(report['stages'],[dict(stage='governance',attempts=5,exported_spans=10)])
            self.assertNotIn('synthetic-private-diagnostic',raw);self.assertEqual(report['real_provider_requests'],0)
