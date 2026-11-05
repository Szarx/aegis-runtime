"""Explicit async reviewed graph host with local checkpoints; no LLM."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
import uuid

import aegis
import aiosqlite
from aegis_policy import Policy, Rule
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable, canonical_arguments
from aegis_runtime.async_durable_graph import configure_async_reviewed_checkpointer
from aegis_runtime.async_langgraph_reviewed import AsyncReviewedGraphTool
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from aegis_runtime.durable_graph import CheckpointUnavailable, open_reviewed_checkpointer
from aegis_runtime.langgraph_reviewed import GraphBindingError, TICKET
from langgraph.graph import StateGraph, START, END


class State(TypedDict, total=False):
    aegis_call: dict
    aegis_reviewed: dict


class SyntheticFailure(ValueError): pass


def save_ticket(path, ticket):
    temporary=path.with_suffix('.tmp')
    with temporary.open('xb') as output:
        output.write(canonical_arguments(ticket));output.flush();os.fsync(output.fileno())
    os.link(temporary,path);temporary.unlink()


def load_ticket(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise GraphBindingError()
            result[key]=value
        return result
    with path.open('rb') as source:raw=source.read(16385)
    if len(raw)>16384:raise GraphBindingError()
    ticket=json.loads(raw,object_pairs_hook=unique);canonical_arguments(ticket)
    if type(ticket) is not dict or set(ticket)!={'schema','action_id','graph_binding','arguments','summary','ttl_seconds'} or ticket['schema']!=TICKET:
        raise GraphBindingError()
    binding=ticket['graph_binding']
    if type(binding) is not dict or any(binding.get(key)!=value for key,value in
        {'graph_id':'async-durable-demo','graph_revision':'graph-v1','node':'review','tool_revision':'demo-async-v1'}.items()):
        raise GraphBindingError()
    return ticket


def make_gate(connection, directory):
    async def write_record(*,record_id,value,fail=False):
        await asyncio.sleep(0)
        # A small synthetic effect log, not an async file-I/O adapter.
        with (directory/'tool-calls.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps(dict(record_id=record_id,value=value,fail=fail))+'\n')
            output.flush();os.fsync(output.fileno())
        if fail:raise SyntheticFailure('synthetic partial effect')
        return {'record_id':record_id,'updated':True}
    policy=Policy('async-durable-policy-v1',(Rule('permit','allow',('demo-agent',),('write_record',),('demo.write',)),))
    return AsyncReviewedGraphTool(write_record,client=connection,policy=policy,subject='demo-agent',permission='demo.write',
        tool='write_record',tool_revision='demo-async-v1',graph_id='async-durable-demo',graph_revision='graph-v1',
        node_name='review',disclose_arguments=True)


def compile_graph(gate, saver):
    async def disabled(state):raise GraphBindingError()
    graph=StateGraph(State);graph.add_node('review',disabled if gate is None else gate.node)
    graph.add_edge(START,'review');graph.add_edge('review',END)
    return graph.compile(checkpointer=saver)


async def run(args, directory, ticket):
    async with aiosqlite.connect((directory/'checkpoint.sqlite3').as_uri()+'?mode=rw',uri=True) as database:
        saver=await configure_async_reviewed_checkpointer(database)
        if args.command=='status':
            cfg={'configurable':{'thread_id':ticket['graph_binding']['thread_id']}}
            snapshot=await compile_graph(None,saver).aget_state(cfg)
            if not snapshot.config or not snapshot.values:raise GraphBindingError()
            print(json.dumps({'action_id':ticket['action_id'],'checkpoint_id':snapshot.config['configurable']['checkpoint_id'],
                'pending':bool(snapshot.interrupts),'next':snapshot.next,
                'completed':snapshot.values.get('aegis_reviewed',{}).get('action_id')==ticket['action_id']}))
            return 0
        async with AsyncReviewedClient(args.endpoint,token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],
            execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
            binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY'])) as connection:
            gate=make_gate(connection,directory);graph=compile_graph(gate,saver)
            if args.command=='start':
                cfg={'configurable':{'thread_id':uuid.uuid4().hex}}
                await graph.ainvoke({'aegis_call':{'call_id':uuid.uuid4().hex,'arguments':{
                    'record_id':9223372036854775807,'value':'synthetic-async-write','fail':args.fail}}},cfg,durability='sync')
                ticket=await gate.prepare(graph,cfg,summary='合成异步持久图记录写入',ttl_seconds=600)
                save_ticket(directory/'ticket.json',ticket)
                print(json.dumps({'phase':'pending','action_id':ticket['action_id']}));return 0
            cfg={'configurable':{'thread_id':ticket['graph_binding']['thread_id']}}
            aegis.init('async-durable-example',output_path=directory/'traces.jsonl')
            @aegis.observe(name='async-durable-host')
            async def resume():return await gate.resume(graph,cfg,ticket)
            result=await resume()
            print(json.dumps({'action_id':ticket['action_id'],'confirmation':result.confirmation,
                'continuation':result.continuation,'result':result.value}))
            return 0 if result.continuation=='resumed' else 3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('start','status','resume'));parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--endpoint',default='http://127.0.0.1:8000');parser.add_argument('--fail',action='store_true')
    args=parser.parse_args()
    if args.fail and args.command!='start':parser.error('--fail applies only to start')
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    directory=args.state.absolute();ticket=None
    try:
        if args.command=='start':directory.mkdir()
        else:ticket=load_ticket(directory/'ticket.json')
        # Synchronous initialization/validation happens before the event loop.
        with open_reviewed_checkpointer(directory/'checkpoint.sqlite3',create=args.command=='start'):pass
        return asyncio.run(run(args,directory,ticket))
    except SyntheticFailure:
        print(json.dumps({'action_id':ticket['action_id'],'business_error':'SyntheticFailure','retry':False}));return 2
    except (OSError,ValueError,KeyError,ImportError,CheckpointUnavailable,ApprovalUnavailable,ActionDenied):
        print(json.dumps({'action_id':None if ticket is None else ticket.get('action_id'),'operation':'not completed','retry':False}));return 1
    finally:aegis.shutdown()


if __name__=='__main__':sys.exit(main())
