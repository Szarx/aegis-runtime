"""Offline graph streaming comparison; EOF and explicit early close."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import aegis
from openai import OpenAI,AsyncOpenAI

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from examples.langgraph.agent import build_agent,initial_state
from examples.deepseek.offline import Fixture


def normalize(value):
    if hasattr(value,'model_dump'):return value.model_dump(exclude={'id'})
    if isinstance(value,dict):return {key:normalize(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [normalize(item) for item in value]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--early-close',action='store_true')
    parser.add_argument('--fail-tool',action='store_true')
    destination=parser.add_mutually_exclusive_group()
    destination.add_argument('--endpoint')
    destination.add_argument('--output',type=Path)
    args=parser.parse_args()
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    telemetry={'output_path':args.output or Path('artifacts/langgraph-stream/traces.jsonl')}
    if args.endpoint:
        telemetry={'endpoint':args.endpoint}
        if os.environ.get('AEGIS_API_TOKEN'):telemetry['headers']={'Authorization':'Bearer '+os.environ['AEGIS_API_TOKEN']}
    sdk=aegis.init('langgraph-stream-example',**telemetry)

    def sync(traced):
        with OpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=Fixture().http_client(),max_retries=0) as client:
            graph,counts=build_agent(client,traced=traced,fail_tool=args.fail_tool,handle_tool_errors=args.fail_tool)
            stream=graph.stream(initial_state(),stream_mode='updates',version='v2')
            try:
                values=[next(stream)] if args.early_close else list(stream)
            finally:stream.close()
            return values,counts

    async def asynchronous(traced):
        async with AsyncOpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=Fixture(asynchronous=True).http_client(),max_retries=0) as client:
            graph,counts=build_agent(client,traced=traced,asynchronous=True,fail_tool=args.fail_tool,handle_tool_errors=args.fail_tool)
            stream=graph.astream(initial_state(),stream_mode='updates',version='v2')
            try:
                values=[await stream.__anext__()] if args.early_close else [value async for value in stream]
            finally:await stream.aclose()
            return values,counts
    try:
        if args.asynchronous:
            async def compare():return await asynchronous(False),await asynchronous(True)
            before,after=asyncio.run(compare())
        else:before,after=sync(False),sync(True)
        equivalent=normalize(before[0])==normalize(after[0]) and before[1]==after[1]
        print(json.dumps({'mode':'offline','async':args.asynchronous,'early_close':args.early_close,'handled_tool_error':args.fail_tool,'equivalent':equivalent,'chunks':len(after[0]),'before_counts':before[1],'after_counts':after[1]}))
    finally:
        flushed,closed=aegis.flush(),aegis.shutdown()
        print(json.dumps({'diagnostics':sdk.diagnostics(),'flush':flushed,'shutdown':closed}))
    return 0 if equivalent and flushed and closed else 1


if __name__=='__main__':raise SystemExit(main())
