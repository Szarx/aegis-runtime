"""SPEC-002 transport, privacy and error contracts; storage uses a test double."""

import json
import unittest

from fastapi.testclient import TestClient
from google.rpc.status_pb2 import Status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

from aegis_collector.api import create_app
from aegis_collector.storage import StorageError
from tests.fixtures.otlp import combine, first_span, request_for


class RecordingStore:
    def __init__(self):
        self.records = []
        self.failing = False

    def insert(self, records):
        if self.failing:
            raise StorageError("synthetic-secret-database-address")
        self.records.extend(records)

    def ping(self):
        if self.failing:
            raise StorageError("synthetic-secret-database-address")

    def list_traces(self, **kwargs):
        return {"items": [], "total": 0, "limit": kwargs["limit"], "offset": kwargs["offset"]}

    def trace_detail(self, trace_id):
        return None


class ProtocolAcceptance(unittest.TestCase):
    def setUp(self):
        self.store = RecordingStore()
        self.client = TestClient(create_app(self.store))
        self.addCleanup(self.client.close)

    def post(self, request, **kwargs):
        return self.client.post("/v1/traces", content=request.SerializeToString(), headers={"Content-Type": "application/x-protobuf"}, **kwargs)

    def test_ac201_empty_success_and_standard_response(self):
        response = self.post(combine())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/x-protobuf")
        parsed = ExportTraceServiceResponse.FromString(response.content)
        self.assertFalse(parsed.HasField("partial_success"))
        self.assertEqual(self.store.records, [])
        self.assertEqual(self.post(request_for()).status_code, 200)
        self.assertEqual(len(self.store.records), 1)

    def test_ac202_mixed_invalid_spans_and_unsupported_scope(self):
        invalid = request_for(trace=2)
        first_span(invalid).trace_id = b"\0" * 16
        unsupported = request_for(trace=3)
        unsupported.resource_spans[0].scope_spans[0].scope.name = "another-instrumentation"
        response = self.post(combine(request_for(), invalid, unsupported))
        result = ExportTraceServiceResponse.FromString(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result.partial_success.rejected_spans, 2)
        self.assertEqual(len(self.store.records), 1)

    def test_ac202_bad_encoding_and_body_batch_limits(self):
        for body, headers, expected in (
            (b"\xff", {"Content-Type": "application/x-protobuf"}, 400),
            (b"{}", {"Content-Type": "application/json"}, 415),
            (b"", {"Content-Type": "application/x-protobuf", "Content-Encoding": "gzip"}, 415),
            (b"a" * (1024 * 1024 + 1), {"Content-Type": "application/x-protobuf"}, 413),
        ):
            with self.subTest(expected=expected):
                response = self.client.post("/v1/traces", content=body, headers=headers)
                self.assertEqual(response.status_code, expected)
                self.assertTrue(Status.FromString(response.content).message)
        request = request_for()
        scope = request.resource_spans[0].scope_spans[0]
        template = first_span(request)
        for _ in range(512):
            scope.spans.add().CopyFrom(template)
        self.assertEqual(self.post(request).status_code, 413)
        self.assertEqual(self.store.records, [])

    def test_ac202_retained_metadata_validation(self):
        def zero_time(request):
            first_span(request).start_time_unix_nano = 0
        def duplicate_key(request):
            first_span(request).attributes.add(key="gen_ai.agent.name").value.string_value = "other"
        def bad_value(request):
            first_span(request).attributes[0].value.int_value = 123
        def bad_nul(request):
            request.resource_spans[0].resource.attributes[0].value.string_value = "bad\0name"
        def big_timestamp(request):
            first_span(request).end_time_unix_nano = 2**63
        def invalid_parent(request):
            first_span(request).parent_span_id = b"\0" * 8
        def too_many_attributes(request):
            for index in range(65):
                first_span(request).attributes.add(key=f"unknown-{index}").value.string_value = "ignored"
        def too_many_events(request):
            for _ in range(17):
                first_span(request).events.add(name="ignored")
        def missing_error_type(request):
            first_span(request).status.code = 2
        for change in (zero_time, duplicate_key, bad_value, bad_nul, big_timestamp, invalid_parent, too_many_attributes, too_many_events, missing_error_type):
            with self.subTest(change=change.__name__):
                request = request_for()
                change(request)
                result = ExportTraceServiceResponse.FromString(self.post(request).content)
                self.assertEqual(result.partial_success.rejected_spans, 1)
        self.assertEqual(self.store.records, [])

    def test_ac208_content_and_error_messages_are_not_retained(self):
        secret = "synthetic-secret-content"
        request = request_for(error=True)
        resource = request.resource_spans[0]
        resource.resource.attributes.add(key="authorization").value.string_value = secret
        step = first_span(request)
        step.attributes.add(key="gen_ai.input.messages").value.string_value = secret
        step.attributes.add(key="gen_ai.tool.call.arguments").value.string_value = secret
        step.events[0].attributes.add(key="exception.message").value.string_value = secret
        step.events[0].attributes.add(key="exception.stacktrace").value.string_value = secret
        step.status.message = secret
        response = self.post(request)
        self.assertEqual(response.status_code, 200)
        payload = json.dumps(self.store.records[0].public())
        self.assertNotIn(secret, payload)
        self.assertNotIn("stacktrace", payload)
        self.assertNotIn("authorization", payload)
        self.assertEqual(self.store.records[0].events[0]["attributes"], {"exception.type": "builtins.LookupError"})

    def test_ac209_authentication_and_database_failure(self):
        self.client.close()
        self.client = TestClient(create_app(self.store, api_token="synthetic-test-token"))
        response = self.post(request_for())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Status.FromString(response.content).message, "unauthorized")
        self.assertEqual(self.client.get("/api/v1/traces").status_code, 401)
        auth = {"Authorization": "Bearer synthetic-test-token"}
        response = self.client.post("/v1/traces", content=request_for().SerializeToString(), headers={**auth, "Content-Type": "application/x-protobuf"})
        self.assertEqual(response.status_code, 200)
        self.store.failing = True
        response = self.client.post("/v1/traces", content=request_for().SerializeToString(), headers={**auth, "Content-Type": "application/x-protobuf"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("synthetic-secret", Status.FromString(response.content).message)
        self.assertEqual(self.client.get("/health/live").status_code, 200)
        self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_ac206_invalid_query_and_unknown_trace(self):
        for query in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 10001}, {"status": "bad"}, {"agent_name": " "}, {"service_name": "bad\0value"}, {"started_after_ns": 10, "started_before_ns": 5}):
            with self.subTest(query=query):
                response = self.client.get("/api/v1/traces", params=query)
                self.assertEqual(response.status_code, 400)
        for identifier in ("invalid", "0" * 32, "A" * 32):
            self.assertEqual(self.client.get(f"/api/v1/traces/{identifier}").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/traces/" + "1" * 32).status_code, 404)


if __name__ == "__main__":
    unittest.main()
