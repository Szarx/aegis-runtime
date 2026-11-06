"""Reproduce notices for the npm production dependency closure in package-lock."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def render(root):
    dashboard = root / 'dashboard'
    lock = json.loads((dashboard / 'package-lock.json').read_text())
    sections = [
        'Aegis Dashboard — third-party license notices\n',
        'Generated from package-lock.json production dependencies (including their build-time subdependencies).',
        'Package versions and license/NOTICE text are retained from the installed locked npm packages.\n',
    ]
    for name, metadata in sorted(lock['packages'].items()):
        if not name or metadata.get('dev') or metadata.get('optional'):
            continue
        folder = dashboard / name
        actual = json.loads((folder / 'package.json').read_text())
        if actual['version'] != metadata['version']:
            raise ValueError('installed version differs from lock')
        files = sorted(path for path in folder.iterdir() if path.is_file() and
                       path.name.lower().startswith(('license', 'notice', 'copying')))
        if (folder / 'licenses').is_dir():
            files += sorted(path for path in (folder / 'licenses').rglob('*') if path.is_file())
        if not files:
            raise ValueError('dependency license unavailable')
        sections += ['=' * 72, actual['name'] + ' ' + actual['version'] + '\n']
        for file in files:
            sections += [file.relative_to(folder).as_posix(), file.read_text(encoding='utf-8-sig').rstrip() + '\n']
    # Preserve license words while normalizing line-ending/trailing whitespace.
    return '\n'.join(line.rstrip() for line in '\n'.join(sections).splitlines()).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        value = render(ROOT)
        path = ROOT / 'dashboard/public/third-party-notices.txt'
        if args.check:
            if path.read_text(encoding='utf-8') != value:
                raise ValueError('notices changed')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding='utf-8', newline='\n')
    except (OSError, ValueError, KeyError):
        print('Third-party notices unavailable or inconsistent with the installed lock.');return 1
    print('Third-party notices match the locked production dependency closure.');return 0


if __name__ == '__main__':
    sys.exit(main())
