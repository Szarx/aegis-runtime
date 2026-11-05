"""Supported OTLP subset frozen by SPEC-002; no dependency on SDK internals."""

from dataclasses import asdict, dataclass
import re

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

MAX_BODY_BYTES = 1024 * 1024
MAX_SPANS = 512
MAX_NANO = 2**63 - 1
SPAN_KEYS = frozenset({
    "gen_ai.operation.name", "gen_ai.agent.name", "gen_ai.tool.name",
    "aegis.tool.permission", "aegis.mapping.version", "error.type",
})
RESOURCE_KEYS = frozenset({
    "service.name", "telemetry.sdk.name", "telemetry.sdk.language", "telemetry.sdk.version",
})
GRAPH_KEYS = (SPAN_KEYS - {"gen_ai.tool.name", "aegis.tool.permission"}) | frozenset({"aegis.graph.mode", "aegis.graph.outcome"})
GOVERNANCE_KEYS = SPAN_KEYS | frozenset({'aegis.action.id','aegis.subject.id','aegis.policy.revision',
    'aegis.decision.rule_id','aegis.decision.effect','aegis.decision.reason','aegis.action.outcome'})
APPROVAL_GOVERNANCE_KEYS = GOVERNANCE_KEYS | frozenset({'aegis.approval.phase'})
TOKEN_KEYS = frozenset({"gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"})
LLM_KEYS = (SPAN_KEYS - {"gen_ai.tool.name", "aegis.tool.permission"}) | TOKEN_KEYS | frozenset({
    "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model",
    "aegis.call.api", "aegis.call.mode", "aegis.call.outcome",
})


class InvalidPayload(ValueError):
    pass


class TooManySpans(ValueError):
    pass


class InvalidSpan(ValueError):
    pass


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    operation: str
    kind: str
    status: str
    service_name: str
    agent_name: str | None
    start_time_ns: int
    end_time_ns: int
    resource: dict[str, str]
    scope: dict[str, str]
    attributes: dict[str, str | int]
    events: list[dict]
    resource_schema_url: str
    scope_schema_url: str

    def public(self) -> dict:
        data = asdict(self)
        data["start_time_unix_nano"] = data.pop("start_time_ns")
        data["end_time_unix_nano"] = data.pop("end_time_ns")
        return data


def string(value: str, maximum: int, *, allow_empty: bool = False) -> str:
    if "\x00" in value or len(value) > maximum or (not allow_empty and not value.strip()):
        raise InvalidSpan("invalid metadata string")
    return value


def attributes(values, allowed: frozenset[str], *, maximum_count: int = 64, tokens: bool = False) -> dict[str, str | int]:
    if len(values) > maximum_count:
        raise InvalidSpan("too many attributes")
    result = {}
    for item in values:
        if item.key not in allowed:
            continue
        if item.key in result:
            raise InvalidSpan("invalid retained attribute")
        if tokens and item.key in TOKEN_KEYS:
            if item.value.WhichOneof("value") != "int_value" or item.value.int_value < 0:
                raise InvalidSpan("invalid token count")
            result[item.key] = item.value.int_value
        else:
            if item.value.WhichOneof("value") != "string_value":
                raise InvalidSpan("invalid retained attribute")
            result[item.key] = string(item.value.string_value, 256)
    return result


def identifier(value: bytes, length: int, *, optional: bool = False) -> str | None:
    if not value and optional:
        return None
    if len(value) != length or not any(value):
        raise InvalidSpan("invalid span identifier")
    return value.hex()


def governance_metadata(attrs, status):
    effect,reason,outcome=(attrs.get(key) for key in ('aegis.decision.effect','aegis.decision.reason','aegis.action.outcome'))
    reasons={'explicit_allow','explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error'}
    action=attrs.get('aegis.action.id','')
    if not re.fullmatch('[0-9a-f]{32}',action) or not int(action,16): raise InvalidSpan('invalid action identifier')
    approval=attrs.get('aegis.mapping.version')=='aegis.governance.v2'
    if approval:
        phase=attrs.get('aegis.approval.phase')
        if effect!='require_approval' or reason!='explicit_require_approval' or phase not in ('request','execute'):
            raise InvalidSpan('invalid approval decision')
        allowed=('awaiting_approval','error','cancelled') if phase=='request' else ('completed','error','cancelled')
        if outcome not in allowed: raise InvalidSpan('invalid approval outcome')
    else:
        if effect not in ('allow','deny') or reason not in reasons or (effect=='allow')!=(reason=='explicit_allow'):
            raise InvalidSpan('invalid governance decision')
        if outcome not in ('completed','error','cancelled','denied') or (effect=='deny')!=(outcome=='denied'):
            raise InvalidSpan('invalid governance outcome')
    if (status=='ERROR')!=(outcome not in ('completed','awaiting_approval')) or (status=='UNSET' and 'error.type' in attrs):
        raise InvalidSpan('inconsistent governance status')
    for key in ('gen_ai.tool.name','aegis.tool.permission','aegis.subject.id','aegis.policy.revision','aegis.decision.rule_id'):
        if key in attrs and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',attrs[key]):
            raise InvalidSpan('invalid governance label')
    subject='aegis.subject.id' in attrs
    permission='aegis.tool.permission' in attrs
    revision='aegis.policy.revision' in attrs
    if (reason=='identity_missing') != (not subject): raise InvalidSpan('inconsistent governance subject')
    if reason=='permission_missing' and permission: raise InvalidSpan('inconsistent governance permission')
    if reason not in ('identity_missing','permission_missing') and not permission: raise InvalidSpan('missing governance permission')
    if reason=='policy_unavailable' and revision: raise InvalidSpan('inconsistent governance policy')
    if reason in ('explicit_allow','explicit_deny','explicit_require_approval','no_match','policy_error') and not revision: raise InvalidSpan('missing governance policy')
    if (reason in ('explicit_allow','explicit_deny','explicit_require_approval'))!=('aegis.decision.rule_id' in attrs):
        raise InvalidSpan('inconsistent governance rule')


def normalize(resource_spans, scope_spans, span) -> SpanRecord:
    resource = attributes(resource_spans.resource.attributes, RESOURCE_KEYS)
    service = string(resource.get("service.name", ""), 128)
    scope = {
        "name": string(scope_spans.scope.name, 64),
        "version": string(scope_spans.scope.version, 64),
    }
    if scope["name"] != "aegis":
        raise InvalidSpan("unsupported scope")
    llm = span.kind == 3
    graph = any(item.key == "aegis.mapping.version" and item.value.string_value == "aegis.graph.v1" for item in span.attributes)
    governance = any(item.key == 'aegis.mapping.version' and item.value.string_value in ('aegis.governance.v1','aegis.governance.v2') for item in span.attributes)
    attrs = attributes(span.attributes, LLM_KEYS if llm else APPROVAL_GOVERNANCE_KEYS if governance and any(item.key=='aegis.mapping.version' and item.value.string_value=='aegis.governance.v2' for item in span.attributes) else GOVERNANCE_KEYS if governance else GRAPH_KEYS if graph else SPAN_KEYS, tokens=llm)
    operation = attrs.get("gen_ai.operation.name")
    if llm:
        if operation != "chat" or attrs.get("aegis.mapping.version") != "aegis.genai.v2":
            raise InvalidSpan("unsupported model mapping")
        provider = attrs.get("gen_ai.provider.name")
        api = attrs.get("aegis.call.api")
        if provider not in ("openai", "deepseek") or api not in ("responses", "chat.completions") or (provider == "deepseek" and api != "chat.completions") or attrs.get("aegis.call.mode") not in ("stream", "non_stream") or attrs.get("aegis.call.outcome") not in ("completed", "incomplete", "closed", "cancelled", "error"):
            raise InvalidSpan("invalid model metadata")
        for key in ("gen_ai.request.model", "gen_ai.response.model"):
            if key in attrs:
                string(attrs[key], 128)
    elif governance:
        if operation != 'execute_tool': raise InvalidSpan('unsupported governance operation')
    elif graph:
        if operation != "invoke_agent" or attrs.get("aegis.graph.mode") not in ("stream", "astream") or attrs.get("aegis.graph.outcome") not in ("completed", "closed", "error", "cancelled"):
            raise InvalidSpan("unsupported graph mapping")
    elif operation not in ("invoke_agent", "execute_tool") or attrs.get("aegis.mapping.version") != "aegis.genai.v1":
        raise InvalidSpan("unsupported native mapping")
    agent = string(attrs["gen_ai.agent.name"], 128) if "gen_ai.agent.name" in attrs else None
    label_key = "gen_ai.request.model" if llm else "gen_ai.agent.name" if operation == "invoke_agent" else "gen_ai.tool.name"
    label = string(attrs.get(label_key, ""), 128)
    if "aegis.tool.permission" in attrs:
        string(attrs["aegis.tool.permission"], 128)
    if span.kind != (3 if llm else 1) or span.name != f"{operation} {label}":
        raise InvalidSpan("unsupported kind or name")
    if not 0 < span.start_time_unix_nano <= span.end_time_unix_nano <= MAX_NANO:
        raise InvalidSpan("invalid span times")
    if span.status.code not in (0, 1, 2):
        raise InvalidSpan("invalid span status")
    status = "ERROR" if span.status.code == 2 else "UNSET"
    if governance: governance_metadata(attrs,status)
    if llm and ((status == "ERROR") != (attrs["aegis.call.outcome"] in ("error", "cancelled"))):
        raise InvalidSpan("inconsistent model outcome")
    if graph and ((status == "ERROR") != (attrs["aegis.graph.outcome"] in ("error", "cancelled"))):
        raise InvalidSpan("inconsistent graph outcome")
    if status == "ERROR" and "error.type" not in attrs:
        raise InvalidSpan("missing error type")
    if len(span.events) > 16:
        raise InvalidSpan("too many events")
    events = []
    for event in span.events:
        if event.name != "exception":
            continue
        event_attrs = attributes(event.attributes, frozenset({"exception.type"}))
        if event_attrs.get("exception.type") != attrs.get("error.type") or "exception.type" not in event_attrs:
            raise InvalidSpan("invalid exception metadata")
        if not span.start_time_unix_nano <= event.time_unix_nano <= span.end_time_unix_nano:
            raise InvalidSpan("invalid event time")
        events.append({"name": "exception", "time_unix_nano": event.time_unix_nano, "attributes": event_attrs})
    return SpanRecord(
        trace_id=identifier(span.trace_id, 16),
        span_id=identifier(span.span_id, 8),
        parent_span_id=identifier(span.parent_span_id, 8, optional=True),
        name=span.name,
        operation=operation,
        kind="CLIENT" if llm else "INTERNAL",
        status=status,
        service_name=service,
        agent_name=agent,
        start_time_ns=span.start_time_unix_nano,
        end_time_ns=span.end_time_unix_nano,
        resource=resource,
        scope=scope,
        attributes=attrs,
        events=events,
        resource_schema_url=string(resource_spans.schema_url, 256, allow_empty=True),
        scope_schema_url=string(scope_spans.schema_url, 256, allow_empty=True),
    )


def decode(body: bytes) -> tuple[list[SpanRecord], int]:
    request = ExportTraceServiceRequest()
    try:
        request.ParseFromString(body)
    except DecodeError:
        raise InvalidPayload("invalid protobuf") from None
    count = sum(len(scope.spans) for resource in request.resource_spans for scope in resource.scope_spans)
    if count > MAX_SPANS:
        raise TooManySpans("batch span limit exceeded")
    accepted = []
    rejected = 0
    for resource in request.resource_spans:
        for scope in resource.scope_spans:
            for span in scope.spans:
                try:
                    accepted.append(normalize(resource, scope, span))
                except InvalidSpan:
                    rejected += 1
    return accepted, rejected
