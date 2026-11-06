import json
from pathlib import Path
import tempfile
import unittest
import test_repository

from scripts.public_check import classification, check_catalog, markdown_issues
from scripts.repository_check import audit_history


class PublicationMaterials(unittest.TestCase):
    def test_unclassified_roots_require_a_publication_decision(self):
        self.assertIsNone(classification('private-notes.md'))
        self.assertIsNone(classification('customer-data/export.json'))
        self.assertEqual(classification('sdk/python/src/aegis/health.py'), 'product')
        self.assertEqual(classification('examples/external_react_agent/upstream/LICENSE'), 'licensed_upstream')

    def test_catalog_rejects_omitted_duplicate_and_unreviewed_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'specs/001-example'
            source.mkdir(parents=True)
            for name in ('spec.md', 'plan.md', 'tasks.md'):
                (source / name).write_text('# SPEC-001 Example\n')
            row = dict(number='001', path='specs/001-example', title='SPEC-001 Example',
                       disposition='public', status='historical_verified', group='SDK', review='synthetic')
            def save(records):
                (root / 'specs/catalog.json').write_text(json.dumps(dict(schema_version='aegis.spec-catalog.v1', records=records)))
            names = ['specs/001-example/spec.md']
            save([row]);self.assertEqual(check_catalog(root, names), 1)
            for records in ([], [row, row], [{**row, 'disposition': 'undecided'}], [{**row, 'number': '002'}]):
                save(records)
                with self.subTest(records=records), self.assertRaises(ValueError):
                    check_catalog(root, names)

    def test_broken_and_outside_links_fail_without_echoing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'README.md').write_text('[missing](private-report.md) [escape](../outside.md) [site](https://example.invalid)')
            count, issues = markdown_issues(root, ['README.md'])
            self.assertEqual(count, 2)
            self.assertEqual(len(issues), 2)
            self.assertNotIn('private-report', str(issues))


class PublicationHistory(test_repository.RepositoryTree):
    test_ac4601_staged_and_committed_bytes_are_independent_of_worktree = None
    test_ac4601_empty_or_special_entries_fail_closed = None

    def test_deleted_secret_in_old_commit_still_blocks_publication(self):
        secret = 'sk-' + 'q' * 29
        path = self.root / 'agent.py'
        path.write_text(secret)
        self.git('add', 'agent.py');self.git('commit', '-qm', 'Synthetic old commit')
        old = self.git('rev-parse', 'HEAD')
        path.write_text('print(1)\n')
        self.git('add', 'agent.py');self.git('commit', '-qm', 'Synthetic cleanup')
        report = audit_history(self.root)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['commits'], 2)
        self.assertEqual(report['issues'][0]['commit'], old)
        self.assertNotIn(secret, json.dumps(report))

    def test_all_reachable_branches_and_empty_history(self):
        self.assertEqual(audit_history(self.root)['status'], 'failed')
        (self.root / 'agent.py').write_text('print(1)\n')
        self.git('add', 'agent.py');self.git('commit', '-qm', 'Synthetic main')
        self.assertEqual(audit_history(self.root)['status'], 'passed')
        self.git('checkout', '-qb', 'other')
        (self.root / '.env').write_text('SYNTHETIC=only')
        self.git('add', '.env');self.git('commit', '-qm', 'Synthetic private file')
        self.git('checkout', '-')
        self.assertEqual(audit_history(self.root)['status'], 'failed')
