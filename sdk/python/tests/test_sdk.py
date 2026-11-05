"""Behavioral acceptance coverage for SPEC-001; no external services needed."""

import asyncio
import inspect
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import aegis
from aegis import observe, tool
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode


class BlockingExporter(InMemorySpanExporter):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.thread_id = None

    def export(self, spans):
        self.thread_id = threading.get_ident()
        self.entered.set()
        if not self.release.wait(5):
            return SpanExportResult.FAILURE
        return super().export(spans)


class FailingExporter(SpanExporter):
    def __init__(self, raises):
        self.raises = raises

    def export(self, spans):
        if self.raises:
            raise RuntimeError("synthetic-secret-export-error")
        return SpanExportResult.FAILURE

    def shutdown(self):
        pass


class SDKAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.exporter = InMemorySpanExporter()
        self.sdk = None
        self.blockers = []

    def tearDown(self):
        for exporter in self.blockers:
            exporter.release.set()
        if self.sdk is not None:
            self.sdk.shutdown()
        aegis.shutdown()

    def start(self, **kwargs):
        self.sdk = aegis.init("test-service", exporter=self.exporter, **kwargs)
        return self.sdk

    def spans(self):
        self.assertTrue(aegis.flush())
        return self.exporter.get_finished_spans()

    def test_ac01_ac03_sync_tree_signature_identity_and_single_execution(self):
        self.start()
        result = {"status": "synthetic"}
        calls = []

        def lookup(order_id: str, *, mode="read") -> dict:
            calls.append(order_id)
            return result

        wrapped = tool(permission="orders.read")(lookup)

        @observe(name="order-agent")
        def agent(order_id):
            return wrapped(order_id)

        self.assertIs(agent("synthetic-order"), result)
        self.assertEqual(calls, ["synthetic-order"])
        self.assertEqual(inspect.signature(wrapped), inspect.signature(lookup))
        self.assertEqual(wrapped.__name__, lookup.__name__)
        spans = {span.name: span for span in self.spans()}
        parent = spans["invoke_agent order-agent"]
        child = spans["execute_tool lookup"]
        self.assertEqual(parent.context.trace_id, child.context.trace_id)
        self.assertEqual(child.parent.span_id, parent.context.span_id)
        self.assertIsNone(parent.parent)
        self.assertEqual(child.attributes["aegis.tool.permission"], "orders.read")
        self.assertEqual(parent.status.status_code, StatusCode.UNSET)

    def test_ac01_nested_agent_nearest_context_and_standalone_tool(self):
        self.start()

        @tool
        def leaf():
            return 42

        @observe()
        def inner():
            return leaf()

        @observe
        def outer():
            return inner()

        self.assertEqual(outer(), 42)
        self.assertEqual(leaf(), 42)
        spans = self.spans()
        nested_tool = next(s for s in spans if s.name == "execute_tool leaf" and s.parent)
        standalone = next(s for s in spans if s.name == "execute_tool leaf" and not s.parent)
        inner_span = next(s for s in spans if s.name == "invoke_agent inner")
        outer_span = next(s for s in spans if s.name == "invoke_agent outer")
        self.assertEqual(nested_tool.parent.span_id, inner_span.context.span_id)
        self.assertEqual(inner_span.parent.span_id, outer_span.context.span_id)
        self.assertEqual(nested_tool.attributes["gen_ai.agent.name"], "inner")
        self.assertNotIn("gen_ai.agent.name", standalone.attributes)
        self.assertNotEqual(standalone.context.trace_id, outer_span.context.trace_id)

    def test_ac02_async_concurrency_isolation(self):
        self.start()

        @tool(permission="orders.read")
        async def lookup(value):
            await asyncio.sleep(0)
            return value

        @observe
        async def agent(value):
            return await lookup(value)

        async def run():
            return await asyncio.gather(*(agent(i) for i in range(12)))

        self.assertTrue(inspect.iscoroutinefunction(agent))
        self.assertEqual(asyncio.run(run()), list(range(12)))
        spans = self.spans()
        roots = {s.context.span_id: s for s in spans if s.name == "invoke_agent agent"}
        children = [s for s in spans if s.name == "execute_tool lookup"]
        self.assertEqual(len({s.context.trace_id for s in roots.values()}), 12)
        self.assertEqual(len(children), 12)
        for child in children:
            self.assertEqual(child.context.trace_id, roots[child.parent.span_id].context.trace_id)

    def test_ac02_ac08_upstream_context_and_host_provider_preserved(self):
        host = trace.get_tracer_provider()
        upstream = TracerProvider(shutdown_on_exit=False)
        self.addCleanup(upstream.shutdown)
        self.start()

        @observe
        def agent():
            return 1

        with upstream.get_tracer("host").start_as_current_span("incoming") as parent:
            self.assertEqual(agent(), 1)
            self.assertIs(trace.get_current_span(), parent)
        span = self.spans()[0]
        self.assertEqual(span.parent.span_id, parent.get_span_context().span_id)
        self.assertEqual(span.context.trace_id, parent.get_span_context().trace_id)
        self.assertIs(trace.get_tracer_provider(), host)
        self.sdk.shutdown()
        self.assertIs(trace.get_tracer_provider(), host)

    def test_ac03_ac04_ac05_original_exception_and_content_privacy(self):
        output = Path(self.directory.name) / "trace.jsonl"
        self.sdk = aegis.init("test-service", output_path=output)
        secret = "synthetic-secret-argument-output-and-message"
        failure = ValueError(secret)
        calls = []

        @tool(permission="orders.read")
        def lookup(value):
            calls.append(1)
            raise failure

        @observe
        def agent(value):
            return lookup(value)

        with self.assertRaises(ValueError) as caught:
            agent(secret)
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls, [1])

        @observe
        def successful(value):
            return {"secret": value}

        self.assertEqual(successful(secret), {"secret": secret})
        self.assertTrue(aegis.flush())
        payload = output.read_text(encoding="utf-8")
        self.assertNotIn(secret, payload)
        self.assertNotIn("exception.message", payload)
        self.assertNotIn("exception.stacktrace", payload)
        records = [json.loads(line) for line in payload.splitlines()]
        failed = [r for r in records if r["status"] == "ERROR"]
        self.assertEqual(len(failed), 2)
        for record in failed:
            self.assertEqual(record["attributes"]["error.type"], "builtins.ValueError")
            self.assertEqual(record["events"][0]["attributes"], {"exception.type": "builtins.ValueError"})

    def test_ac05_async_cancel_and_context_cleanup(self):
        self.start()

        async def run():
            entered = asyncio.Event()

            @observe(name="cancelled-agent")
            async def pending():
                entered.set()
                await asyncio.Event().wait()

            task = asyncio.create_task(pending())
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

            @observe(name="later-agent")
            async def later():
                return 1

            self.assertEqual(await later(), 1)

        asyncio.run(run())
        spans = {s.name: s for s in self.spans()}
        cancelled = spans["invoke_agent cancelled-agent"]
        later = spans["invoke_agent later-agent"]
        self.assertEqual(cancelled.status.status_code, StatusCode.ERROR)
        self.assertTrue(cancelled.attributes["error.type"].endswith("CancelledError"))
        self.assertIsNone(later.parent)
        self.assertNotEqual(cancelled.context.trace_id, later.context.trace_id)

    def test_ac06_export_failures_do_not_repeat_business(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                self.sdk = aegis.init("test-service", exporter=FailingExporter(raises))
                calls = []

                @tool
                def action():
                    calls.append(1)
                    return "unchanged"

                self.assertEqual(action(), "unchanged")
                self.assertFalse(aegis.flush())
                self.assertEqual(calls, [1])
                self.assertEqual(self.sdk.diagnostics()["failed_spans"], 1)
                self.assertEqual(self.sdk.diagnostics()["export_failures"], 1)
                self.assertFalse(self.sdk.shutdown())

    def test_ac06_ac07_background_overflow_and_flush_timeout(self):
        blocker = BlockingExporter()
        self.blockers.append(blocker)
        self.exporter = blocker
        self.start(max_queue_size=2, max_export_batch_size=1)

        @tool
        def action():
            return 1

        self.assertEqual(action(), 1)
        self.assertTrue(blocker.entered.wait(2))
        for _ in range(5):
            self.assertEqual(action(), 1)
        self.assertNotEqual(blocker.thread_id, threading.get_ident())
        diagnostics = self.sdk.diagnostics()
        self.assertEqual(diagnostics["accepted_spans"], 3)
        self.assertEqual(diagnostics["dropped_spans"], 3)
        self.assertEqual(diagnostics["pending_spans"], 3)
        start = time.monotonic()
        self.assertFalse(aegis.flush(timeout_millis=20))
        self.assertLess(time.monotonic() - start, 1)
        blocker.release.set()
        self.assertTrue(aegis.flush())
        self.assertEqual(len(blocker.get_finished_spans()), 3)

    def test_ac07_shutdown_wait_is_bounded_and_repeatable(self):
        blocker = BlockingExporter()
        self.blockers.append(blocker)
        self.exporter = blocker
        self.start(max_export_batch_size=1)

        @observe
        def agent():
            return 1

        agent()
        self.assertTrue(blocker.entered.wait(2))
        start = time.monotonic()
        self.assertFalse(self.sdk.shutdown(timeout_millis=20))
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(agent(), 1)
        blocker.release.set()
        self.assertTrue(self.sdk.shutdown())

    def test_ac06_local_write_failure_is_diagnostic(self):
        self.sdk = aegis.init("test-service", output_path=Path(self.directory.name))

        @observe
        def agent():
            return "business-ok"

        self.assertEqual(agent(), "business-ok")
        self.assertFalse(aegis.flush())
        self.assertEqual(self.sdk.diagnostics()["failed_spans"], 1)

    def test_ac03_instrumentation_failure_still_calls_business_once(self):
        self.start()
        calls = []

        @observe
        def agent():
            calls.append(1)
            return 1

        with patch.object(self.sdk.tracer, "start_span", side_effect=RuntimeError("synthetic-secret")):
            self.assertEqual(agent(), 1)
        self.assertEqual(calls, [1])
        self.assertEqual(self.sdk.diagnostics()["instrumentation_failures"], 1)

    def test_ac04_resources_do_not_capture_environment_attributes(self):
        with patch.dict(os.environ, {"OTEL_RESOURCE_ATTRIBUTES": "api.key=synthetic-secret"}):
            self.start()

        @observe
        def agent():
            return 1

        agent()
        self.assertNotIn("api.key", self.spans()[0].resource.attributes)

    def test_ac08_ac11_disabled_reinitialize_and_configuration(self):
        marker = object()

        @observe
        def agent():
            return marker

        self.assertIs(agent(), marker)
        self.start()
        self.assertIs(agent(), marker)
        self.assertEqual(len(self.spans()), 1)
        with self.assertRaises(RuntimeError):
            aegis.init("duplicate")
        self.assertTrue(self.sdk.shutdown())
        self.assertIs(agent(), marker)
        self.exporter = InMemorySpanExporter()
        self.start()
        self.assertIs(agent(), marker)
        self.assertEqual(len(self.spans()), 1)

    def test_ac11_invalid_configuration_and_unsupported_generators(self):
        for service_name in ("", " ", "a" * 129, 123):
            with self.subTest(service_name=service_name), self.assertRaises(ValueError):
                aegis.init(service_name)
        for options in (
            {"max_queue_size": 0},
            {"max_export_batch_size": True},
            {"schedule_delay_millis": -1},
            {"max_queue_size": 2, "max_export_batch_size": 3},
            {"output_path": "test.jsonl", "exporter": self.exporter},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                aegis.init("test-service", **options)
        for timeout in (-1, True, 1.2):
            with self.assertRaises(ValueError):
                aegis.flush(timeout)
            with self.assertRaises(ValueError):
                aegis.shutdown(timeout)
        with self.assertRaises(ValueError):
            tool(permission=" ")
        with self.assertRaises(ValueError):
            observe(name="")

        def stream():
            yield 1

        async def async_stream():
            yield 1

        for function in (stream, async_stream):
            with self.assertRaises(TypeError):
                observe(function)

    def test_ac09_ac10_native_example_and_jsonl_contract(self):
        repo = Path(__file__).resolve().parents[3]
        output = Path(self.directory.name) / "demo.jsonl"
        run = subprocess.run(
            [sys.executable, str(repo / "examples/native-python/agent.py"), "--output", str(output)],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Expected failure", run.stdout)
        records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 4)
        self.assertEqual(len({r["trace_id"] for r in records}), 2)
        self.assertEqual(sum(r["status"] == "ERROR" for r in records), 2)
        expected_fields = {
            "schema_version", "trace_id", "span_id", "parent_span_id", "name", "kind",
            "start_time_unix_nano", "end_time_unix_nano", "status", "resource", "scope",
            "attributes", "events",
        }
        by_id = {r["span_id"]: r for r in records}
        for record in records:
            self.assertEqual(set(record), expected_fields)
            self.assertEqual(record["schema_version"], "aegis.span.v1")
            self.assertRegex(record["trace_id"], r"^[0-9a-f]{32}$")
            self.assertRegex(record["span_id"], r"^[0-9a-f]{16}$")
            self.assertNotEqual(int(record["trace_id"], 16), 0)
            self.assertNotEqual(int(record["span_id"], 16), 0)
            self.assertEqual(record["kind"], "INTERNAL")
            self.assertIs(type(record["start_time_unix_nano"]), int)
            self.assertIs(type(record["end_time_unix_nano"]), int)
            self.assertGreater(record["start_time_unix_nano"], 0)
            self.assertGreaterEqual(record["end_time_unix_nano"], record["start_time_unix_nano"])
            self.assertIn(record["status"], {"UNSET", "ERROR"})
            self.assertEqual(set(record["resource"]), {
                "service.name", "telemetry.sdk.name", "telemetry.sdk.language", "telemetry.sdk.version"
            })
            self.assertEqual(record["resource"]["service.name"], "order-service")
            self.assertEqual(record["resource"]["telemetry.sdk.name"], "opentelemetry")
            self.assertEqual(record["resource"]["telemetry.sdk.language"], "python")
            self.assertEqual(record["resource"]["telemetry.sdk.version"], "1.45.1")
            self.assertEqual(record["scope"], {"name": "aegis", "version": "0.1.0.dev0"})
            self.assertLessEqual(set(record["attributes"]), {
                "gen_ai.operation.name", "gen_ai.agent.name", "gen_ai.tool.name",
                "aegis.tool.permission", "aegis.mapping.version", "error.type"
            })
            self.assertTrue(all(isinstance(value, str) for value in record["attributes"].values()))
            self.assertEqual(record["attributes"]["aegis.mapping.version"], "aegis.genai.v1")
            if record["parent_span_id"] is not None:
                self.assertRegex(record["parent_span_id"], r"^[0-9a-f]{16}$")
                parent = by_id[record["parent_span_id"]]
                self.assertEqual(record["trace_id"], parent["trace_id"])
                self.assertEqual(record["attributes"]["gen_ai.operation.name"], "execute_tool")
                self.assertEqual(record["attributes"]["gen_ai.tool.name"], "lookup_order")
                self.assertEqual(record["attributes"]["aegis.tool.permission"], "orders.read")
            else:
                self.assertEqual(record["attributes"]["gen_ai.operation.name"], "invoke_agent")
            self.assertEqual(record["attributes"]["gen_ai.agent.name"], "customer-agent")
            operation = record["attributes"]["gen_ai.operation.name"]
            label = record["attributes"]["gen_ai.tool.name"] if operation == "execute_tool" else "customer-agent"
            self.assertEqual(record["name"], f"{operation} {label}")
            if record["status"] == "ERROR":
                self.assertEqual(record["attributes"]["error.type"], "builtins.LookupError")
                self.assertEqual(len(record["events"]), 1)
                self.assertEqual(set(record["events"][0]), {"name", "time_unix_nano", "attributes"})
                self.assertEqual(record["events"][0]["name"], "exception")
                self.assertIs(type(record["events"][0]["time_unix_nano"]), int)
                self.assertEqual(record["events"][0]["attributes"], {"exception.type": "builtins.LookupError"})
            else:
                self.assertEqual(record["events"], [])


if __name__ == "__main__":
    unittest.main()
