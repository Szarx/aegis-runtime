"""An ordinary LangGraph application; no Aegis imports or tracing flags."""

import json
from langchain_core.messages import AIMessage, HumanMessage, convert_to_openai_messages
from langchain_core.tools import StructuredTool
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode


def build_agent(client, lookup_order, *, asynchronous=False):
    order_tool = StructuredTool.from_function(lookup_order)
    tools = [{'type':'function','function':{'name':'lookup_order','description':'Read a synthetic order.',
        'parameters':{'type':'object','properties':{'order_id':{'type':'string'}},'required':['order_id']}}}]

    def options(state):
        return dict(model='offline-deepseek',messages=convert_to_openai_messages(state['messages']),tools=tools,
            tool_choice={'type':'function','function':{'name':'lookup_order'}} if isinstance(state['messages'][-1],HumanMessage) else 'none',
            max_tokens=128)

    def update(response):
        message=response.choices[0].message
        calls=[dict(name=call.function.name,args=json.loads(call.function.arguments),id=call.id,type='tool_call') for call in message.tool_calls or []]
        return {'messages':[AIMessage(content=message.content or '',tool_calls=calls)]}

    def model(state):return update(client.chat.completions.create(**options(state)))
    async def async_model(state):return update(await client.chat.completions.create(**options(state)))

    graph=StateGraph(MessagesState)
    graph.add_node('model',async_model if asynchronous else model)
    # The existing host deliberately handles tool failures and lets the model finish.
    graph.add_node('tools',ToolNode([order_tool],handle_tool_errors=True))
    graph.add_edge(START,'model');graph.add_edge('tools','model')
    graph.add_conditional_edges('model',lambda state:'tools' if state['messages'][-1].tool_calls else END)
    return graph.compile()


def initial_state():return {'messages':[HumanMessage(content='Look up synthetic order demo-order.')]}


def business_view(state):return [message.model_dump(exclude={'id'}) for message in state['messages']]
