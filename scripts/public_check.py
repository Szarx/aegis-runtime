"""Check source-publication materials without sending their contents anywhere."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.repository_check import audit, git

ROOT_FILES = {
    '.dockerignore', '.editorconfig', '.env.example', '.gitattributes', '.gitignore',
    'ARCHITECTURE.md', 'CONTRIBUTING.md', 'README.md', 'ROADMAP.md', 'SECURITY.md',
    'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md', 'docker-compose.yml', 'requirements-dev.lock',
}
GROUPS = {
    'collector': 'product', 'dashboard': 'product', 'sdk': 'product', 'runtime': 'product',
    'policy-engine': 'product', 'tests': 'synthetic_verification', 'examples': 'synthetic_examples',
    'docs': 'documentation', 'specs': 'technical_archive', 'resources': 'reference_metadata',
    'scripts': 'reproduction_tools', 'deploy': 'deployment', '.github': 'ci',
}
UPSTREAM = 'examples/external_react_agent/upstream/'


def classification(name):
    if name in ROOT_FILES:
        return 'project_entry'
    if name.startswith(UPSTREAM):
        return 'licensed_upstream'
    return GROUPS.get(name.split('/')[0]) if '/' in name else None


def markdown_issues(root, names):
    issues = []
    count = 0
    for name in names:
        if not name.endswith('.md') or name == UPSTREAM + 'README.md':
            continue  # Byte-preserved upstream links refer to its original repository.
        value = (root / name).read_text(encoding='utf-8-sig')
        if '\ufffd' in value or sum(line.startswith('```') for line in value.splitlines()) % 2:
            issues.append({'path': name, 'category': 'invalid_markdown'})
        for target in re.findall(r'\]\(([^)]+)\)', value):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            count += 1
            resolved = (root / name).parent / unquote(url.path)
            resolved = resolved.resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                issues.append({'path': name, 'category': 'invalid_local_link'})
    return count, issues


def check_catalog(root, names):
    catalog = json.loads((root / 'specs/catalog.json').read_text(encoding='utf-8'))
    records = catalog['records']
    expected = sorted(name[:-len('/spec.md')] for name in names
                      if re.fullmatch(r'specs/\d{3}-[^/]+/spec.md', name))
    paths = [row['path'] for row in records]
    if catalog.get('schema_version') != 'aegis.spec-catalog.v1' or paths != expected or not paths:
        raise ValueError('catalog mismatch')
    for number, row in enumerate(records, 1):
        if row['number'] != f'{number:03}' or not row['path'].startswith(f'specs/{number:03}-'):
            raise ValueError('missing or duplicate spec')
        if row['disposition'] != 'public' or row['status'] not in {
            'in_progress', 'historical_with_deferred_items', 'historical_verified', 'verified',
        } or not row['group'] or not row['review']:
            raise ValueError('missing disposition')
        directory = root / row['path']
        title = (directory / 'spec.md').read_text(encoding='utf-8-sig').splitlines()[0].lstrip('# ').strip()
        if title != row['title'] or any(not (directory / file).is_file() for file in ('plan.md', 'tasks.md')):
            raise ValueError('incomplete spec')
    return len(records)


def check_licenses(root):
    license_bytes = (root / 'LICENSE').read_bytes()
    if b'Apache License' not in license_bytes or b'Version 2.0, January 2004' not in license_bytes:
        raise ValueError('license missing')
    for component in ('sdk/python', 'runtime', 'policy-engine', 'collector'):
        package = root / component
        metadata = tomllib.loads((package / 'pyproject.toml').read_text())
        if metadata['project']['license'] != {'file': 'LICENSE'} or (package / 'LICENSE').read_bytes() != license_bytes:
            raise ValueError('package license mismatch')
        if (package / 'NOTICE').read_bytes() != (root / 'NOTICE').read_bytes():
            raise ValueError('notice mismatch')
    package = json.loads((root / 'dashboard/package.json').read_text())
    lock = json.loads((root / 'dashboard/package-lock.json').read_text())
    if package.get('license') != 'Apache-2.0' or lock['packages'][''].get('license') != 'Apache-2.0':
        raise ValueError('dashboard license mismatch')
    for required in ('NOTICE', 'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'docs/capabilities.md',
                     'dashboard/public/third-party-notices.txt'):
        if not (root / required).is_file():
            raise ValueError('required publication document missing')
    source = root / 'examples/external_react_agent'
    upstream = json.loads((source / 'upstream.json').read_text())
    for row in upstream['files']:
        path = (source / 'upstream' / row['path']).resolve()
        if not path.is_relative_to(source / 'upstream') or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('upstream changed')


def check(root):
    root = root.resolve()
    result = {'scope': 'public_materials', 'status': 'failed', 'issues': []}
    try:
        candidates = audit(root)
        if candidates['status'] != 'passed':
            result['issues'] = candidates.get('issues', [])
            return result
        names = sorted(set(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})
        counts = {}
        for name in names:
            group = classification(name)
            if group is None:
                result['issues'].append({'path': name, 'category': 'unclassified_public_material'})
            else:
                counts[group] = counts.get(group, 0) + 1
        result.update(candidate_files=len(names), classifications=counts)
        result['specs'] = check_catalog(root, names)
        check_licenses(root)
        links, issues = markdown_issues(root, names)
        result['local_links'] = links
        result['issues'].extend(issues)
        result['status'] = 'failed' if result['issues'] else 'passed'
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        result['issues'].append({'category': 'publication_material_invalid'})
    return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = check(ROOT)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
