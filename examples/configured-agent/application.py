"""Ordinary synthetic business functions and a real LangGraph; no Aegis imports."""
import inspect


def make_tool(counter,asynchronous=False):
    def lookup_order(order_id:str)->dict:
        """Return one synthetic order; no business service access."""
        counter['calls']+=1
        if order_id!='demo':raise ValueError('synthetic invalid order')
        return {'order_id':order_id,'status':'shipped'}
    if not asynchronous:return lookup_order
    async def async_lookup_order(order_id:str)->dict:
        """Return one synthetic order; no business service access."""
        return lookup_order(order_id)
    async_lookup_order.__name__='lookup_order'
    return async_lookup_order


def build_graph(tool):
    from langchain_core.messages import AIMessage
    from langchain_core.tools import StructuredTool
    from langgraph.graph import StateGraph,MessagesState,START,END
    from langgraph.prebuilt import ToolNode
    structured=StructuredTool.from_function(coroutine=tool) if inspect.iscoroutinefunction(tool) else StructuredTool.from_function(tool)
    def request(state):return {'messages':[AIMessage(content='',tool_calls=[dict(name='lookup_order',args={'order_id':'demo'},id='synthetic-call',type='tool_call')])]}
    def finish(state):return {'messages':[AIMessage(content='done')]}
    graph=StateGraph(MessagesState);graph.add_node('request',request);graph.add_node('tools',ToolNode([structured],handle_tool_errors=True));graph.add_node('finish',finish)
    graph.add_edge(START,'request');graph.add_edge('request','tools');graph.add_edge('tools','finish');graph.add_edge('finish',END)
    return graph.compile()


def business_view(state):return [m.model_dump(exclude={'id'}) for m in state['messages']]
