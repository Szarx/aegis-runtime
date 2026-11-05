import copy
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from aegis_policy import Policy, Rule
from aegis_runtime import Runtime, ActionDenied
from aegis_runtime.approvals import ApprovalClient, ApprovalUnavailable, canonical_arguments, policy_digest


class Response(io.BytesIO):
    status = 200


class Approvals(unittest.TestCase):
    def client(self):
        return ApprovalClient("http://127.0.0.1:8000", token="synthetic-producer", binding_key=b"synthetic-binding-key-for-tests!!")

    def request(self):
        return dict(action_id="1" * 32, subject="agent", tool="write", permission="records.write",
                    policy=Policy("r1", ()), arguments={"private": "never-send-this-value"}, summary="Synthetic record change")

    def transport(self, client, mutate=lambda data: data):
        def send(request, **kwargs):
            data = json.loads(request.data)
            self.sent = data
            now = datetime.now(timezone.utc)
            data.update(status="pending", created_at=now.isoformat(), expires_at=(now + timedelta(seconds=data["ttl_seconds"])).isoformat(), decided_at=None, reviewer=None)
            return Response(json.dumps(mutate(data)).encode())
        client._opener = Mock()
        client._opener.open.side_effect = send

    def test_ac1001_canonical_preserves_types_order_and_input(self):
        value = {"z": [None, False, 3, "中文"], "a": {"b": 1}}
        original = copy.deepcopy(value)
        self.assertEqual(canonical_arguments(value), canonical_arguments(dict(reversed(list(value.items())))))
        self.assertEqual(value, original)
        self.assertNotEqual(canonical_arguments([1]), canonical_arguments([True]))
        self.assertNotEqual(canonical_arguments([1, 2]), canonical_arguments([2, 1]))
        self.assertEqual(canonical_arguments(-(2**63)), b"-9223372036854775808")

    def test_ac1001_rejects_unsafe_types_cycles_depth_and_size(self):
        cycle = []; cycle.append(cycle)
        deep = []
        for _ in range(17): deep = [deep]
        class Custom(str): pass
        for value in (1.0, float("nan"), (1,), {1: "x"}, 2**63, -(2**63)-1, "x"*2049,
                      [0]*129, cycle, deep, Custom("x"), ["界"*2048]*3, "\ud800"):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError): canonical_arguments(value)

    def test_ac1001_binding_changes_and_raw_parameters_never_leave_client(self):
        client = self.client(); self.transport(client)
        request = self.request()
        first = client.prepare(**request)
        self.assertNotIn("never-send-this-value", json.dumps(self.sent))
        self.assertNotIn("arguments", self.sent)
        request["arguments"] = {"private": "changed"}
        second = client.prepare(**request)
        self.assertNotEqual(first["arguments_hmac"], second["arguments_hmac"])
        other = ApprovalClient("http://localhost", token="other", binding_key=b"b" * 32)
        self.transport(other)
        self.assertNotEqual(other.prepare(**request)["arguments_hmac"], second["arguments_hmac"])
        rule = Rule("r", "allow", ("agent",), ("write",), ("records.write",))
        self.assertNotEqual(policy_digest(Policy("r1", ())), policy_digest(Policy("r1", (rule,))))
        self.assertNotEqual(policy_digest(Policy("r1", ())), policy_digest(Policy("r2", ())))
        self.assertNotIn("synthetic-binding", repr(client))

    def test_ac1004_rejects_remote_redirect_credentials_and_invalid_configuration(self):
        for endpoint in ("https://localhost", "http://example.com", "http://localhost/", "http://x@localhost", "http://localhost?key=x", "http://localhost#x", "http://localhost:99999"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                ApprovalClient(endpoint, token="x", binding_key=b"a"*32)
        for timeout in (0, 6, True, float("nan")):
            with self.assertRaises(ValueError): ApprovalClient("http://localhost", token="x", binding_key=b"a"*32, timeout=timeout)
        client = self.client()
        from aegis_runtime.approvals import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_ac1004_transport_and_bad_response_fail_with_fixed_error_no_retry(self):
        for failure in (TimeoutError("private"), OSError("secret")):
            client = self.client(); client._opener = Mock(); client._opener.open.side_effect = failure
            with self.assertRaisesRegex(ApprovalUnavailable, "^approval service unavailable$"): client.prepare(**self.request())
            self.assertEqual(client._opener.open.call_count, 1)
        for mutate in (lambda x: {**x, "subject": "other"}, lambda x: {**x, "ttl_seconds": True},
                       lambda x: {**x, "status": "executed"}, lambda x: {**x, "expires_at": "bad"},
                       lambda x: {**x, "reviewer": "fake"}):
            client = self.client(); self.transport(client, mutate)
            with self.assertRaises(ApprovalUnavailable): client.prepare(**self.request())
        for raw in (b"bad-json", b"x"*65537):
            client = self.client(); client._opener = Mock(); client._opener.open.return_value = Response(raw)
            with self.assertRaises(ApprovalUnavailable): client.prepare(**self.request())

    def test_ac1004_approved_record_never_overrides_runtime(self):
        client = self.client()
        def approve(data):
            return {**data, "status": "approved", "decided_at": data["created_at"], "reviewer": "local-reviewer"}
        self.transport(client, approve)
        self.assertEqual(client.prepare(**self.request())["status"], "approved")
        calls = []
        runtime = Runtime(policy=Policy("r1", ()), subject="agent")
        @runtime.tool(permission="records.write", name="write")
        def business(): calls.append(1)
        with self.assertRaises(ActionDenied): business()
        self.assertEqual(calls, [])

    def test_ac1004_live_http_redirect_and_timeout_never_retry_or_forward(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        import time
        received = []
        class Handler(BaseHTTPRequestHandler):
            mode = "redirect"
            def log_message(self, *args): pass
            def do_POST(self):
                received.append(self.path)
                self.rfile.read(int(self.headers["Content-Length"]))
                if self.mode == "redirect":
                    self.send_response(307); self.send_header("Location", "/forwarded"); self.end_headers()
                else:
                    time.sleep(0.1)
                    self.send_response(200); self.end_headers()
            def do_GET(self):
                received.append(self.path); self.send_response(200); self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            client = ApprovalClient(f"http://127.0.0.1:{server.server_port}", token="synthetic", binding_key=b"x"*32, timeout=0.02)
            with self.assertRaises(ApprovalUnavailable): client.prepare(**self.request())
            Handler.mode = "timeout"
            with self.assertRaises(ApprovalUnavailable): client.prepare(**self.request())
            self.assertEqual(received, ["/api/v1/approvals", "/api/v1/approvals"])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
