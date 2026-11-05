"""Compare an existing synthetic LangGraph app with explicit Aegis integration."""

import argparse
import asyncio
import difflib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

import aegis
from openai import OpenAI,AsyncOpenAI
from examples.deepseek.offline import Fixture
from examples.existing_agent import adapter,host_before,host_after
from examples.existing_agent.application import business_view,initial_state
from examples.existing_agent.verify import verify


def host_delta():
    folder=Path(__file__).parent
    before=(folder/'host_before.py').read_text(encoding='utf-8').splitlines()
    after=(folder/'host_after.py').read_text(encoding='utf-8').splitlines()
    added=deleted=0
    for operation,a,b,c,d in difflib.SequenceMatcher(a=before,b=after,autojunk=False).get_opcodes():
        if operation in ('replace','insert'):added+=d-c
        if operation in ('replace','delete'):deleted+=b-a
    return {'scope':'host import switch only; excludes adapter implementation, SDK lifecycle, install and human edits',
        'added_lines':added,'deleted_lines':deleted,'application_lines_changed':0}


def business_tool(counts):
    def lookup_order(order_id: str) -> dict:
        """Read one synthetic order without contacting any business service."""
        counts['tool_calls']+=1
        if order_id!='demo-order':raise ValueError('synthetic order required')
        return {'order_id':order_id,'status':'shipped'}
    return lookup_order


def graph_for(client,tool,mode,asynchronous):
    if mode=='baseline':return host_before.connect(client,tool,asynchronous=asynchronous)
    if mode=='observe':return host_after.connect(client,tool,asynchronous=asynchronous)
    return adapter.build_agent(client,tool,asynchronous=asynchronous,mode=mode)


def execute(mode,asynchronous):
    fixture=Fixture(asynchronous=asynchronous);counts={'tool_calls':0}
    options=dict(api_key='synthetic-only-key',base_url='https://offline.invalid/v1',http_client=fixture.http_client(),max_retries=0)
    if asynchronous:
        async def run():
            async with AsyncOpenAI(**options) as client:
                state=await graph_for(client,business_tool(counts),mode,True).ainvoke(initial_state())
                return state
        state=asyncio.run(run())
    else:
        with OpenAI(**options) as client:state=graph_for(client,business_tool(counts),mode,False).invoke(initial_state())
    counts['model_calls']=len(fixture.requests)
    return business_view(state),counts


def run_case(mode,asynchronous,directory):
    started=time.perf_counter()
    receipt={'schema':'aegis.existing-agent.v1','status':'failed','mode':mode,'async':asynchronous,
        'python':platform.python_version(),'provider_requests':0,'human_onboarding':'not_run','platform_acceptance':'not_run',
        'host_delta':host_delta()}
    sdk=None;flushed=closed=False
    try:
        baseline,before_counts=execute('baseline',asynchronous)
        if mode!='baseline':sdk=aegis.init('existing-agent-recipe',output_path=directory/'traces.jsonl')
        try:result,counts=execute(mode,asynchronous)
        finally:
            if sdk is not None:flushed=aegis.flush();closed=aegis.shutdown()
            else:flushed=closed=True
        path=directory/'traces.jsonl'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []
        equivalent=result==baseline and counts==before_counts
        receipt['verification']=verify(rows,mode=mode,counts=counts,equivalent=equivalent,
            diagnostics=None if sdk is None else sdk.diagnostics(),flushed=flushed,closed=closed)
        receipt.update(status='passed',counts=counts,equivalent_to_baseline=equivalent)
    except Exception:
        # Never persist private exception messages, model responses or environment values.
        receipt['error_category']='execution_or_verification_failed'
    finally:
        receipt['execution_and_validation_ms']=round((time.perf_counter()-started)*1000,3)
        (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('baseline','observe','allow','deny'),default='observe')
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--runs-dir',type=Path,default=ROOT/'artifacts/existing-agent')
    args=parser.parse_args(argv)
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    args.runs_dir.mkdir(parents=True,exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix=args.mode+'-',dir=args.runs_dir))
    receipt=run_case(args.mode,args.asynchronous,directory)
    print(json.dumps({'status':receipt['status'],'receipt':str(directory/'receipt.json')}))
    return 0 if receipt['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())
