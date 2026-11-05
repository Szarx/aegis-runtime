from .otlp import first_span,request_for


def graph_request(*,outcome='completed',mode='stream',trace=1,span=1):
    request=request_for(trace=trace,span=span)
    step=first_span(request)
    step.name='invoke_agent stream-agent'
    step.ClearField('attributes')
    for key,value in {'aegis.mapping.version':'aegis.graph.v1','gen_ai.operation.name':'invoke_agent','gen_ai.agent.name':'stream-agent','aegis.graph.mode':mode,'aegis.graph.outcome':outcome}.items():
        step.attributes.add(key=key).value.string_value=value
    if outcome in ('error','cancelled'):
        step.status.code=2
        step.attributes.add(key='error.type').value.string_value='builtins.RuntimeError' if outcome=='error' else 'asyncio.exceptions.CancelledError'
    return request
