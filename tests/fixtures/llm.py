from .otlp import first_span, request_for


def llm_request(*, trace=1, span=2, parent=1):
    request = request_for(trace=trace, span=span, parent=parent)
    step = first_span(request)
    step.kind, step.name = 3, "chat offline-model"
    step.ClearField("attributes")
    for key, value in {
        "gen_ai.operation.name":"chat", "aegis.mapping.version":"aegis.genai.v2",
        "gen_ai.agent.name":"demo-agent", "gen_ai.provider.name":"openai",
        "gen_ai.request.model":"offline-model", "gen_ai.response.model":"offline-model",
        "aegis.call.api":"responses", "aegis.call.mode":"non_stream", "aegis.call.outcome":"completed",
    }.items():
        step.attributes.add(key=key).value.string_value = value
    step.attributes.add(key="gen_ai.usage.input_tokens").value.int_value = 7
    step.attributes.add(key="gen_ai.usage.output_tokens").value.int_value = 0
    return request
