"""One real LangGraph interrupt, reviewed by a human; no model calls."""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
import uuid

import aegis
from aegis_policy import Policy,Rule
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import ReviewedGraphTool,GraphBindingError
from aegis_runtime.reviewed_execution import ReviewedClient
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver

ROOT=Path(__file__).resolve().parents[2]
EVENTS=ROOT/'artifacts/langgraph-reviewed/tool-calls.jsonl'


class State(TypedDict,total=False):
    aegis_call:dict
    aegis_reviewed:dict


class SyntheticFailure(ValueError):pass


def write_demo_record(*,record_id,value,fail=False):
    EVENTS.parent.mkdir(parents=True,exist_ok=True)
    with EVENTS.open('a',encoding='utf-8') as output:
        output.write(json.dumps(dict(record_id=record_id,value=value,fail=fail))+'\n')
    if fail:raise SyntheticFailure('synthetic partial effect')
    return {'record_id':record_id,'updated':True}


def make_gate(endpoint):
    connection=ReviewedClient(endpoint,token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],
                              execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
                              binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY']))
    policy=Policy('demo-graph-policy-v1',(Rule('permit','allow',('demo-agent',),('write_demo_record',),('demo.write',)),))
    return ReviewedGraphTool(write_demo_record,client=connection,policy=policy,subject='demo-agent',permission='demo.write',
                             tool='write_demo_record',tool_revision='demo-sync-v1',disclose_arguments=True,
                             graph_id='demo-reviewed-graph',graph_revision='graph-v1',node_name='review')


def compile_graph(gate,saver):
    graph=StateGraph(State);graph.add_node('review',gate.node)
    graph.add_edge(START,'review');graph.add_edge('review',END)
    return graph.compile(checkpointer=saver)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000')
    parser.add_argument('--fail',action='store_true')
    parser.add_argument('--rebuild-host',action='store_true')
    args=parser.parse_args()
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    aegis.init('langgraph-reviewed-example',output_path=ROOT/'artifacts/langgraph-reviewed/traces.jsonl')
    ticket=None
    try:
        gate=make_gate(args.endpoint);saver=InMemorySaver();graph=compile_graph(gate,saver)
        config={'configurable':{'thread_id':uuid.uuid4().hex}}
        graph.invoke({'aegis_call':{'call_id':uuid.uuid4().hex,'arguments':{
            'record_id':9223372036854775807,'value':'synthetic-graph-updated','fail':args.fail}}},config)
        ticket=gate.prepare(graph,config,summary='合成LangGraph记录写入',ttl_seconds=600)
        print(json.dumps({'phase':'pending','action_id':ticket['action_id']}),flush=True)
        print('在Dashboard执行审批中核对并批准；按Enter显式恢复，EOF保留暂停。',file=sys.stderr,flush=True)
        if sys.stdin.readline()=='':return 4
        if args.rebuild_host:
            # Same in-process saver, new driver and compiled graph. Not a
            # demonstration of durable storage across process termination.
            gate=make_gate(args.endpoint);graph=compile_graph(gate,saver)
        @aegis.observe(name='langgraph-reviewed-host')
        def resume():return gate.resume(graph,config,ticket)
        result=resume()
        print(json.dumps({'action_id':ticket['action_id'],'confirmation':result.confirmation,
                          'continuation':result.continuation,'result':result.value}))
        return 0 if result.continuation=='resumed' else 3
    except SyntheticFailure:
        print(json.dumps({'action_id':ticket['action_id'],'business_error':'SyntheticFailure','retry':False}))
        return 2
    except (KeyError,ValueError,ApprovalUnavailable,GraphBindingError):
        print(json.dumps({'action_id':None if ticket is None else ticket['action_id'],'operation':'not completed','retry':False}))
        return 1
    finally:
        aegis.shutdown()


if __name__=='__main__':raise SystemExit(main())
