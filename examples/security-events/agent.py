"""Send synthetic governance attempts through SDK OTLP; never calls an LLM."""
import argparse
import asyncio
import json
import os

import aegis
from aegis_policy import Policy,Rule
from aegis_runtime import Runtime,ActionDenied


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000/v1/traces')
    parser.add_argument('--count',type=int,default=25)
    args=parser.parse_args()
    if not 1<=args.count<=100:parser.error('--count must be1..100')
    headers={'Authorization':'Bearer '+os.environ['AEGIS_API_TOKEN']} if os.environ.get('AEGIS_API_TOKEN') else {}
    sdk=aegis.init('security-events-example',endpoint=args.endpoint,headers=headers)
    counters=dict(completed=0,denied=0,error=0,cancelled=0,business_calls=0)
    allow=Policy('demo-policy-v1',(Rule('allow','allow',('demo-agent',),('write_record',),('demo.write',)),))
    deny=Policy('demo-policy-v1',(Rule('deny','deny',('demo-agent',),('write_record',),('demo.write',)),))
    @aegis.observe(name='security-events-agent')
    def attempt(index):
        case=index%5
        runtime=Runtime(policy=deny if case==1 else allow,subject=None if case==4 else 'demo-agent')
        @runtime.tool(name='write_record',permission='demo.write')
        def write_record():
            counters['business_calls']+=1
            if case==2:raise ValueError('synthetic private business error')
        @runtime.tool(name='write_record',permission='demo.write')
        async def cancelled():
            counters['business_calls']+=1
            raise asyncio.CancelledError('synthetic private cancellation')
        try:
            if case==3:asyncio.run(cancelled())
            else:write_record()
            counters['completed']+=1
        except ActionDenied:counters['denied']+=1
        except asyncio.CancelledError:counters['cancelled']+=1
        except ValueError:counters['error']+=1
    try:
        for i in range(args.count):attempt(i)
    finally:
        flushed=aegis.flush();closed=aegis.shutdown()
    report=dict(counters=counters,flush=flushed,shutdown=closed,diagnostics=sdk.diagnostics())
    print(json.dumps(report))
    return 0 if flushed and closed and report['diagnostics']['exported_spans']==args.count*2 else 1


if __name__=='__main__':raise SystemExit(main())
