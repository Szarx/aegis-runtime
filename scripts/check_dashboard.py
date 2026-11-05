"""Bounded frontend verification using installed, locked workspace tools."""
import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]


def validate_test_report(report):
    keys=('numTotalTests','numPassedTests','numFailedTests','numPendingTests')
    if (type(report) is not dict or report.get('success') is not True or
        any(type(report.get(key)) is not int or report[key]<0 for key in keys) or report['numTotalTests']==0 or
        report['numPassedTests']!=report['numTotalTests'] or report['numFailedTests'] or report['numPendingTests'] or
        report.get('numTodoTests',0) or report.get('numFailedTestSuites',0)):
        raise ValueError('frontend tests failed or incomplete')
    return dict(run=report['numTotalTests'],passed=True,failures=0,skipped=0)


def bundle_inventory(directory):
    root=Path(directory).resolve()
    class Entries(HTMLParser):
        def __init__(self):super().__init__();self.values=[]
        def handle_starttag(self,tag,attrs):
            values=dict(attrs)
            if tag=='script' and values.get('src'):self.values.append(values['src'])
            if tag=='link' and values.get('href') and values.get('rel') in ('stylesheet','modulepreload'):self.values.append(values['href'])
    parser=Entries();parser.feed((root/'index.html').read_text(encoding='utf-8-sig'))
    entries=[]
    for value in parser.values:
        url=urlsplit(value);path=root/unquote(url.path).lstrip('/')
        if url.scheme or url.netloc or url.query or url.fragment or not url.path.startswith('/assets/') or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('invalid or external build entry')
        entries.append(path.resolve())
    if not any(path.suffix=='.js' for path in entries):raise ValueError('no JavaScript entry')
    assets=[]
    for path in sorted(root.rglob('*')):
        if path.suffix not in ('.js','.css') or not path.is_file():continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('unexpected build asset')
        raw=path.read_bytes();assets.append(dict(path=path.relative_to(root).as_posix(),bytes=len(raw),gzip_bytes=len(gzip.compress(raw,mtime=0)),sha256=hashlib.sha256(raw).hexdigest(),entry=path.resolve() in entries))
    sizes=dict(entry_js_gzip=sum(row['gzip_bytes'] for row in assets if row['entry'] and row['path'].endswith('.js')),
        all_js=sum(row['bytes'] for row in assets if row['path'].endswith('.js')),all_css=sum(row['bytes'] for row in assets if row['path'].endswith('.css')))
    limits=dict(entry_js_gzip=50*1024,all_js=1200*1024,all_css=64*1024)
    return dict(passed=all(sizes[key]<=limit for key,limit in limits.items()),sizes=sizes,limits=limits,assets=assets)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',default=shutil.which('node'));parser.add_argument('--output',type=Path,default=ROOT/'artifacts/dashboard-check')
    args=parser.parse_args(argv)
    if not args.node:parser.error('Node.js is required; provide --node PATH')
    folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=True);dashboard=ROOT/'dashboard'
    report=dict(status='failed',steps=[])
    try:
        with (folder/'check.log').open('w',encoding='utf-8') as log:
            stages=[('tests',['node_modules/vitest/vitest.mjs','run','--reporter=json','--outputFile='+str(folder/'tests.json')]),
                ('types',['node_modules/vue-tsc/bin/vue-tsc.js','--noEmit']),('build',['node_modules/vite/bin/vite.js','build'])]
            for name,command in stages:
                print('Checking dashboard '+name,flush=True);start=time.perf_counter()
                try:result=subprocess.run([args.node,*command],cwd=dashboard,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
                except subprocess.TimeoutExpired as error:
                    for partial in (error.stdout,error.stderr):
                        if partial:log.write(partial.decode('utf-8',errors='replace') if isinstance(partial,bytes) else partial)
                    log.flush();report['steps'].append(dict(step=name,returncode=None,timed_out=True,seconds=round(time.perf_counter()-start,3)))
                    raise
                log.write(result.stdout+result.stderr);log.flush()
                report['steps'].append(dict(step=name,returncode=result.returncode,seconds=round(time.perf_counter()-start,3)))
                if result.returncode:raise RuntimeError('frontend stage failed')
                if name=='tests':report['tests']=validate_test_report(json.loads((folder/'tests.json').read_text(encoding='utf-8')))
        report['bundle']=bundle_inventory(dashboard/'dist')
        if not report['bundle']['passed']:raise ValueError('bundle budget exceeded')
        report['status']='passed'
    except Exception as error:report['error']=type(error).__name__;report['message']='Dashboard verification failed; see check.log and stage results'
    (folder/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='bundle'}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
