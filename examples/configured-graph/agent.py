"""Configured local reviewed graph: separate start / status / resume processes, no LLM."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
import uuid
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application,load_application
from aegis_runtime.approvals import ApprovalUnavailable,canonical_arguments
from aegis_runtime.durable_graph import CheckpointUnavailable,open_reviewed_checkpointer
from aegis_runtime.langgraph_reviewed import GraphBindingError,TICKET
from langgraph.graph import StateGraph,START,END


class State(TypedDict,total=False):
    aegis_call:dict
    aegis_reviewed:dict


class SyntheticFailure(ValueError):pass


def save_ticket(path,ticket):
    temporary=path.with_suffix('.tmp')
    with temporary.open('xb') as output:
        output.write(canonical_arguments(ticket));output.flush();os.fsync(output.fileno())
    os.link(temporary,path);temporary.unlink()


def load_ticket(path,binding):
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
    graph=ticket['graph_binding']
    expected=dict(graph_id=binding.graph.id,graph_revision=binding.graph.revision,node=binding.graph.node,tool_revision=binding.tool_revision)
    if type(graph) is not dict or any(graph.get(key)!=value for key,value in expected.items()):raise GraphBindingError()
    return ticket


def compile_graph(gate,saver,binding):
    def disabled(state):raise GraphBindingError()
    graph=StateGraph(State);graph.add_node(binding.graph.node,disabled if gate is None else gate.node)
    graph.add_edge(START,binding.graph.node);graph.add_edge(binding.graph.node,END)
    return graph.compile(checkpointer=saver)


def effect(directory,scenario):
    # Only a synthetic count is logged; full arguments live in the explicit approval/ticket.
    with (directory/'tool-calls.jsonl').open('a',encoding='utf-8') as output:
        output.write('{"synthetic_business_call":1}\n');output.flush();os.fsync(output.fileno())
    if scenario=='failure':raise SyntheticFailure()


def credentials():
    return dict(token=os.environ['AEGIS_APPROVAL_REQUEST_TOKEN'],execution_token=os.environ['AEGIS_APPROVAL_EXECUTION_TOKEN'],
        binding_key=bytes.fromhex(os.environ['AEGIS_APPROVAL_BINDING_KEY']))


def config_for(ticket):return {'configurable':{'thread_id':ticket['graph_binding']['thread_id']}}


def initial(args):return {'aegis_call':{'call_id':uuid.uuid4().hex,'arguments':{
    'record_id':9223372036854775807,'value':'synthetic-configured-write','scenario':args.scenario}}}


def status(snapshot,ticket):
    if not snapshot.config or not snapshot.values:raise GraphBindingError()
    print(json.dumps(dict(action_id=ticket['action_id'],checkpoint_id=snapshot.config['configurable']['checkpoint_id'],
        pending=bool(snapshot.interrupts),next=snapshot.next,completed=snapshot.values.get('aegis_reviewed',{}).get('action_id')==ticket['action_id'])))
    return 0


def prepared(directory,ticket):
    save_ticket(directory/'ticket.json',ticket)
    print(json.dumps(dict(action_id=ticket['action_id'],phase='pending')));return 0


def resumed(ticket,result):
    print(json.dumps(dict(action_id=ticket['action_id'],confirmation=result.confirmation,continuation=result.continuation)))
    return 0 if result.continuation=='resumed' else 4


def synchronous(args,directory,config,binding,ticket):
    from aegis_runtime.reviewed_execution import ReviewedClient
    with open_reviewed_checkpointer(directory/'checkpoint.sqlite3',create=args.command=='start') as saver:
        if args.command=='status':return status(compile_graph(None,saver,binding).get_state(config_for(ticket)),ticket)
        connection=ReviewedClient(args.endpoint,**credentials())
        with Application(config,subject='demo-agent') as app:
            def write(*,record_id,value,scenario='success'):
                effect(directory,scenario);return True
            gate=app.reviewed_graph_tool(write,client=connection,disclose_arguments=True)
            graph=compile_graph(gate,saver,binding)
            if args.command=='start':
                cfg={'configurable':{'thread_id':uuid.uuid4().hex}}
                app.agent(graph.invoke,name='configured-graph-start')(initial(args),cfg,durability='sync')
                return prepared(directory,gate.prepare(graph,cfg,summary='Synthetic configured graph write',ttl_seconds=600))
            return resumed(ticket,app.agent(gate.resume,name='configured-graph-resume')(graph,config_for(ticket),ticket))


async def asynchronous(args,directory,config,binding,ticket):
    import aiosqlite
    from aegis_runtime.async_durable_graph import configure_async_reviewed_checkpointer
    from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
    async with aiosqlite.connect((directory/'checkpoint.sqlite3').as_uri()+'?mode=rw',uri=True) as database:
        saver=await configure_async_reviewed_checkpointer(database)
        if args.command=='status':return status(await compile_graph(None,saver,binding).aget_state(config_for(ticket)),ticket)
        async with AsyncReviewedClient(args.endpoint,**credentials()) as connection:
            with Application(config,subject='demo-agent') as app:
                async def write(*,record_id,value,scenario='success'):
                    await asyncio.sleep(0);effect(directory,scenario)
                    if scenario=='cancel':raise asyncio.CancelledError()
                    return True
                gate=app.reviewed_graph_tool(write,client=connection,disclose_arguments=True)
                graph=compile_graph(gate,saver,binding)
                if args.command=='start':
                    cfg={'configurable':{'thread_id':uuid.uuid4().hex}}
                    await app.agent(graph.ainvoke,name='configured-graph-start')(initial(args),cfg,durability='sync')
                    return prepared(directory,await gate.prepare(graph,cfg,summary='Synthetic configured graph write',ttl_seconds=600))
                return resumed(ticket,await app.agent(gate.resume,name='configured-graph-resume')(graph,config_for(ticket),ticket))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('start','status','resume'));parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True);parser.add_argument('--endpoint',default='http://127.0.0.1:8000')
    parser.add_argument('--async',dest='asynchronous',action='store_true');parser.add_argument('--scenario',choices=('success','failure','cancel'),default='success')
    args=parser.parse_args()
    if args.scenario!='success' and (args.command!='start' or args.scenario=='cancel' and not args.asynchronous):parser.error('scenario applies to start; cancel requires --async')
    os.environ['LANGSMITH_TRACING']='false';os.environ['LANGCHAIN_TRACING_V2']='false'
    directory=args.state.absolute();ticket=None
    try:
        config=load_application(args.config)
        if len(config.tools)!=1 or config.tools[0].name!='write' or config.tools[0].execution!='reviewed_graph':raise ValueError()
        binding=config.tools[0]
        if args.command=='start':directory.mkdir()
        else:ticket=load_ticket(directory/'ticket.json',binding)
        if args.asynchronous:
            with open_reviewed_checkpointer(directory/'checkpoint.sqlite3',create=args.command=='start'):pass
            return asyncio.run(asynchronous(args,directory,config,binding,ticket))
        return synchronous(args,directory,config,binding,ticket)
    except SyntheticFailure:
        print(json.dumps(dict(action_id=None if ticket is None else ticket['action_id'],business_error='SyntheticFailure',retry=False)));return 2
    except asyncio.CancelledError:
        print(json.dumps(dict(action_id=None if ticket is None else ticket['action_id'],operation='cancelled',retry=False)));return 3
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,ImportError,CheckpointUnavailable,ApprovalUnavailable,ActionDenied):
        print(json.dumps(dict(action_id=None if ticket is None else ticket.get('action_id'),operation='not_completed',retry=False)));return 1


if __name__=='__main__':sys.exit(main())
