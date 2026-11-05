"""Application leases around the original reviewed-execution protocols."""
import inspect
from aegis_policy import identifier
from .reviewed_execution import ReviewedTool


class ManagedReviewedTool:
    def __init__(self,application,reviewed):self._application=application;self._reviewed=reviewed
    def prepare(self,arguments,*,summary,action_id=None,ttl_seconds=300):
        with self._application._lease():
            return self._reviewed.prepare(arguments,summary=summary,action_id=action_id,ttl_seconds=ttl_seconds)
    def resume(self,action_id,arguments,*,summary,ttl_seconds=300):
        with self._application._lease():
            return self._reviewed.resume(action_id,arguments,summary=summary,ttl_seconds=ttl_seconds)


class ManagedAsyncReviewedTool:
    def __init__(self,application,reviewed):self._application=application;self._reviewed=reviewed
    async def prepare(self,arguments,*,summary,action_id=None,ttl_seconds=300):
        with self._application._lease():
            return await self._reviewed.prepare(arguments,summary=summary,action_id=action_id,ttl_seconds=ttl_seconds)
    async def resume(self,action_id,arguments,*,summary,ttl_seconds=300):
        with self._application._lease():
            return await self._reviewed.resume(action_id,arguments,summary=summary,ttl_seconds=ttl_seconds)


def bind_reviewed(application,function,*,client,name=None,disclose_arguments=False):
    with application._lock:
        if application._state!='active':raise RuntimeError('Application is not active')
        label=identifier(name if name is not None else function.__name__)
        bindings={t.name:t for t in application._config.tools}
        binding=bindings.get(label)
        if binding is None or binding.execution!='reviewed' or label in application._bound:
            raise ValueError('Reviewed tool is unconfigured or already bound')
        options=dict(client=client,policy=application._config.policy,subject=application._runtime.subject,
            permission=binding.permission,tool=label,tool_revision=binding.tool_revision,disclose_arguments=disclose_arguments)
        if inspect.iscoroutinefunction(function):
            from .async_reviewed_execution import AsyncReviewedTool
            wrapped=ManagedAsyncReviewedTool(application,AsyncReviewedTool(function,**options))
        else:wrapped=ManagedReviewedTool(application,ReviewedTool(function,**options))
        application._bound[label]=wrapped;return wrapped
