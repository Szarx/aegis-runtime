"""Explicit policy routing; a pending record never authorizes execution."""
from contextlib import nullcontext
from dataclasses import dataclass
import inspect
import json
import uuid

from aegis.governance import governed_tool_span
from . import ActionDenied
from .approvals import ApprovalUnavailable
from .reviewed_execution import ReviewedTool


@dataclass(frozen=True, slots=True)
class PendingReview:
    record: dict
    kind: str = 'pending_review'


class _PolicyCore:
    _application = None

    def _scope(self):
        return self._application._lease() if self._application is not None else nullcontext()

    def _decision(self):
        core = self._reviewed
        return core._runtime._decide(core._tool, core._permission)

    def _direct_allow(self, action):
        decision=self._decision()
        if decision.effect!='allow':raise ActionDenied(decision,action)

    def _span(self, action, decision):
        core = self._reviewed
        return governed_tool_span(core._tool, permission=core._permission, subject=core._runtime.subject,
            action_id=action, effect=decision.effect, reason=decision.reason,
            policy_revision=decision.policy_revision, rule_id=decision.rule_id,
            approval_phase='request' if decision.effect=='require_approval' else None)

    def _ticket(self, record, arguments, summary, ttl_seconds):
        try:
            if type(record) is not dict: raise ApprovalUnavailable()
            origin = {key:record[key] for key in ('trace_id','span_id')}
            payload = self._reviewed._prepare(record['action_id'], arguments, summary, ttl_seconds, **origin)
            self._reviewed._client._record(payload, record)
            return payload['action_id'], origin
        except ActionDenied:
            raise
        except Exception:
            raise ApprovalUnavailable() from None


class PolicyTool(_PolicyCore):
    def __init__(self, function, **options):
        self._reviewed = ReviewedTool(function, **options)

    def invoke(self, arguments, *, summary, action_id=None, ttl_seconds=300):
        with self._scope():
            action = uuid.uuid4().hex if action_id is None else action_id
            decision = self._decision()
            with self._span(action, decision) as span:
                if decision.effect=='deny': raise ActionDenied(decision,action)
                if decision.effect=='require_approval':
                    record = self._reviewed.prepare(arguments, summary=summary, action_id=action,
                        ttl_seconds=ttl_seconds)
                    return PendingReview(json.loads(json.dumps(record)))
                payload = self._reviewed._prepare(action,arguments,summary,ttl_seconds)
                self._direct_allow(action)
                return self._reviewed._function(**payload['review_arguments'])

    def resume(self, record, arguments, *, summary, ttl_seconds=300):
        with self._scope():
            action, origin = self._ticket(record,arguments,summary,ttl_seconds)
            return self._reviewed.resume(action,arguments,summary=summary,ttl_seconds=ttl_seconds,**origin)


class AsyncPolicyTool(_PolicyCore):
    def __init__(self, function, **options):
        from .async_reviewed_execution import AsyncReviewedTool
        self._reviewed = AsyncReviewedTool(function, **options)

    async def invoke(self, arguments, *, summary, action_id=None, ttl_seconds=300):
        with self._scope():
            action = uuid.uuid4().hex if action_id is None else action_id
            decision = self._decision()
            with self._span(action, decision) as span:
                if decision.effect=='deny': raise ActionDenied(decision,action)
                if decision.effect=='require_approval':
                    record = await self._reviewed.prepare(arguments,summary=summary,action_id=action,
                        ttl_seconds=ttl_seconds)
                    return PendingReview(json.loads(json.dumps(record)))
                payload = self._reviewed._prepare(action,arguments,summary,ttl_seconds)
                self._direct_allow(action)
                return await self._reviewed._function(**payload['review_arguments'])

    async def resume(self, record, arguments, *, summary, ttl_seconds=300):
        with self._scope():
            action, origin = self._ticket(record,arguments,summary,ttl_seconds)
            return await self._reviewed.resume(action,arguments,summary=summary,ttl_seconds=ttl_seconds,**origin)


def bind_policy(application,function,*,client,name=None,disclose_arguments=False):
    from aegis_policy import identifier
    with application._lock:
        if application._state!='active': raise RuntimeError('Application is not active')
        label=identifier(name if name is not None else function.__name__)
        binding=next((tool for tool in application._config.tools if tool.name==label),None)
        if binding is None or binding.execution!='policy' or label in application._bound:
            raise ValueError('Policy tool is unconfigured or already bound')
        wrapped=(AsyncPolicyTool if inspect.iscoroutinefunction(function) else PolicyTool)(function,
            client=client,policy=application._config.policy,subject=application._runtime.subject,
            permission=binding.permission,tool=label,tool_revision=binding.tool_revision,disclose_arguments=disclose_arguments)
        wrapped._application=application
        application._bound[label]=wrapped
        return wrapped
