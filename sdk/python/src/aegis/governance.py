"""Governance telemetry only. Authorization belongs to the caller's Runtime."""

import asyncio
from contextlib import contextmanager
import re

from opentelemetry import context, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .tracing.client import current_sdk
from .tracing.context import _AGENT_NAME
from .tracing.semantics import GOVERNANCE_MAPPING_VERSION, validate_label


@contextmanager
def governed_tool_span(name, *, permission, subject, action_id, effect, reason,
                       policy_revision=None, rule_id=None, approval_phase=None):
    validate_label(name,'tool name')
    if not re.fullmatch('[0-9a-f]{32}',action_id) or not int(action_id,16):
        raise ValueError('invalid action identifier')
    if effect not in ('allow','deny','require_approval') or reason not in ('explicit_allow','explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error','explicit_require_approval'):
        raise ValueError('invalid governance metadata')
    if effect=='require_approval':
        if reason!='explicit_require_approval' or approval_phase not in ('request','execute'): raise ValueError('invalid approval phase')
    elif approval_phase is not None: raise ValueError('unexpected approval phase')
    span=token=None
    sdk=None
    try:
        sdk=current_sdk()
        if sdk is not None:
            attrs={'gen_ai.operation.name':'execute_tool','gen_ai.tool.name':name,
                   'aegis.mapping.version':'aegis.governance.v2' if effect=='require_approval' else GOVERNANCE_MAPPING_VERSION,'aegis.action.id':action_id,
                   'aegis.decision.effect':effect,'aegis.decision.reason':reason}
            if approval_phase is not None: attrs['aegis.approval.phase']=approval_phase
            optional={'gen_ai.agent.name':context.get_value(_AGENT_NAME),'aegis.tool.permission':permission,
                      'aegis.subject.id':subject,'aegis.policy.revision':policy_revision,'aegis.decision.rule_id':rule_id}
            attrs.update({key:value for key,value in optional.items() if value is not None})
            span=sdk.tracer.start_span(f'execute_tool {name}',kind=SpanKind.INTERNAL,attributes=attrs)
            token=context.attach(trace.set_span_in_context(span))
    except Exception:
        if sdk is not None: sdk.instrumentation_failed()
    outcome='denied' if effect=='deny' else 'awaiting_approval' if approval_phase=='request' else 'completed'
    try:
        yield span
    except BaseException as error:
        outcome='denied' if effect=='deny' else 'cancelled' if isinstance(error,asyncio.CancelledError) else 'error'
        if span is not None:
            try:
                kind=f'{type(error).__module__}.{type(error).__qualname__}'[:256]
                span.set_attribute('error.type',kind)
                span.set_status(Status(StatusCode.ERROR))
                span.add_event('exception',{'exception.type':kind})
            except Exception:
                sdk.instrumentation_failed()
        raise
    finally:
        if token is not None:
            try: context.detach(token)
            except Exception: sdk.instrumentation_failed()
        if span is not None:
            try: span.set_attribute('aegis.action.outcome',outcome)
            except Exception: sdk.instrumentation_failed()
            try: span.end()
            except Exception: sdk.instrumentation_failed()


__all__=['governed_tool_span']
