"""Explicit tool control using a host-bound identity and policy snapshot."""

from dataclasses import dataclass
from functools import wraps
import inspect
import uuid

from aegis.governance import governed_tool_span
from aegis_policy import Policy, Decision
from aegis_policy import identifier


class ActionDenied(PermissionError):
    def __init__(self, decision, action_id):
        super().__init__('Tool invocation denied by Aegis runtime')
        self._decision, self._action_id = decision, action_id

    @property
    def decision(self): return self._decision

    @property
    def action_id(self): return self._action_id


@dataclass(frozen=True, slots=True)
class Runtime:
    policy: Policy | None = None
    subject: str | None = None

    def __post_init__(self):
        if self.policy is not None and type(self.policy) is not Policy:
            raise ValueError('Runtime requires a validated Policy')
        if self.subject is not None: identifier(self.subject)

    def _decide(self, name, permission):
        revision=self.policy.revision if self.policy else None
        if self.subject is None: return Decision('deny','identity_missing',revision)
        if permission is None: return Decision('deny','permission_missing',revision)
        if self.policy is None: return Decision('deny','policy_unavailable')
        try:
            result=self.policy.evaluate(subject=self.subject,tool=name,permission=permission)
            if type(result) is not Decision or result.policy_revision!=revision:
                raise ValueError('invalid policy result')
            return result
        except Exception:
            return Decision('deny','policy_error',revision)

    def tool(self, function=None, *, permission=None, name=None):
        if permission is not None: identifier(permission)
        def decorate(fn):
            if inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn):
                raise TypeError('Runtime tool requires a regular sync or async function')
            label=identifier(name if name is not None else fn.__name__)

            def prepare():
                decision=self._decide(label,permission)
                action_id=uuid.uuid4().hex
                span=governed_tool_span(label,permission=permission,subject=self.subject,
                    action_id=action_id,effect=decision.effect,reason=decision.reason,
                    policy_revision=decision.policy_revision,rule_id=decision.rule_id,
                    approval_phase='request' if decision.effect=='require_approval' else None)
                return decision,action_id,span

            if inspect.iscoroutinefunction(fn):
                @wraps(fn)
                async def wrapped(*args,**kwargs):
                    decision,action_id,span=prepare()
                    with span:
                        if decision.effect!='allow': raise ActionDenied(decision,action_id)
                        return await fn(*args,**kwargs)
            else:
                @wraps(fn)
                def wrapped(*args,**kwargs):
                    decision,action_id,span=prepare()
                    with span:
                        if decision.effect!='allow': raise ActionDenied(decision,action_id)
                        return fn(*args,**kwargs)
            return wrapped
        return decorate(function) if function is not None else decorate


__all__=['Runtime','ActionDenied']
