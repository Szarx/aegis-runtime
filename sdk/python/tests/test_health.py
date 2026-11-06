import unittest
import aegis
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class SDKHealth(unittest.TestCase):
    def tearDown(self):
        aegis.shutdown()

    def test_activity_is_bounded_and_released_without_exporting_running_spans(self):
        exporter = InMemorySpanExporter()
        sdk = aegis.init('synthetic', exporter=exporter)
        spans = [sdk.tracer.start_span('work') for _ in range(140)]
        activity = sdk._processor.activity()
        self.assertEqual(activity['active_spans'], 140)
        self.assertEqual(len(activity['active_traces']), 16)
        self.assertTrue(activity['activity_truncated'])
        self.assertEqual(len(exporter.get_finished_spans()), 0)
        for span in spans:
            span.end()
        self.assertEqual(sdk._processor.activity()['active_spans'], 0)
        self.assertEqual(sdk._processor.activity()['active_traces'], [])

    def test_invalid_opt_in_does_not_attach_reporter(self):
        sdk = aegis.init('synthetic', exporter=InMemorySpanExporter())
        for endpoint in ('http://example.org/v1/health', 'https://example.org/other', 'https://user:pass@example.org/v1/health'):
            with self.assertRaises(ValueError):
                sdk.start_health_reporting(endpoint)
        self.assertIsNone(sdk._health)
