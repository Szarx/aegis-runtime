"""Optional, explicit call and stream instrumentation for compiled StateGraph."""

try:
    from langgraph.graph.state import CompiledStateGraph
    from langchain_core.runnables import RunnableBinding
except ImportError:
    raise ImportError("LangGraph integration requires the SDK langgraph extra") from None

from .tracing.context import operation_span
from .tracing.semantics import validate_label
from .integrations.langgraph.streaming import observe_stream


class _ObservedGraph:
    def __init__(self, graph, name):
        self._graph, self._name = graph, name

    def __getattr__(self, name):
        return getattr(self._graph, name)

    def invoke(self, *args, **kwargs):
        with operation_span("invoke_agent", self._name, None):
            return self._graph.invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        with operation_span("invoke_agent", self._name, None):
            return await self._graph.ainvoke(*args, **kwargs)

    def with_config(self, *args, **kwargs):
        return observe_graph(self._graph.with_config(*args, **kwargs), name=self._name)

    def stream(self, *args, **kwargs):
        return observe_stream(self._graph.stream(*args, **kwargs), self._name)

    def astream(self, *args, **kwargs):
        return observe_stream(self._graph.astream(*args, **kwargs), self._name, asynchronous=True)


def observe_graph(graph, *, name=None):
    """Return a proxy; other graph APIs delegate without an Agent span."""
    if isinstance(graph, _ObservedGraph):
        if name is not None and name != graph._name:
            raise ValueError("graph is already observed with a different name")
        return graph
    target = graph
    while isinstance(target, RunnableBinding):
        target = target.bound
    if not isinstance(target, CompiledStateGraph):
        raise TypeError("observe_graph requires a compiled LangGraph StateGraph")
    label = validate_label("langgraph-agent" if name is None else name, "name")
    if "\x00" in label:
        raise ValueError("name must not contain NUL")
    return _ObservedGraph(graph, label)


__all__ = ["observe_graph"]
