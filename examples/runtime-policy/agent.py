"""Local counter-based authorization demo; no model or business service access."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import aegis
from aegis_policy import Policy
from aegis_runtime import Runtime, ActionDenied


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    destination=parser.add_mutually_exclusive_group()
    destination.add_argument('--output',type=Path)
    destination.add_argument('--endpoint')
    args=parser.parse_args()
    policy=Policy.from_json(Path(__file__).with_name('policy.json').read_text(encoding='utf-8'))
    telemetry={'output_path':args.output or Path('artifacts/runtime-policy/traces.jsonl')}
    if args.endpoint:
        telemetry={'endpoint':args.endpoint}
        if os.environ.get('AEGIS_API_TOKEN'):
            telemetry['headers']={'Authorization':'Bearer '+os.environ['AEGIS_API_TOKEN']}
    sdk=aegis.init('runtime-policy-example',**telemetry)
    results=[]
    original=ValueError('synthetic private tool failure')

    def prepare(subject,permission,fail):
        calls=[]
        def execute():
            calls.append(1)
            if fail:raise original
            return 'synthetic-result'
        if args.asynchronous:
            async def lookup_order():return execute()
        else:
            def lookup_order():return execute()
        return Runtime(policy,subject=subject).tool(lookup_order,permission=permission),calls

    scenarios=[('allow','order-agent','orders.read',False,1,'completed'),
        ('explicit-deny','blocked-agent','orders.read',False,0,'denied'),
        ('default-deny','order-agent','orders.write',False,0,'denied'),
        ('allowed-error','order-agent','orders.read',True,1,'error')]
    try:
        for scenario,subject,permission,fail,expected_calls,expected_outcome in scenarios:
            function,calls=prepare(subject,permission,fail)
            outcome='completed'
            try:
                if args.asynchronous:
                    @aegis.observe(name='governed-'+scenario)
                    async def agent():return await function()
                    result=asyncio.run(agent())
                else:
                    @aegis.observe(name='governed-'+scenario)
                    def agent():return function()
                    result=agent()
                assert result=='synthetic-result'
            except ActionDenied:outcome='denied'
            except ValueError as error:
                if error is not original:raise
                outcome='error'
            if outcome!=expected_outcome or len(calls)!=expected_calls:
                raise RuntimeError('authorization example failed')
            results.append({'scenario':scenario,'tool_calls':len(calls),'outcome':outcome})
        print(json.dumps({'mode':'local-synthetic','async':args.asynchronous,'scenarios':results}))
    finally:
        flushed=aegis.flush();stopped=aegis.shutdown()
        print(json.dumps({'diagnostics':sdk.diagnostics(),'flush':flushed,'shutdown':stopped}))
    return 0 if flushed and stopped else 1


if __name__=='__main__':raise SystemExit(main())
