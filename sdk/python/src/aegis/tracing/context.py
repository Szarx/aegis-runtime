"""Privacy-preserving context around exactly one business invocation."""

from contextlib import contextmanager

from opentelemetry import context, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .client import current_sdk
from .semantics import MAPPING_VERSION

_AGENT_NAME = context.create_key("aegis-agent-name")


@contextmanager
def operation_span(operation: str, name: str, permission: str | None):
    sdk = current_sdk()
    if sdk is None:
        yield
        return
    span = None
    token = None
    try:
        attributes = {
            "gen_ai.operation.name": operation,
            "aegis.mapping.version": MAPPING_VERSION,
        }
        agent_name = name if operation == "invoke_agent" else context.get_value(_AGENT_NAME)
        if agent_name is not None:
            attributes["gen_ai.agent.name"] = agent_name
        if operation == "execute_tool":
            attributes["gen_ai.tool.name"] = name
            if permission is not None:
                attributes["aegis.tool.permission"] = permission
        span = sdk.tracer.start_span(
            f"{operation} {name}", kind=SpanKind.INTERNAL, attributes=attributes
        )
        active_context = trace.set_span_in_context(span)
        if operation == "invoke_agent":
            active_context = context.set_value(_AGENT_NAME, name, active_context)
        token = context.attach(active_context)
    except Exception:
        sdk.instrumentation_failed()
        if span is not None:
            try:
                span.end()
            except Exception:
                sdk.instrumentation_failed()
        span = None
    try:
        yield
    except BaseException as error:
        if span is not None:
            try:
                error_type = f"{type(error).__module__}.{type(error).__qualname__}"[:256]
                span.set_attribute("error.type", error_type)
                span.set_status(Status(StatusCode.ERROR))
                span.add_event("exception", {"exception.type": error_type})
            except Exception:
                sdk.instrumentation_failed()
        raise
    finally:
        if token is not None:
            try:
                context.detach(token)
            except Exception:
                sdk.instrumentation_failed()
        if span is not None:
            try:
                span.end()
            except Exception:
                sdk.instrumentation_failed()
