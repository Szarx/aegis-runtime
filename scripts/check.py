"""Run repository Python suites with explicit PostgreSQL opt-in."""
import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FOLDERS=('sdk/python/tests','policy-engine/tests','runtime/tests','collector/tests','tests/contract','tests/integration')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/check')
    parser.add_argument('--suite',choices=FOLDERS,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.suite:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/args.suite)))
        receipt=dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful() and not result.skipped)
        print(json.dumps(receipt));return 0 if receipt['passed'] else 1
    if args.postgres and not os.environ.get('AEGIS_TEST_DATABASE_URL'):parser.error('--postgres requires dedicated AEGIS_TEST_DATABASE_URL')
    if args.postgres:
        try:
            import psycopg
            with psycopg.connect(os.environ['AEGIS_TEST_DATABASE_URL'],connect_timeout=3,options='-c statement_timeout=3000') as connection:
                connection.execute('SELECT 1')
        except Exception:
            print('Dedicated PostgreSQL preflight failed; check the local test database before rerunning.');return 2
    folders=FOLDERS if args.postgres else FOLDERS[:-1]
    directory=args.output.resolve();directory.mkdir(parents=True,exist_ok=True)
    suites=[]
    with (directory/'tests.log').open('w',encoding='utf-8') as output:
        for folder in folders:
            print('Checking '+folder,flush=True)
            try:
                child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--suite',folder],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900)
                output.write(child.stdout+child.stderr);output.flush()
                row=json.loads(child.stdout.strip().splitlines()[-1]);row['passed']=row['passed'] and child.returncode==0
            except Exception as error:
                if isinstance(error,subprocess.TimeoutExpired):
                    for partial in (error.stdout,error.stderr):
                        if partial:output.write(partial.decode('utf-8',errors='replace') if isinstance(partial,bytes) else partial)
                output.write('\nSuite runner failed: '+type(error).__name__+'\n');output.flush()
                row=dict(run=0,failures=0,errors=1,skipped=0,passed=False,runner_error=type(error).__name__)
            suites.append(dict(suite=folder,**row))
    receipt={key:sum(row[key] for row in suites) for key in ('run','failures','errors','skipped')}
    receipt.update(postgres=args.postgres,passed=all(row['passed'] for row in suites),suites=suites)
    (directory/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
    if not receipt['passed']:print('See '+str(directory/'tests.log')+'; skips do not count as a passing run.')
    return 0 if receipt['passed'] else 1


if __name__=='__main__':sys.exit(main())
