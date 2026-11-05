import unittest
import aegis
from aegis.governance import governed_tool_span
from aegis.exporters.jsonl import span_record
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class GovernanceTelemetry(unittest.TestCase):
    def tearDown(self):aegis.shutdown()
    def test_metadata_only_context_is_not_authorization_and_local_v4_whitelist(self):
        exporter=InMemorySpanExporter();aegis.init('governance-sdk',exporter=exporter)
        with governed_tool_span('lookup',permission='orders.read',subject='reader',action_id='1'*32,
                                effect='allow',reason='explicit_allow',policy_revision='v1',rule_id='read'):
            from opentelemetry import trace
            trace.get_current_span().set_attribute('arguments','private argument')
        aegis.flush()
        record=span_record(exporter.get_finished_spans()[0])
        self.assertEqual(record['schema_version'],'aegis.span.v4')
        self.assertEqual(record['attributes']['aegis.action.outcome'],'completed')
        self.assertNotIn('private',str(record))
    def test_no_sdk_is_passthrough_and_business_exception_is_preserved(self):
        marker=LookupError('private error')
        try:
            with governed_tool_span('lookup',permission=None,subject=None,action_id='2'*32,effect='deny',reason='identity_missing'):
                raise marker
        except LookupError as error:self.assertIs(error,marker)
        else:self.fail('expected original exception')


if __name__=='__main__':unittest.main()
