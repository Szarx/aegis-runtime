from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

BASE_TIME = 1_790_000_000_000_000_000


def request_for(
    *, trace=1, span=1, parent=None, operation="invoke_agent", agent="demo-agent",
    service="demo-service", start=100, end=300, error=False,
):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add()
    resource.resource.attributes.add(key="service.name").value.string_value = service
    scope = resource.scope_spans.add()
    scope.scope.name = "aegis"
    scope.scope.version = "0.1.0.dev0"
    label = agent if operation == "invoke_agent" else "lookup"
    step = scope.spans.add(
        trace_id=trace.to_bytes(16, "big"), span_id=span.to_bytes(8, "big"),
        parent_span_id=parent.to_bytes(8, "big") if parent is not None else b"",
        name=f"{operation} {label}", kind=1,
        start_time_unix_nano=BASE_TIME + start, end_time_unix_nano=BASE_TIME + end,
    )
    attributes = {
        "gen_ai.operation.name": operation,
        "gen_ai.agent.name": agent,
        "aegis.mapping.version": "aegis.genai.v1",
    }
    if operation == "execute_tool":
        attributes.update({"gen_ai.tool.name": label, "aegis.tool.permission": "orders.read"})
    if error:
        attributes["error.type"] = "builtins.LookupError"
        step.status.code = 2
        event = step.events.add(name="exception", time_unix_nano=BASE_TIME + end - 1)
        event.attributes.add(key="exception.type").value.string_value = "builtins.LookupError"
    for key, value in attributes.items():
        step.attributes.add(key=key).value.string_value = value
    return request


def first_span(request):
    return request.resource_spans[0].scope_spans[0].spans[0]


def combine(*requests):
    result = ExportTraceServiceRequest()
    for request in requests:
        result.resource_spans.extend(request.resource_spans)
    return result
