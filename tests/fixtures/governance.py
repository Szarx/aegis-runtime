from .otlp import request_for,first_span


def governance_request(*,trace=1,span=2,parent=1,effect='deny',reason='explicit_deny',outcome=None):
    request=request_for(trace=trace,span=span,parent=parent,operation='execute_tool')
    step=first_span(request)
    step.ClearField('attributes')
    attrs={'gen_ai.operation.name':'execute_tool','gen_ai.tool.name':'lookup','gen_ai.agent.name':'demo-agent',
        'aegis.mapping.version':'aegis.governance.v1','aegis.action.id':f'{span:032x}',
        'aegis.decision.effect':effect,'aegis.decision.reason':reason,
        'aegis.action.outcome':outcome or ('denied' if effect=='deny' else 'completed')}
    if reason!='identity_missing':attrs['aegis.subject.id']='reader'
    if reason!='permission_missing':attrs['aegis.tool.permission']='orders.read'
    if reason!='policy_unavailable':attrs['aegis.policy.revision']='v1'
    if reason in ('explicit_allow','explicit_deny'):attrs['aegis.decision.rule_id']='read'
    if attrs['aegis.action.outcome']!='completed':
        step.status.code=2;attrs['error.type']='aegis_runtime.ActionDenied' if effect=='deny' else 'builtins.ValueError'
    for key,value in attrs.items():step.attributes.add(key=key).value.string_value=value
    return request
