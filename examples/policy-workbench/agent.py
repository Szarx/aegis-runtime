"""Gate a synthetic Runtime demo with declared policy acceptance cases."""
import argparse
import asyncio
import json
from pathlib import Path
import aegis
from aegis_policy.workbench import check_cases,load_cases,load_policy
from aegis_runtime import ActionDenied,Runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--output',default='artifacts/policy-workbench/traces.jsonl')
    args=parser.parse_args();folder=Path(__file__).resolve().parent
    policy=load_policy(folder/'policy.json');suite=load_cases(folder/'cases.json')
    report=check_cases(policy,suite)
    if report['status']!='passed':raise RuntimeError('policy cases failed before Runtime setup')
    sdk=aegis.init('policy-workbench-example',output_path=args.output)
    calls=0;attempts=[]
    def execute():
        nonlocal calls
        calls+=1;return 'synthetic'
    async def execute_async():return execute()
    try:
        for case in suite['cases']:
            runtime=Runtime(policy,subject=case['subject'])
            tool=runtime.tool(execute_async if args.asynchronous else execute,name=case['tool'],permission=case['permission'])
            @aegis.observe(name='policy-case-'+case['id'])
            def attempt():
                try:
                    if args.asynchronous:asyncio.run(tool())
                    else:tool()
                    decision=dict(effect='allow',reason='explicit_allow',rule_id=case['expected']['rule_id'])
                except ActionDenied as error:
                    decision={key:getattr(error.decision,key) for key in ('effect','reason','rule_id')}
                if decision!=case['expected']:raise RuntimeError('Runtime decision differs from case')
                attempts.append(dict(id=case['id'],**decision))
            attempt()
    finally:flushed=aegis.flush();closed=aegis.shutdown()
    expected=sum(c['expected']['effect']=='allow' for c in suite['cases'])
    result=dict(status='passed' if calls==expected and flushed and closed else 'failed',
        asynchronous=args.asynchronous,cases=len(attempts),business_calls=calls,
        policy_fingerprint=report['policy_fingerprint'],diagnostics=sdk.diagnostics())
    print(json.dumps(result));return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
