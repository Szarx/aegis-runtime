"""Verify an installed private development snapshot without installing or publishing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check import FOLDERS
from scripts.check_dashboard import bundle_inventory


def fingerprint():
    raw=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT,timeout=30)
    names=sorted(set(raw.decode('utf-8').split('\0'))-{''});digest=hashlib.sha256()
    if not names:raise ValueError('empty candidate inventory')
    for name in names:
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('invalid candidate')
        content=path.read_bytes()
        digest.update(name.encode('utf-8')+b'\0'+hashlib.sha256(content).digest())
    return dict(files=len(names),sha256=digest.hexdigest())


def positive(value):return type(value) is int and value>0


def validate_python(report):
    suites=report['suites']
    if report.get('passed') is not True or report.get('postgres') is not True or [r['suite'] for r in suites]!=list(FOLDERS):raise ValueError('incomplete Python suites')
    for row in [report,*suites]:
        if row.get('passed') is not True or not positive(row.get('run')) or any(type(row.get(k)) is not int or row[k]!=0 for k in ('failures','errors','skipped')):raise ValueError('failed Python tests')
    if report['run']!=sum(row['run'] for row in suites):raise ValueError('inconsistent count')
    return report['run']


def validate_dashboard(report):
    steps=report['steps'];tests=report['tests'];bundle=report['bundle']
    if report.get('status')!='passed' or [r['step'] for r in steps]!=['tests','types','build'] or any(type(r.get('returncode')) is not int or r['returncode']!=0 for r in steps):raise ValueError('incomplete dashboard')
    if tests.get('passed') is not True or not positive(tests.get('run')) or any(type(tests.get(k)) is not int or tests[k]!=0 for k in ('failures','skipped')):raise ValueError('failed dashboard tests')
    expected=dict(entry_js_gzip=51200,all_js=1228800,all_css=65536)
    if bundle.get('passed') is not True or bundle.get('limits')!=expected or not bundle.get('assets'):raise ValueError('invalid bundle')
    if any(not positive(bundle['sizes'].get(k)) or bundle['sizes'][k]>limit for k,limit in expected.items()):raise ValueError('bundle budget exceeded')
    return tests['run']


def run_stage(name,command,folder,report,timeout):
    report['steps'].append(dict(stage=name,status='running'))
    save(folder,report)
    with (folder/(name+'.stdout.log')).open('w',encoding='utf-8') as output,(folder/(name+'.stderr.log')).open('w',encoding='utf-8') as error:
        try:child=subprocess.run(command,cwd=ROOT,stdout=output,stderr=error,timeout=timeout)
        except subprocess.TimeoutExpired:
            report['steps'][-1]['status']='timed_out';raise
    report['steps'][-1].update(status='passed' if child.returncode==0 else 'failed',returncode=child.returncode)
    if child.returncode:raise ValueError('stage failed')


def save(folder,report):
    temporary=folder/'result.tmp'
    temporary.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    temporary.replace(folder/'result.json')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres',action='store_true');parser.add_argument('--node',default=shutil.which('node'));parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if not args.postgres or not os.environ.get('AEGIS_TEST_DATABASE_URL') or not args.node or not shutil.which(args.node):
        print('Snapshot preflight failed: explicit dedicated PostgreSQL and installed Node are required.');return 2
    requested=args.output or ROOT/'artifacts/snapshot-check'/uuid.uuid4().hex
    folder=requested.resolve();base=ROOT/'artifacts'
    try:
        if any(path.is_symlink() for path in (requested,*requested.parents)) or base.is_symlink() or not base.resolve().is_relative_to(ROOT) or not folder.is_relative_to(base.resolve()) or folder==base.resolve():raise ValueError()
        folder.mkdir(parents=True,exist_ok=False)
    except (OSError,ValueError):
        print('Snapshot output must be a new directory inside repository artifacts.');return 2
    report=dict(schema_version='aegis.snapshot-check.v1',status='running',steps=[],scope='Local working-tree candidate bytes; no Git history, remote CI or publication approval.')
    try:
        report['before']=fingerprint();save(folder,report)
        commands=[('dependencies',[sys.executable,'-m','pip','check'],120),('repository',[sys.executable,'scripts/repository_check.py'],120),
            ('python',[sys.executable,'scripts/check.py','--postgres','--output',str(folder/'python')],6000),
            ('dashboard',[sys.executable,'scripts/check_dashboard.py','--node',args.node,'--output',str(folder/'dashboard')],1000)]
        for name,command,timeout in commands:
            print('Checking snapshot '+name,flush=True);run_stage(name,command,folder,report,timeout)
            if name=='repository':
                result=json.loads((folder/'repository.stdout.log').read_text(encoding='utf-8'))
                if result.get('status')!='passed' or result.get('candidate_files')!=report['before']['files'] or not positive(result.get('candidate_files')) or result.get('issues')!=[]:raise ValueError('invalid repository receipt')
            if name=='python':report['python_tests']=validate_python(json.loads((folder/'python/result.json').read_text(encoding='utf-8')))
            if name=='dashboard':
                result=json.loads((folder/'dashboard/result.json').read_text(encoding='utf-8'))
                report['frontend_tests']=validate_dashboard(result)
                if bundle_inventory(ROOT/'dashboard/dist')!=result['bundle']:raise ValueError('build changed')
        report['steps'].append(dict(stage='source',status='running'));save(folder,report)
        report['after']=fingerprint()
        if report['before']!=report['after']:raise ValueError('source changed')
        report['steps'][-1]['status']='passed'
        report['status']='passed'
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__,message='Snapshot verification failed; inspect local stage logs and receipts before rerunning.')
        if report['steps'] and report['steps'][-1]['status']!='timed_out':report['steps'][-1]['status']='failed'
    save(folder,report);print(json.dumps(report));return 0 if report['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())
