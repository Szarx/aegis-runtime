"""Real LangGraph, offline model transport; compare before/after tracing."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

import aegis
from aegis.langgraph import observe_graph
from aegis.openai import wrap_openai
from langchain_core.messages import AIMessage, HumanMessage, convert_to_openai_messages
from langchain_core.tools import StructuredTool
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from openai import OpenAI, AsyncOpenAI

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from examples.deepseek.offline import Fixture


def build_agent(client, *, traced=False, asynchronous=False, fail_tool=False, handle_tool_errors=False, tool_error=None):
    counts = {'model_calls':0,'tool_calls':0}
    # The graph topology and state are identical before and after tracing.
    if traced:
        client = wrap_openai(client,provider='deepseek')

    def lookup_order(order_id: str) -> dict:
        """Read the fixed synthetic demo order; never accesses a business system."""
        counts['tool_calls'] += 1
        if fail_tool:
            raise tool_error if tool_error is not None else ValueError('synthetic private tool failure')
        if order_id != 'demo-order':
            raise ValueError('only the synthetic order is supported')
        return {'order_id':order_id,'status':'shipped','source':'synthetic'}

    # Wrap the function before LangChain derives its schema/signature.
    observed_tool = aegis.tool(lookup_order,permission='orders.read') if traced else lookup_order
    order_tool = StructuredTool.from_function(observed_tool)
    tools = [{'type':'function','function':{'name':'lookup_order','description':'Read a synthetic demo order.','parameters':{'type':'object','properties':{'order_id':{'type':'string','enum':['demo-order']}},'required':['order_id']}}}]

    def options(state):
        first = isinstance(state['messages'][-1],HumanMessage)
        return {'model':'offline-deepseek','messages':convert_to_openai_messages(state['messages']), 'tools':tools, 'tool_choice':{'type':'function','function':{'name':'lookup_order'}} if first else 'none', 'max_tokens':128, 'extra_body':{'thinking':{'type':'disabled'}}}

    def update(response):
        message = response.choices[0].message
        calls = [{'name':call.function.name,'args':json.loads(call.function.arguments),'id':call.id,'type':'tool_call'} for call in message.tool_calls or []]
        return {'messages':[AIMessage(content=message.content or '',tool_calls=calls)]}

    def model_node(state):
        counts['model_calls'] += 1
        return update(client.chat.completions.create(**options(state)))

    async def async_model_node(state):
        counts['model_calls'] += 1
        return update(await client.chat.completions.create(**options(state)))

    graph = StateGraph(MessagesState)
    graph.add_node('model',async_model_node if asynchronous else model_node)
    graph.add_node('tools',ToolNode([order_tool],handle_tool_errors=handle_tool_errors))
    graph.add_edge(START,'model')
    graph.add_conditional_edges('model',lambda state:'tools' if state['messages'][-1].tool_calls else END)
    graph.add_edge('tools','model')
    compiled = graph.compile()
    return (observe_graph(compiled,name='langgraph-order-agent') if traced else compiled),counts


def initial_state():
    return {'messages':[HumanMessage(content='Look up synthetic order demo-order.')]}


def business_view(state):
    # Random framework message IDs do not affect the business result.
    return [message.model_dump(exclude={'id'}) for message in state['messages']]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--async',dest='asynchronous',action='store_true')
    parser.add_argument('--fail-tool',action='store_true')
    destination=parser.add_mutually_exclusive_group()
    destination.add_argument('--endpoint')
    destination.add_argument('--output',type=Path)
    args=parser.parse_args()
    # This CLI is strictly offline with respect to provider/LangSmith services.
    os.environ['LANGSMITH_TRACING']='false'
    os.environ['LANGCHAIN_TRACING_V2']='false'
    telemetry={'output_path':args.output or Path('artifacts/langgraph/traces.jsonl')}
    if args.endpoint:
        telemetry={'endpoint':args.endpoint}
        if os.environ.get('AEGIS_API_TOKEN'):
            telemetry['headers']={'Authorization':'Bearer '+os.environ['AEGIS_API_TOKEN']}
    sdk=aegis.init('langgraph-example',**telemetry)
    started=time.perf_counter()
    def execute_sync(traced):
        with OpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=Fixture().http_client(),max_retries=0) as client:
            graph,counts=build_agent(client,traced=traced,fail_tool=args.fail_tool,handle_tool_errors=args.fail_tool)
            return graph.invoke(initial_state()),counts
    async def execute_async(traced):
        async with AsyncOpenAI(api_key='offline-synthetic-key',base_url='https://offline.invalid/v1',http_client=Fixture(asynchronous=True).http_client(),max_retries=0) as client:
            graph,counts=build_agent(client,traced=traced,asynchronous=True,fail_tool=args.fail_tool,handle_tool_errors=args.fail_tool)
            return await graph.ainvoke(initial_state()),counts
    try:
        if args.asynchronous:
            async def compare(): return await execute_async(False),await execute_async(True)
            before,after=asyncio.run(compare())
        else:
            before,after=execute_sync(False),execute_sync(True)
        equivalent=business_view(before[0])==business_view(after[0]) and before[1]==after[1]
        elapsed_ms=round((time.perf_counter()-started)*1000,3)
        print(json.dumps({'mode':'offline','framework':'langgraph','async':args.asynchronous,'handled_tool_error':args.fail_tool,'equivalent':equivalent,'before_counts':before[1],'after_counts':after[1],'cached_comparison_ms':elapsed_ms}))
    finally:
        flushed=aegis.flush()
        first_flush_ms=round((time.perf_counter()-started)*1000,3)
        closed=aegis.shutdown()
        print(json.dumps({'diagnostics':sdk.diagnostics(),'flush':flushed,'shutdown':closed,'cached_first_flush_ms':first_flush_ms}))
    return 0 if equivalent and flushed and closed else 1


if __name__=='__main__':
    raise SystemExit(main())
