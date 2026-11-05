"""Default offline; live sends only synthetic verification data to DeepSeek."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import aegis
from aegis.deepseek import AegisAsyncDeepSeek, AegisDeepSeek

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from examples.deepseek.offline import Fixture


def call_options(model, stream=False):
    options = {'model':model, 'messages':[{'role':'user','content':'Reply with the single word OK.'}], 'stream':stream, 'max_tokens':128, 'extra_body':{'thinking':{'type':'disabled'}}}
    if stream:
        options['stream_options'] = {'include_usage':True}
    return options


@aegis.tool(permission='orders.read')
def lookup_order(order_id='demo-order'):
    if order_id != 'demo-order':
        raise ValueError('only the synthetic order is supported')
    return {'order_id':order_id, 'status':'shipped', 'source':'synthetic'}


@aegis.observe(name='deepseek-order-agent')
def run_agent(client, *, model, stream=False):
    response = client.chat.completions.create(**call_options(model, stream))
    if stream:
        with response as events:
            for _ in events: pass
    return lookup_order()


@aegis.observe(name='deepseek-order-agent')
async def run_async_agent(client, *, model, stream=False):
    response = await client.chat.completions.create(**call_options(model, stream))
    if stream:
        async with response as events:
            async for _ in events: pass
    return lookup_order()


@aegis.observe(name='deepseek-tool-agent')
def run_tool_agent(client, *, model):
    options = call_options(model)
    options['messages'] = [{'role':'user','content':'Look up synthetic order demo-order using lookup_order, then report its status briefly.'}]
    options['tools'] = [{'type':'function','function':{'name':'lookup_order','description':'Read one synthetic demo order.','parameters':{'type':'object','properties':{'order_id':{'type':'string','enum':['demo-order']}},'required':['order_id'],'additionalProperties':False}}}]
    options['tool_choice'] = {'type':'function','function':{'name':'lookup_order'}}
    response = client.chat.completions.create(**options)
    message = response.choices[0].message
    calls = message.tool_calls or []
    if len(calls) != 1 or calls[0].function.name != 'lookup_order':
        raise ValueError('expected exactly one synthetic lookup_order call')
    arguments = json.loads(calls[0].function.arguments)
    if arguments != {'order_id':'demo-order'}:
        raise ValueError('unexpected synthetic tool arguments')
    result = lookup_order(**arguments)
    options['messages'].extend([message.model_dump(exclude_none=True), {'role':'tool','tool_call_id':calls[0].id,'content':json.dumps(result)}])
    options['tool_choice'] = 'none'
    client.chat.completions.create(**options)
    return {'status':result['status'], 'tool_calls':1, 'model_calls':2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('offline','live'),default='offline')
    parser.add_argument('--stream',action='store_true')
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--tool-loop',action='store_true',help='sync, non-streaming two-call synthetic tool loop')
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument('--output',type=Path)
    destination.add_argument('--endpoint')
    args = parser.parse_args()
    if args.tool_loop and (args.stream or args.asynchronous):
        parser.error('--tool-loop currently supports sync non-streaming only')
    model = 'offline-deepseek'
    options = {'max_retries':0,'timeout':30}
    if args.mode == 'live':
        if not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL'):
            parser.error('live mode requires local DEEPSEEK_API_KEY and DEEPSEEK_MODEL')
        model = os.environ['DEEPSEEK_MODEL']
    else:
        options.update(api_key='offline-synthetic-key',http_client=Fixture(asynchronous=args.asynchronous).http_client())
    telemetry = {'output_path':args.output or Path('artifacts/deepseek/traces.jsonl')}
    if args.endpoint:
        telemetry = {'endpoint':args.endpoint}
        if os.environ.get('AEGIS_API_TOKEN'):
            telemetry['headers'] = {'Authorization':'Bearer ' + os.environ['AEGIS_API_TOKEN']}
    sdk = aegis.init('deepseek-example',**telemetry)
    success = False
    try:
        if args.asynchronous:
            async def execute():
                async with AegisAsyncDeepSeek(**options) as client:
                    return await run_async_agent(client,model=model,stream=args.stream)
            result = asyncio.run(execute())
        else:
            with AegisDeepSeek(**options) as client:
                result = run_tool_agent(client,model=model) if args.tool_loop else run_agent(client,model=model,stream=args.stream)
        print(json.dumps({'mode':args.mode,'provider':'deepseek','model':model,'stream':args.stream,'async':args.asynchronous,'result':result}))
        success = True
    except Exception as error:
        # SDK error strings may include provider response bodies. Never print them.
        status = getattr(error,'status_code',None)
        print(json.dumps({'mode':args.mode,'error_type':type(error).__name__,'http_status':status if type(status) is int else None}))
    finally:
        flushed, closed = aegis.flush(), aegis.shutdown()
        print(json.dumps({'diagnostics':sdk.diagnostics(),'flush':flushed,'shutdown':closed}))
    return 0 if success and flushed and closed else 1


if __name__ == '__main__':
    raise SystemExit(main())
