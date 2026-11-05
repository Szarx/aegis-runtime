import unittest
from aegis_collector.ingestion.otlp import decode
from tests.fixtures.governance import governance_request
from tests.fixtures.otlp import first_span,request_for,combine
from tests.fixtures.llm import llm_request
from tests.fixtures.graph_stream import graph_request


class GovernanceProtocol(unittest.TestCase):
    def test_all_decisions_and_old_mappings_coexist(self):
        for reason in ('explicit_allow','explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error'):
            request=governance_request(effect='allow' if reason=='explicit_allow' else 'deny',reason=reason)
            records,rejected=decode(combine(request_for(),llm_request(),graph_request(),request).SerializeToString())
            self.assertEqual((len(records),rejected),(4,0))
        for outcome in ('completed','error','cancelled'):
            self.assertEqual(decode(governance_request(effect='allow',reason='explicit_allow',outcome=outcome).SerializeToString())[1],0)

    def test_invalid_decision_pairing_identifiers_types_and_status_rejected(self):
        for key,value in [('aegis.action.id','0'*32),('aegis.action.id','Z'*32),('aegis.decision.effect','allow'),('aegis.decision.reason','unknown'),('aegis.action.outcome','completed'),('aegis.policy.revision','*'),('gen_ai.operation.name','invoke_agent')]:
            request=governance_request()
            next(attr for attr in first_span(request).attributes if attr.key==key).value.string_value=value
            self.assertEqual(decode(request.SerializeToString()),([],1))
        for key in ('aegis.subject.id','aegis.tool.permission','aegis.policy.revision','aegis.decision.rule_id'):
            request=governance_request();step=first_span(request)
            values=[attr for attr in step.attributes if attr.key!=key];step.ClearField('attributes');step.attributes.extend(values)
            self.assertEqual(decode(request.SerializeToString()),([],1))
        request=governance_request();first_span(request).status.code=0
        self.assertEqual(decode(request.SerializeToString()),([],1))
        request=governance_request();first_span(request).kind=3
        self.assertEqual(decode(request.SerializeToString()),([],1))

    def test_privacy_and_native_permissions_do_not_claim_enforcement(self):
        request=governance_request()
        for key in ('arguments','result','prompt','authorization'):
            first_span(request).attributes.add(key=key).value.string_value='private payload'
        records,rejected=decode(request.SerializeToString())
        self.assertEqual(rejected,0);self.assertNotIn('private',str(records))
        native=request_for(operation='execute_tool')
        first_span(native).attributes.add(key='aegis.decision.effect').value.string_value='allow'
        self.assertNotIn('aegis.decision.effect',decode(native.SerializeToString())[0][0].attributes)
