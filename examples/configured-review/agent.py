"""Prepare or explicitly resume a synthetic reviewed action; never approves it."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application,load_application
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.reviewed_execution import ReviewedClient


class SyntheticFailure(ValueError):pass


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','resume'));parser.add_argument('--config',default=str(Path(__file__).with_name('application.json')))
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000');parser.add_argument('--action-id');parser.add_argument('--subject',default='demo-agent')
    parser.add_argument('--async',dest='asynchronous',action='store_true');parser.add_argument('--value',default='synthetic')
    parser.add_argument('--scenario',choices=('success','failure','cancel'),default='success')
    parser.add_argument('--calls',default='artifacts/configured-review/business-calls.jsonl');args=parser.parse_args(argv)
    if args.command=='resume' and not args.action_id:parser.error('resume requires --action-id')
    if args.scenario=='cancel' and not args.asynchronous:parser.error('cancel requires --async')
    summary='Synthetic configured write; review complete arguments before approval'
    arguments=dict(record_id=9223372036854775807,value=args.value,scenario=args.scenario)
    def effect(record_id,value,scenario):
        target=Path(args.calls);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('a',encoding='utf-8') as output:output.write('{"synthetic_business_call":1}\n')
        if scenario=='failure':raise SyntheticFailure('synthetic partial effect')
        return 'synthetic-result'
    def write(record_id,value,scenario='success'):return effect(record_id,value,scenario)
    async def async_write(record_id,value,scenario='success'):
        await asyncio.sleep(0);result=effect(record_id,value,scenario)
        if scenario=='cancel':raise asyncio.CancelledError('synthetic cancellation after partial effect')
        return result
    def credentials():
        return dict(token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
                    binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY']))
    def present(result):
        if args.command=='prepare':return dict(action_id=result['action_id'],status=result['status'],execution_state=result['execution_state'])
        return dict(action_id=args.action_id,confirmation=result.confirmation,retry=False)
    try:
        config=load_application(args.config)
        if args.asynchronous:
            from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
            async def run():
                async with AsyncReviewedClient(args.endpoint,**credentials()) as client:
                    with Application(config,subject=args.subject) as app:
                        governed=app.reviewed_tool(async_write,name='write',client=client,disclose_arguments=True)
                        @app.agent(name='configured-reviewed-agent')
                        async def invoke():
                            if args.command=='prepare':return await governed.prepare(arguments,summary=summary,action_id=args.action_id)
                            return await governed.resume(args.action_id,arguments,summary=summary)
                        return present(await invoke())
            result=asyncio.run(run())
        else:
            client=ReviewedClient(args.endpoint,**credentials())
            with Application(config,subject=args.subject) as app:
                governed=app.reviewed_tool(write,client=client,disclose_arguments=True)
                @app.agent(name='configured-reviewed-agent')
                def invoke():
                    if args.command=='prepare':return governed.prepare(arguments,summary=summary,action_id=args.action_id)
                    return governed.resume(args.action_id,arguments,summary=summary)
                result=present(invoke())
        print(json.dumps(result));return 4 if result.get('confirmation')=='unknown' else 0
    except asyncio.CancelledError:
        print(json.dumps(dict(action_id=args.action_id,status='cancelled',retry=False)));return 3
    except SyntheticFailure:
        print(json.dumps(dict(action_id=args.action_id,status='business_failed',retry=False)));return 2
    except Exception:
        print(json.dumps(dict(action_id=args.action_id,status='not_completed',retry=False)));return 1


if __name__=='__main__':raise SystemExit(main())
