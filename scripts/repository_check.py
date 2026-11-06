"""Check local candidate files, a staged tree, or a committed tree."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=(r'sk-[A-Za-z0-9_-]{20,}',r'gh[pousr]_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'AKIA[0-9A-Z]{16}')
BLOCKED={'.git','.venv','venv','node_modules','__pycache__','artifacts','tmp','build','dist','.aws','.codex','sources'}


def inspect_file(name,data):
    path=Path(name)
    if any(part in BLOCKED or part.endswith('.egg-info') for part in path.parts) or path.suffix in ('.whl','.pyc','.sqlite','.sqlite3','.pem','.key'):
        return 'generated_or_private_file'
    if path.name.startswith('.env') and path.name!='.env.example':return 'private_environment_file'
    if b'\0' in data:return 'unreviewed_binary'
    try:value=data.decode('utf-8-sig')
    except UnicodeError:return 'unreviewed_encoding'
    if any(re.search(pattern,value) for pattern in PATTERNS):return 'credential_pattern'
    return None


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)


def issue(name, category):
    return {'path': name, 'category': category}


def check_worktree(root):
    raw = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    names = sorted(set(raw.decode('utf-8').split('\0')) - {''})
    issues = []
    for name in names:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            category = 'symlink_requires_review'
        else:
            try:
                category = inspect_file(name, path.read_bytes())
            except OSError:
                category = 'unreadable_candidate'
        if category:
            issues.append(issue(name, category))
    return len(names), issues


def check_tree(root, tree):
    entries = git(root, 'ls-tree', '-rz', tree).split(b'\0')[:-1]
    issues = []
    with subprocess.Popen(
        ['git', 'cat-file', '--batch'], cwd=root, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as reader:
        for entry in entries:
            metadata, raw_name = entry.split(b'\t', 1)
            mode, kind, oid = metadata.split()
            name = raw_name.decode('utf-8')
            if mode == b'120000':
                issues.append(issue(name, 'symlink_requires_review'))
                continue
            if kind != b'blob' or mode not in (b'100644', b'100755'):
                issues.append(issue(name, 'unsupported_git_entry'))
                continue
            reader.stdin.write(oid + b'\n')
            reader.stdin.flush()
            header = reader.stdout.readline().split()
            if len(header) != 3 or header[:2] != [oid, b'blob']:
                raise ValueError('Missing or invalid Git blob')
            size = int(header[2])
            data = reader.stdout.read(size)
            if len(data) != size or reader.stdout.read(1) != b'\n':
                raise ValueError('Truncated Git blob')
            category = inspect_file(name, data)
            if category:
                issues.append(issue(name, category))
        reader.stdin.close()
        if reader.wait():
            raise ValueError('Git blob reader failed')
    return len(entries), issues


def audit(root, *, staged=False, commit=None):
    scope = 'staged' if staged else 'commit' if commit is not None else 'worktree'
    report = {'scope': scope}
    try:
        if staged:
            tree = git(root, 'write-tree').decode('ascii').strip()
        elif commit is not None:
            revision = git(root, 'rev-parse', '--verify', '--end-of-options',
                           commit + '^{commit}').decode('ascii').strip()
            tree = git(root, 'rev-parse', revision + '^{tree}').decode('ascii').strip()
            report['commit'] = revision
        else:
            tree = None

        if tree is None:
            count, issues = check_worktree(root)
        else:
            report['tree'] = tree
            count, issues = check_tree(root, tree)
        report.update(status='passed' if count and not issues else 'failed',
                      candidate_files=count, issues=issues)
        if not count:
            report['category'] = 'empty_candidate_inventory'
    except (OSError, subprocess.SubprocessError, ValueError):
        report.update(status='failed', category='candidate_inventory_unavailable')
    return report


def audit_history(root):
    """Inspect every reachable commit, including files deleted from HEAD."""
    report = {'scope': 'reachable_history', 'issues': []}
    try:
        commits = git(root, 'rev-list', '--all').decode('ascii').splitlines()
        if not commits:
            raise ValueError('empty history')
        trees = set()
        for commit in commits:
            checked = audit(root, commit=commit)
            if checked['status'] != 'passed':
                report['issues'].append({
                    'commit': commit,
                    'category': checked.get('category', 'unsafe_historical_tree'),
                    'issues': checked.get('issues', []),
                })
            if 'tree' in checked:
                trees.add(checked['tree'])
        report.update(status='failed' if report['issues'] else 'passed',
                      commits=len(commits), trees=len(trees))
    except (OSError, subprocess.SubprocessError, ValueError):
        report.update(status='failed', category='history_unavailable')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--staged', action='store_true', help='check the Git index')
    source.add_argument('--commit', help='check the tree of an existing commit')
    source.add_argument('--history', action='store_true', help='check all reachable commits')
    args = parser.parse_args()
    report = audit_history(ROOT) if args.history else audit(ROOT, staged=args.staged, commit=args.commit)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__=='__main__':sys.exit(main())
