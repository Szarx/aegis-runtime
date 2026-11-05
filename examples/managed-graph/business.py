"""Business graph with injected model client and optional tool assembly; no Aegis imports."""
import json
from langchain_core.messages import AIMessage,HumanMessage,convert_to_openai_messages
from langchain_core.tools import StructuredTool
from langgraph.graph import MessagesState,StateGraph,START,END
from langgraph.prebuilt import ToolNode


def build(client,*,asynchronous=False,fail_tool=False,bind_tool=None):
    counts=dict(model_calls=0,tool_calls=0)
    def lookup_order(order_id:str)->dict:
        """Read one synthetic order, with no external business service."""
        counts['tool_calls']+=1
        if fail_tool:raise ValueError('synthetic private business failure')
        if order_id!='demo-order':raise ValueError('synthetic order required')
        return {'status':'shipped','source':'synthetic'}
    async def async_lookup_order(order_id:str)->dict:
        """Read one synthetic order asynchronously."""
        return lookup_order(order_id)
    function=async_lookup_order if asynchronous else lookup_order
    if bind_tool is not None:function=bind_tool(function,name='lookup_order')
    tool=StructuredTool.from_function(coroutine=function,name='lookup_order') if asynchronous else StructuredTool.from_function(function,name='lookup_order')
    tools=[{'type':'function','function':{'name':'lookup_order','description':'Read synthetic order','parameters':{
        'type':'object','properties':{'order_id':{'type':'string'}},'required':['order_id']}}}]
    def options(state):
        first=isinstance(state['messages'][-1],HumanMessage)
        return dict(model='offline-deepseek',messages=convert_to_openai_messages(state['messages']),tools=tools,
            tool_choice={'type':'function','function':{'name':'lookup_order'}} if first else 'none',max_tokens=128,
            extra_body={'thinking':{'type':'disabled'}})
    def update(response):
        message=response.choices[0].message
        return {'messages':[AIMessage(content=message.content or '',tool_calls=[dict(name=c.function.name,args=json.loads(c.function.arguments),id=c.id,type='tool_call') for c in message.tool_calls or []])]}
    def model(state):counts['model_calls']+=1;return update(client.chat.completions.create(**options(state)))
    async def async_model(state):counts['model_calls']+=1;return update(await client.chat.completions.create(**options(state)))
    graph=StateGraph(MessagesState);graph.add_node('model',async_model if asynchronous else model)
    graph.add_node('tools',ToolNode([tool],handle_tool_errors=True));graph.add_edge(START,'model')
    graph.add_conditional_edges('model',lambda state:'tools' if state['messages'][-1].tool_calls else END)
    graph.add_edge('tools','model')
    return graph.compile(),counts


def initial():return {'messages':[HumanMessage(content='Look up synthetic order demo-order.')]}


def normalize(value):
    if hasattr(value,'model_dump'):return value.model_dump(exclude={'id'})
    if isinstance(value,dict):return {key:normalize(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [normalize(item) for item in value]
    return value
