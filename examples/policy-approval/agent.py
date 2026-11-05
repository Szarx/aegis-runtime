"""Synthetic request/resume host. Human decisions are a separate operation."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application, load_application
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.policy_tool import PendingReview
from aegis_runtime.reviewed_execution import ReviewedClient, ExecutionResult


def options(args):
    return dict(endpoint=args.endpoint,token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],
        execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
        binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY']))


def outcome(value):
    if isinstance(value,PendingReview):return dict(kind='pending_review',record=value.record)
    return dict(kind='completed',confirmation=value.confirmation if isinstance(value,ExecutionResult) else 'not_required')


def main(argv=None):
    os.environ.update(LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('request','resume'))
    parser.add_argument('--config',default=str(Path(__file__).with_name('application.json')))
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000')
    parser.add_argument('--action-id');parser.add_argument('--subject',default='reviewer');parser.add_argument('--ticket',required=True,type=Path)
    parser.add_argument('--calls',required=True,type=Path);parser.add_argument('--value',default='synthetic-private-value')
    parser.add_argument('--mode',choices=('native','langgraph'),default='native')
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--scenario',choices=('success','failure','cancel'),default='success')
    args=parser.parse_args(argv)
    output=None;result=None;state=None
    try:
        config=load_application(args.config)
        if args.command=='request':output=args.ticket.open('x',encoding='utf-8')
        else:
            raw=args.ticket.read_bytes()
            if len(raw)>65536:raise ValueError()
            saved=json.loads(raw)
            if type(saved) is not dict or saved.get('schema_version')!='aegis.policy-ticket.v1' or saved.get('kind')!='pending_review':raise ValueError()
            result=saved['record']
        arguments=dict(record_id=1,value=args.value)
        def write(record_id=1,value='synthetic-private-value'):
            with args.calls.open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(record_id=record_id,value=value))+'\n')
            if args.scenario=='failure':raise ValueError('synthetic business failure')
            return 'synthetic-success'
        async def async_write(record_id=1,value='synthetic-private-value'):
            value=write(record_id,value)
            if args.scenario=='cancel':raise asyncio.CancelledError('synthetic cancellation')
            return value
        class GraphState(TypedDict):
            operation:str
            result:dict
        def graph(node):
            from langgraph.graph import StateGraph,START,END
            builder=StateGraph(GraphState);builder.add_node('controlled_operation',node)
            builder.add_edge(START,'controlled_operation');builder.add_edge('controlled_operation',END)
            return builder.compile()
        def sync_host():
            nonlocal state
            with Application(config,subject=args.subject) as app:
                controlled=app.policy_tool(write,client=ReviewedClient(**options(args)),name='write',disclose_arguments=True)
                def operation():
                    value=controlled.invoke(arguments,summary='Synthetic policy-controlled record',action_id=args.action_id) if args.command=='request' else controlled.resume(result,arguments,summary='Synthetic policy-controlled record')
                    return outcome(value)
                if args.mode=='langgraph':
                    def node(state):return {'result':operation()}
                    state=app.graph(graph(node),name='policy-controlled-graph').invoke({'operation':args.command})['result']
                else:state=app.agent(operation,name='policy-controlled-agent')()
            return app.status()
        async def async_host():
            nonlocal state
            from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
            async with AsyncReviewedClient(**options(args)) as connection:
                with Application(config,subject=args.subject) as app:
                    controlled=app.policy_tool(async_write,client=connection,name='write',disclose_arguments=True)
                    async def operation():
                        value=await controlled.invoke(arguments,summary='Synthetic policy-controlled record',action_id=args.action_id) if args.command=='request' else await controlled.resume(result,arguments,summary='Synthetic policy-controlled record')
                        return outcome(value)
                    if args.mode=='langgraph':
                        async def node(state):return {'result':await operation()}
                        state=(await app.graph(graph(node),name='policy-controlled-graph').ainvoke({'operation':args.command}))['result']
                    else:state=await app.agent(operation,name='policy-controlled-agent')()
            return app.status()
        application=asyncio.run(async_host()) if args.asynchronous else sync_host()
        if output is not None:output.write(json.dumps(dict(schema_version='aegis.policy-ticket.v1',**state),indent=2)+'\n')
        report=dict(status=state['kind'],application=application,real_provider_requests=0)
        if state['kind']=='pending_review':report['action_id']=state['record']['action_id']
        else:report['confirmation']=state['confirmation']
        if application['flush'] is not True or application['shutdown'] is not True:
            report['status']='export_failed';print(json.dumps(report));return 5
        print(json.dumps(report));return 0 if report.get('confirmation')!='unknown' else 4
    except ActionDenied:print(json.dumps(dict(status='denied')));return 1
    except ApprovalUnavailable:print(json.dumps(dict(status='approval_unavailable')));return 2
    except asyncio.CancelledError:print(json.dumps(dict(status='cancelled')));return 3
    except Exception:print(json.dumps(dict(status='failed',error='Check local configuration, ticket, roles and synthetic call log; no automatic retry.')));return 5
    finally:
        if output is not None:output.close()


if __name__=='__main__':sys.exit(main())
