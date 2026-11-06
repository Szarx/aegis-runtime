import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import platform_smoke


class IsolatedPlatformSmoke(unittest.TestCase):
    def test_non_smoke_project_is_rejected_before_files_or_docker(self):
        with patch('sys.argv', ['platform_smoke.py', '--project', 'existing-user-project']), \
             patch('scripts.platform_smoke.subprocess.run') as run, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                platform_smoke.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_existing_container_blocks_all_mutations_and_credentials_are_not_inherited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / 'artifacts/run'
            observed = []
            def child(command, **kwargs):
                observed.append((command, kwargs['env']))
                kwargs['stdout'].write('existing-synthetic-container\n')
                return type('Result', (), {'returncode': 0})()
            argv = ['platform_smoke.py', '--project', 'aegis-smoke-fixture', '--http-port', '18000',
                    '--dashboard-port', '18080', '--postgres-port', '15433', '--output', str(output)]
            with patch.object(platform_smoke, 'ROOT', root), patch('sys.argv', argv), \
                 patch('scripts.platform_smoke.subprocess.run', side_effect=child), \
                 patch.dict('os.environ', {'OPENAI_API_KEY': 'synthetic-private', 'AEGIS_API_TOKEN': 'synthetic-host'}), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(platform_smoke.main(), 1)
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0][0][-3:], ['ps', '-a', '-q'])
            self.assertNotIn('OPENAI_API_KEY', observed[0][1])
            self.assertNotEqual(observed[0][1]['AEGIS_API_TOKEN'], 'synthetic-host')
            report = json.loads((output / 'result.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertNotIn('stop', str(report['stages']))
            self.assertNotIn('synthetic-private', stdout.getvalue())
