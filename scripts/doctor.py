"""Read-only metadata preflight; never imports or runs an Agent."""

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
NATIVE=('aegis-runtime-sdk','opentelemetry-api','opentelemetry-sdk','opentelemetry-semantic-conventions','typing-extensions')
GRAPH=('langgraph','langchain-core','langgraph-checkpoint','langgraph-prebuilt','langgraph-sdk')
PROFILES={
    'native':NATIVE,
    'langgraph':NATIVE+GRAPH+('openai','httpx2'),
    'reviewed-async-graph':NATIVE+GRAPH+('aegis-runtime-policy','aegis-runtime-control','httpx',
        'langgraph-checkpoint-sqlite','aiosqlite','sqlite-vec'),
}
NOT_CHECKED=['transitive dependency resolution','module imports and native binaries','Agent execution',
    'model requests or credentials','Collector/Docker connectivity','server roles/authentication','human onboarding time']


def baseline(root):
    import tomllib
    pins={}
    for line in (root/'requirements-dev.lock').read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        name,expected=line.split('==')
        if name in pins:raise ValueError()
        pins[name]=expected
    for folder in ('sdk/python','runtime','policy-engine'):
        project=tomllib.loads((root/folder/'pyproject.toml').read_text(encoding='utf-8'))['project']
        pins[project['name']]=project['version']
    for name in {name for names in PROFILES.values() for name in names}:
        # This report exposes only the repository's public numeric version baseline.
        import re
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*(?:[ab][0-9]+|rc[0-9]+|\.dev[0-9]+)?',pins[name]):raise ValueError()
    return pins


def reviewed_environment(environment):
    producer=environment.get('AEGIS_APPROVAL_REQUEST_TOKEN')
    executor=environment.get('AEGIS_APPROVAL_EXECUTION_TOKEN')
    def token(value):return type(value) is str and bool(value) and all(33<=ord(c)<=126 for c in value)
    key=environment.get('AEGIS_APPROVAL_BINDING_KEY')
    try:valid_key=type(key) is str and len(bytes.fromhex(key))>=32
    except ValueError:valid_key=False
    return [
        {'id':'producer_shape','status':'matched' if token(producer) else 'invalid'},
        {'id':'executor_shape','status':'matched' if token(executor) else 'invalid'},
        {'id':'producer_executor_distinct','status':'matched' if token(producer) and token(executor) and producer!=executor else 'invalid'},
        {'id':'binding_key_shape','status':'matched' if valid_key else 'invalid'},
    ]


def inspect_environment(profile='native', *, check_reviewed_env=False, root=ROOT, reader=None, environment=None, python=None):
    if profile not in PROFILES or check_reviewed_env and profile!='reviewed-async-graph':raise ValueError('invalid doctor options')
    release=sys.version_info[:3] if python is None else python
    report={'schema':'aegis.preflight.v1','profile':profile,'status':'failed',
        'python':'.'.join(str(value) for value in release),'python_status':'matched' if release[:2]>=(3,11) else 'unsupported',
        'packages':[],'reviewed_environment':{'status':'not_run','checks':[]},'not_checked':list(NOT_CHECKED)}
    if report['python_status']!='matched':return report
    try:pins=baseline(root)
    except Exception:
        report['baseline_status']='unavailable';return report
    report['baseline_status']='matched'
    reader=metadata.version if reader is None else reader
    for name in PROFILES[profile]:
        try:status='matched' if reader(name)==pins[name] else 'mismatch'
        except metadata.PackageNotFoundError:status='missing'
        except Exception:status='unavailable'
        report['packages'].append({'name':name,'expected':pins[name],'status':status})
    if check_reviewed_env:
        checks=reviewed_environment(os.environ if environment is None else environment)
        report['reviewed_environment']={'status':'matched' if all(row['status']=='matched' for row in checks) else 'invalid','checks':checks}
    if all(row['status']=='matched' for row in report['packages']) and report['reviewed_environment']['status'] in ('not_run','matched'):
        report['status']='passed'
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=tuple(PROFILES),default='native')
    parser.add_argument('--check-reviewed-env',action='store_true')
    parser.add_argument('--json',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.check_reviewed_env and args.profile!='reviewed-async-graph':parser.error('--check-reviewed-env requires reviewed-async-graph')
    report=inspect_environment(args.profile,check_reviewed_env=args.check_reviewed_env)
    if args.output is not None:
        try:
            with args.output.open('x',encoding='utf-8') as output:output.write(json.dumps(report,indent=2)+'\n')
        except OSError:
            report['status']='failed';report['report_save_status']='unavailable'
    if args.json:print(json.dumps(report,indent=2))
    else:
        print('Aegis metadata preflight: '+report['status'])
        print('Python: '+report['python_status'])
        print('Repository baseline: '+report.get('baseline_status','not_run'))
        for row in report['packages']:print(row['name']+': '+row['status']+' (expected '+row['expected']+')')
        print('Reviewed environment: '+report['reviewed_environment']['status'])
        if report.get('report_save_status'):print('Report save: unavailable')
        print('Scope and next steps: docs/preflight.md; imports, execution and connectivity were not checked.')
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())
