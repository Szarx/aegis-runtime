import unittest
from aegis_collector.ingestion.otlp import decode
from tests.fixtures.graph_stream import graph_request
from tests.fixtures.otlp import first_span,combine,request_for
from tests.fixtures.llm import llm_request


class GraphStreamProtocol(unittest.TestCase):
    def test_ac704_three_mappings_coexist_and_graph_lifecycles_validate(self):
        for outcome in ('completed','closed','error','cancelled'):
            records,rejected=decode(combine(request_for(),llm_request(),graph_request(outcome=outcome,trace=2)).SerializeToString())
            self.assertEqual(rejected,0)
            self.assertEqual(len(records),3)
            self.assertEqual(records[-1].attributes['aegis.graph.outcome'],outcome)
    def test_ac704_invalid_mode_outcome_kind_operation_and_status_rejected(self):
        for key,value in [('aegis.graph.mode','unknown'),('aegis.graph.outcome','unknown'),('gen_ai.operation.name','execute_tool')]:
            request=graph_request()
            next(a for a in first_span(request).attributes if a.key==key).value.string_value=value
            self.assertEqual(decode(request.SerializeToString()),([],1))
        request=graph_request(outcome='closed');first_span(request).status.code=2
        self.assertEqual(decode(request.SerializeToString()),([],1))
        request=graph_request();first_span(request).kind=3
        self.assertEqual(decode(request.SerializeToString()),([],1))
    def test_ac704_graph_privacy_and_native_metadata_remain_independent(self):
        request=graph_request()
        for key in ('state','chunk','messages','authorization','gen_ai.tool.name'):
            first_span(request).attributes.add(key=key).value.string_value='private-state'
        records,rejected=decode(request.SerializeToString())
        self.assertEqual(rejected,0)
        self.assertNotIn('private-state',str(records))
        native=request_for()
        first_span(native).attributes.add(key='aegis.graph.outcome').value.string_value='closed'
        self.assertNotIn('aegis.graph.outcome',decode(native.SerializeToString())[0][0].attributes)
