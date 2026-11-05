from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.repository_check import audit, inspect_file


class RepositoryCandidates(unittest.TestCase):
    def test_ac1801_private_artifacts_and_credentials_are_blocked_without_echo(self):
        for name in ('tmp/report.json','.env','.env.local','artifacts/traces.jsonl','sdk/build/file.py','dist/package.whl','file.key'):
            self.assertIsNotNone(inspect_file(name,b'ordinary'))
        for raw in (b'sk-'+b'x'*25,b'ghp_'+b'a'*30,b'github_pat_'+b'b'*30,b'-----BEGIN '+b'PRIVATE KEY-----',b'AKIA'+b'Z'*16):
            self.assertEqual(inspect_file('example.py',raw),'credential_pattern')
        self.assertEqual(inspect_file('image.bin',b'a\0b'),'unreviewed_binary')

    def test_ac1801_source_and_environment_template_are_allowed(self):
        for name,data in (('example.py',b'print(1)'),('.env.example',b'AEGIS_API_TOKEN=aegis-local-dev'),('docs/guide.md','中文'.encode())):
            self.assertIsNone(inspect_file(name,data))


class RepositoryTree(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root).decode().strip()

    def test_ac4601_staged_and_committed_bytes_are_independent_of_worktree(self):
        path = self.root / 'agent.py'
        path.write_bytes(b'sk-' + b'x' * 28)
        self.git('add', 'agent.py')
        path.write_text('print(1)\n', encoding='utf-8')
        self.assertEqual(audit(self.root)['status'], 'passed')
        staged = audit(self.root, staged=True)
        self.assertEqual(staged['issues'], [{'path': 'agent.py', 'category': 'credential_pattern'}])

        self.git('commit', '-qm', 'Synthetic fixture')
        self.git('add', 'agent.py')
        self.assertEqual(audit(self.root, staged=True)['status'], 'passed')
        committed = audit(self.root, commit='HEAD')
        self.assertEqual(committed['tree'], staged['tree'])
        self.assertEqual(committed['issues'], staged['issues'])
        self.assertNotIn('x' * 28, str(committed))

    def test_ac4601_empty_or_special_entries_fail_closed(self):
        self.assertEqual(audit(self.root, staged=True)['category'], 'empty_candidate_inventory')
        source = self.root / 'entry'
        source.write_bytes(b'fixture')
        blob = self.git('hash-object', '-w', 'entry')
        self.git('update-index', '--add', '--cacheinfo', '120000,' + blob + ',symlink')
        self.git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',artifacts/private.txt')
        report = audit(self.root, staged=True)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['issues'], [
            {'path': 'artifacts/private.txt', 'category': 'generated_or_private_file'},
            {'path': 'symlink', 'category': 'symlink_requires_review'},
        ])
        self.assertEqual(audit(self.root, commit='missing')['status'], 'failed')
