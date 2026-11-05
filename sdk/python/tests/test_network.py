"""SPEC-002 network failures must never become business retries."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest

import aegis

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    HAVE_OTLP = True
except ImportError:
    HAVE_OTLP = False


@unittest.skipUnless(HAVE_OTLP, "install the SDK otlp extra to run transport acceptance")
class NetworkAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown()
        self.codes = []
        self.bodies = []
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.bodies.append(body)
                time.sleep(owner.delay)
                code = owner.codes.pop(0) if owner.codes else 200
                self.send_response(code)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.05), daemon=True)
        self.worker.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}/v1/traces"

    def tearDown(self):
        aegis.shutdown()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(2)

    def business(self):
        calls = []

        @aegis.observe
        def agent():
            calls.append(1)
            return "same-business-result"

        self.assertEqual(agent(), "same-business-result")
        return calls

    def test_ac207_recovery_retransmits_same_telemetry_only(self):
        self.codes = [503, 200]
        sdk = aegis.init("network-test", endpoint=self.endpoint, export_timeout_millis=5000)
        calls = self.business()
        self.assertTrue(aegis.flush(timeout_millis=6000))
        self.assertEqual(calls, [1])
        self.assertEqual(len(self.bodies), 2)
        self.assertEqual(self.bodies[0], self.bodies[1])
        self.assertEqual(sdk.diagnostics()["exported_spans"], 1)

    def test_ac207_bad_request_is_not_retried(self):
        self.codes = [400]
        sdk = aegis.init("network-test", endpoint=self.endpoint, export_timeout_millis=500)
        calls = self.business()
        self.assertFalse(aegis.flush())
        self.assertEqual(calls, [1])
        self.assertEqual(len(self.bodies), 1)
        self.assertEqual(sdk.diagnostics()["failed_spans"], 1)

    def test_ac207_slow_server_has_bounded_wait(self):
        self.delay = 0.4
        sdk = aegis.init("network-test", endpoint=self.endpoint, export_timeout_millis=100)
        calls = self.business()
        start = time.monotonic()
        self.assertFalse(aegis.flush(timeout_millis=20))
        self.assertLess(time.monotonic() - start, 1)
        self.assertFalse(sdk.flush(timeout_millis=1000))
        self.assertEqual(calls, [1])
        self.assertGreaterEqual(sdk.diagnostics()["failed_spans"], 1)

    def test_ac207_configuration_is_explicit_and_validated(self):
        for endpoint in ("http://example.test", "file:///v1/traces", "http://user:pass@example.test/v1/traces", "http://example.test/v1/traces?secret=value", "http://example.test/v1/traces#fragment", 123):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                aegis.init("test", endpoint=endpoint)
        for timeout in (0, -1, True, 30001):
            with self.assertRaises(ValueError):
                aegis.init("test", endpoint=self.endpoint, export_timeout_millis=timeout)
        with self.assertRaises(ValueError):
            aegis.init("test", endpoint=self.endpoint, output_path="unused.jsonl")
        with self.assertRaises(ValueError):
            aegis.init("test", headers={"Authorization": "token"})
        with self.assertRaises(ValueError):
            aegis.init("test", endpoint=self.endpoint, headers={"Authorization": "bad\r\nvalue"})


if __name__ == "__main__":
    unittest.main()
