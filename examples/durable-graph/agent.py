"""Local SQLite graph checkpoints across start/status/resume processes; no LLM."""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
import uuid

import aegis
from aegis_policy import Policy,Rule
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable,canonical_arguments
from aegis_runtime.durable_graph import CheckpointUnavailable,open_reviewed_checkpointer
from aegis_runtime.langgraph_reviewed import GraphBindingError,ReviewedGraphTool,TICKET
from aegis_runtime.reviewed_execution import ReviewedClient
from langgraph.graph import StateGraph,START,END


class State(TypedDict,total=False):
    aegis_call:dict
    aegis_reviewed:dict


class SyntheticFailure(ValueError):pass


def save_ticket(path,ticket):
    raw=canonical_arguments(ticket)
    temporary=path.with_suffix('.tmp')
    with temporary.open('xb') as output:
        output.write(raw);output.flush();os.fsync(output.fileno())
    # Publish an existing, fully written inode without replacing any ticket.
    os.link(temporary,path)
    temporary.unlink()


def load_ticket(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise GraphBindingError()
            result[key]=value
        return result
    with path.open('rb') as source:raw=source.read(16385)
    if len(raw)>16384:raise GraphBindingError()
    value=json.loads(raw,object_pairs_hook=unique)
    canonical_arguments(value)
    if type(value) is not dict or set(value)!={'schema','action_id','graph_binding','arguments','summary','ttl_seconds'} or value['schema']!=TICKET:
        raise GraphBindingError()
    binding=value['graph_binding']
    if type(binding) is not dict or any(binding.get(key)!=expected for key,expected in
            {'graph_id':'durable-demo','graph_revision':'graph-v1','node':'review','tool_revision':'demo-sync-v1'}.items()):
        raise GraphBindingError()
    return value


def make_gate(endpoint,state_directory):
    connection=ReviewedClient(endpoint,token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],
                              execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
                              binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY']))
    def write_record(*,record_id,value,fail=False):
        with (state_directory/'tool-calls.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps(dict(record_id=record_id,value=value,fail=fail))+'\n')
            output.flush();os.fsync(output.fileno())
        if fail:raise SyntheticFailure('synthetic partial effect')
        return {'record_id':record_id,'updated':True}
    policy=Policy('durable-demo-policy-v1',(Rule('permit','allow',('demo-agent',),('write_record',),('demo.write',)),))
    return ReviewedGraphTool(write_record,client=connection,policy=policy,subject='demo-agent',permission='demo.write',
                             tool='write_record',tool_revision='demo-sync-v1',disclose_arguments=True,
                             graph_id='durable-demo',graph_revision='graph-v1',node_name='review')


def compile_graph(gate,saver):
    def disabled(state):raise GraphBindingError()
    builder=StateGraph(State);builder.add_node('review',disabled if gate is None else gate.node)
    builder.add_edge(START,'review');builder.add_edge('review',END)
    return builder.compile(checkpointer=saver)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('start','status','resume'))
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000')
    parser.add_argument('--fail',action='store_true')
    args=parser.parse_args()
    if args.fail and args.command!='start':parser.error('--fail applies only to start')
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    directory=args.state.absolute();ticket=None
    try:
        if args.command=='start':
            directory.mkdir()  # Never reuse a previous run directory.
            config={'configurable':{'thread_id':uuid.uuid4().hex}}
            gate=make_gate(args.endpoint,directory)
            with open_reviewed_checkpointer(directory/'checkpoint.sqlite3',create=True) as saver:
                graph=compile_graph(gate,saver)
                graph.invoke({'aegis_call':{'call_id':uuid.uuid4().hex,'arguments':{
                    'record_id':9223372036854775807,'value':'synthetic-durable-write','fail':args.fail}}},config,durability='sync')
                ticket=gate.prepare(graph,config,summary='合成持久图记录写入',ttl_seconds=600)
                save_ticket(directory/'ticket.json',ticket)
                print(json.dumps({'phase':'pending','action_id':ticket['action_id']}))
            return 0
        ticket=load_ticket(directory/'ticket.json')
        config={'configurable':{'thread_id':ticket['graph_binding']['thread_id']}}
        with open_reviewed_checkpointer(directory/'checkpoint.sqlite3') as saver:
            if args.command=='status':
                snapshot=compile_graph(None,saver).get_state(config)
                if not snapshot.config or not snapshot.values:raise GraphBindingError()
                print(json.dumps({'action_id':ticket['action_id'],'checkpoint_id':snapshot.config['configurable']['checkpoint_id'],
                                  'pending':bool(snapshot.interrupts),'next':snapshot.next,
                                  'completed':snapshot.values.get('aegis_reviewed',{}).get('action_id')==ticket['action_id']}))
                return 0
            gate=make_gate(args.endpoint,directory);graph=compile_graph(gate,saver)
            aegis.init('durable-graph-example',output_path=directory/'traces.jsonl')
            @aegis.observe(name='durable-graph-host')
            def resume():return gate.resume(graph,config,ticket)
            result=resume()
            print(json.dumps({'action_id':ticket['action_id'],'confirmation':result.confirmation,
                              'continuation':result.continuation,'result':result.value}))
            return 0 if result.continuation=='resumed' else 3
    except SyntheticFailure:
        print(json.dumps({'action_id':ticket['action_id'],'business_error':'SyntheticFailure','retry':False}))
        return 2
    except (OSError,ValueError,KeyError,ImportError,CheckpointUnavailable,ApprovalUnavailable,ActionDenied):
        print(json.dumps({'action_id':None if ticket is None else ticket.get('action_id'),'operation':'not completed','retry':False}))
        return 1
    finally:
        aegis.shutdown()


if __name__=='__main__':raise SystemExit(main())
