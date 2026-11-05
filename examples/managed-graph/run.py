"""Four graph call modes with configured tool control and synthetic official model SDK."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import httpx2
from business import build,initial,normalize
from aegis.openai import wrap_openai
from aegis_runtime.application import Application,load_application
from openai import OpenAI,AsyncOpenAI

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from examples.deepseek.offline import Fixture


def offline_http(asynchronous,delay_ms):
    fixture=Fixture(asynchronous=asynchronous)
    if not delay_ms:return fixture.http_client()
    if asynchronous:
        async def handle(request):
            await asyncio.sleep(delay_ms/1000);return fixture(request)
        return httpx2.AsyncClient(transport=httpx2.MockTransport(handle),trust_env=False)
    def handle(request):
        time.sleep(delay_ms/1000);return fixture(request)
    return httpx2.Client(transport=httpx2.MockTransport(handle),trust_env=False)


def sync_call(graph,args):
    if args.mode=='invoke':return graph.invoke(initial())
    with graph.stream(initial(),stream_mode=stream_mode(args),version=args.version) as stream:
        return [next(stream)] if args.early_close else list(stream)


async def async_call(graph,args):
    if args.mode=='ainvoke':return await graph.ainvoke(initial())
    async with graph.astream(initial(),stream_mode=stream_mode(args),version=args.version) as stream:
        return [await stream.__anext__()] if args.early_close else [item async for item in stream]


def stream_mode(args):return ['updates','values'] if args.stream_mode=='combined' else args.stream_mode


def synchronous(args,config,managed):
    with OpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=offline_http(False,args.model_delay_ms),max_retries=0) as client:
        if not managed:
            graph,counts=build(client,fail_tool=args.fail_tool)
            # Native generators are closed explicitly; managed streams add context support.
            if args.mode=='invoke':result=graph.invoke(initial())
            else:
                stream=graph.stream(initial(),stream_mode=stream_mode(args),version=args.version)
                try:result=[next(stream)] if args.early_close else list(stream)
                finally:stream.close()
            return result,counts,None
        with Application(config,subject=args.subject) as app:
            graph,counts=build(wrap_openai(client,provider='deepseek'),fail_tool=args.fail_tool,bind_tool=app.tool)
            result=sync_call(app.graph(graph,name='configured-order-graph'),args)
        return result,counts,app.status()


async def asynchronous(args,config,managed):
    async with AsyncOpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=offline_http(True,args.model_delay_ms),max_retries=0) as client:
        if not managed:
            graph,counts=build(client,asynchronous=True,fail_tool=args.fail_tool)
            if args.mode=='ainvoke':result=await graph.ainvoke(initial())
            else:
                stream=graph.astream(initial(),stream_mode=stream_mode(args),version=args.version)
                try:result=[await stream.__anext__()] if args.early_close else [item async for item in stream]
                finally:await stream.aclose()
            return result,counts,None
        with Application(config,subject=args.subject) as app:
            graph,counts=build(wrap_openai(client,provider='deepseek'),asynchronous=True,fail_tool=args.fail_tool,bind_tool=app.tool)
            result=await async_call(app.graph(graph,name='configured-order-graph'),args)
        return result,counts,app.status()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).with_name('application.json')))
    parser.add_argument('--subject',default='reader');parser.add_argument('--mode',choices=('invoke','ainvoke','stream','astream'),default='stream')
    parser.add_argument('--early-close',action='store_true');parser.add_argument('--fail-tool',action='store_true')
    parser.add_argument('--model-delay-ms',type=int,default=0,help='Synthetic transport delay only, 0..250ms; never a provider benchmark')
    parser.add_argument('--stream-mode',choices=('updates','values','combined'),default='updates');parser.add_argument('--version',choices=('v1','v2'),default='v2')
    args=parser.parse_args()
    if not 0<=args.model_delay_ms<=250:parser.error('model delay must be 0..250ms')
    if args.early_close and (args.mode not in ('stream','astream') or args.stream_mode!='updates'):parser.error('early close requires updates stream/astream')
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    try:
        config=load_application(args.config)
        if args.mode in ('ainvoke','astream'):
            async def compare():return await asynchronous(args,config,False),await asynchronous(args,config,True)
            before,after=asyncio.run(compare())
        else:before,after=synchronous(args,config,False),synchronous(args,config,True)
        equivalent=normalize(before[0])==normalize(after[0]);counts=after[1];status=after[2]
        allowed=config.policy.evaluate(subject=args.subject,tool='lookup_order',permission='orders.read').effect=='allow'
        expected_models=1 if args.early_close else 2;expected_tools=0 if args.early_close else int(allowed)
        valid=counts==dict(model_calls=expected_models,tool_calls=expected_tools) and equivalent==(allowed or args.early_close)
        valid=valid and status['active_calls']==0 and status['flush'] and status['shutdown'] and status['diagnostics']['exported_spans']==(2 if args.early_close else 4)
        print(json.dumps(dict(status='passed' if valid else 'failed',mode=args.mode,early_close=args.early_close,allowed=allowed,
            model_calls=counts['model_calls'],business_calls=counts['tool_calls'],equivalent_to_baseline=equivalent,application=status)))
        return 0 if valid else 1
    except Exception:
        print(json.dumps(dict(status='failed',error='Managed graph validation failed; inspect configuration and dependencies')));return 1


if __name__=='__main__':sys.exit(main())
