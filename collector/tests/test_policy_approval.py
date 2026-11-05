import copy
import unittest
from aegis_collector.ingestion.otlp import decode
from tests.fixtures.governance import governance_request
from tests.fixtures.otlp import first_span


def approval_request(phase='request',outcome='awaiting_approval'):
    request=governance_request(effect='allow',outcome='completed')
    step=first_span(request)
    values={item.key:item.value.string_value for item in step.attributes}
    values.update({'aegis.mapping.version':'aegis.governance.v2','aegis.decision.effect':'require_approval',
        'aegis.decision.reason':'explicit_require_approval','aegis.approval.phase':phase,'aegis.action.outcome':outcome})
    if outcome in ('error','cancelled'):
        step.status.code=2;values['error.type']='builtins.RuntimeError'
    step.ClearField('attributes')
    for key,value in values.items():step.attributes.add(key=key).value.string_value=value
    return request


class ApprovalGovernanceProtocol(unittest.TestCase):
    def test_phase_status_outcome_matrix_accepts_only_consistent_records(self):
        for phase,outcome in [('request','awaiting_approval'),('execute','completed'),('request','error'),('execute','error'),('execute','cancelled')]:
            accepted,rejected=decode(approval_request(phase,outcome).SerializeToString())
            self.assertEqual((len(accepted),rejected),(1,0))
            self.assertEqual(accepted[0].attributes['aegis.approval.phase'],phase)
        for phase,outcome in [('execute','awaiting_approval'),('request','completed'),('unknown','completed')]:
            self.assertEqual(decode(approval_request(phase,outcome).SerializeToString()),([],1))

    def test_legacy_mapping_cannot_smuggle_new_effect_and_missing_rule_is_rejected(self):
        for key,value in [('aegis.mapping.version','aegis.governance.v1'),('aegis.decision.rule_id',''),('aegis.decision.reason','explicit_allow'),('aegis.subject.id','')]:
            request=approval_request();step=first_span(request)
            for item in step.attributes:
                if item.key==key:item.value.string_value=value
            self.assertEqual(decode(request.SerializeToString()),([],1))
        request=approval_request();first_span(request).status.code=2
        self.assertEqual(decode(request.SerializeToString()),([],1))
