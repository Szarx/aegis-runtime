"""Configured graph drivers; original checkpoint and approval protocols remain authoritative."""
import inspect
from aegis_policy import identifier


class ManagedReviewedGraph:
    def __init__(self,application,driver):
        self._application=application;self._driver=driver
        self.node=application._guard(driver.node)
    def prepare(self,graph,config,*,summary,ttl_seconds=300):
        with self._application._lease():
            return self._driver.prepare(graph,config,summary=summary,ttl_seconds=ttl_seconds)
    def resume(self,graph,config,ticket):
        with self._application._lease():return self._driver.resume(graph,config,ticket)


class ManagedAsyncReviewedGraph:
    def __init__(self,application,driver):
        self._application=application;self._driver=driver
        self.node=application._guard(driver.node)
    async def prepare(self,graph,config,*,summary,ttl_seconds=300):
        with self._application._lease():
            return await self._driver.prepare(graph,config,summary=summary,ttl_seconds=ttl_seconds)
    async def resume(self,graph,config,ticket):
        with self._application._lease():return await self._driver.resume(graph,config,ticket)


def bind_reviewed_graph(application,function,*,client,name=None,disclose_arguments=False):
    with application._lock:
        if application._state!='active':raise RuntimeError('Application is not active')
        label=identifier(name if name is not None else function.__name__)
        binding=next((t for t in application._config.tools if t.name==label),None)
        if binding is None or binding.execution!='reviewed_graph' or label in application._bound:
            raise ValueError('Reviewed graph tool is unconfigured or already bound')
        options=dict(client=client,policy=application._config.policy,subject=application._runtime.subject,
            permission=binding.permission,tool=label,tool_revision=binding.tool_revision,graph_id=binding.graph.id,
            graph_revision=binding.graph.revision,node_name=binding.graph.node,disclose_arguments=disclose_arguments)
        if inspect.iscoroutinefunction(function):
            from .async_langgraph_reviewed import AsyncReviewedGraphTool
            wrapped=ManagedAsyncReviewedGraph(application,AsyncReviewedGraphTool(function,**options))
        else:
            from .langgraph_reviewed import ReviewedGraphTool
            wrapped=ManagedReviewedGraph(application,ReviewedGraphTool(function,**options))
        application._bound[label]=wrapped;return wrapped
