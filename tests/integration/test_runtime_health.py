import time
import threading
import unittest
from urllib.request import urlopen, Request
import json
import subprocess
import sys
from fastapi.responses import JSONResponse
import aegis
from aegis_collector.api import create_app
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from tests.fixtures.live_server import LiveServer


class BlockingFailure(SpanExporter):
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
    def export(self, spans):
        self.entered.set()
        self.release.wait(5)
        return SpanExportResult.FAILURE
    def shutdown(self):
        pass


class RuntimeHealth(unittest.TestCase):
    def test_running_activity_export_loss_and_shutdown_lease(self):
        app = create_app(None, api_token='synthetic-token')
        fail_once = [True]
        @app.middleware('http')
        async def unavailable(request, call_next):
            if request.url.path == '/v1/health' and fail_once[0]:
                fail_once[0] = False
                return JSONResponse({'error': 'synthetic'}, 503)
            return await call_next(request)
        now = [0]
        app.state.health_registry._clock = lambda: now[0]
        live = LiveServer(app).start()
        exporter = BlockingFailure()
        sdk = aegis.init('running-agent', exporter=exporter, max_queue_size=1,
                         max_export_batch_size=1, schedule_delay_millis=1)
        spans = []
        try:
            instance = sdk.start_health_reporting(live.endpoint + '/v1/health', token='synthetic-token', interval_seconds=1)
            def snapshot(condition):
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    with urlopen(Request(live.endpoint + '/api/v1/health',
                            headers={'Authorization': 'Bearer synthetic-token'}), timeout=3) as response:
                        rows = json.load(response)['items']
                    if rows and condition(rows[0]):
                        return rows[0]
                    time.sleep(.05)
                self.fail('Expected health snapshot did not arrive')
            active = sdk.tracer.start_span('slow-work')
            spans.append(active)
            row = snapshot(lambda row: row['active_spans'] == 1)
            self.assertEqual(row['instance_id'], instance)
            self.assertGreater(row['health_failures'], 0)
            self.assertEqual(row['active_traces'], [format(active.get_span_context().trace_id, '032x')])
            first = sdk.tracer.start_span('finished')
            first.end()
            self.assertTrue(exporter.entered.wait(3))
            for _ in range(6):
                sdk.tracer.start_span('overflow').end()
            exporter.release.set()
            row = snapshot(lambda row: row['diagnostics']['dropped_spans'] > 0 and row['diagnostics']['failed_spans'] > 0)
            self.assertEqual(row['active_spans'], 1)
            active.end()
            spans.clear()
            snapshot(lambda row: row['active_spans'] == 0)
            sdk.shutdown()
            sdk._health._worker.join(2)
            self.assertFalse(sdk._health._worker.is_alive())
            now[0] = 46
            self.assertEqual(snapshot(lambda row: row['state'] == 'stale')['active_spans'], 0)
        finally:
            exporter.release.set()
            for span in spans:
                span.end()
            sdk.shutdown()
            live.close()

    def test_process_death_preserves_last_activity_as_stale(self):
        app = create_app(None, api_token='synthetic-token')
        now = [0]
        app.state.health_registry._clock = lambda: now[0]
        live = LiveServer(app).start()
        code = """
import time, aegis
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
sdk = aegis.init('crash-demo', exporter=InMemorySpanExporter())
span = sdk.tracer.start_span('running')
sdk.start_health_reporting(ENDPOINT, token='synthetic-token', interval_seconds=1)
time.sleep(30)
"""
        child = subprocess.Popen([sys.executable, '-c', code.replace('ENDPOINT', repr(live.endpoint + '/v1/health'))],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                rows = app.state.health_registry.listing()['items']
                if rows:
                    break
                time.sleep(.05)
            self.assertTrue(rows)
            self.assertEqual(rows[0]['active_spans'], 1)
            child.kill()
            child.wait(timeout=5)
            now[0] = 46
            last = app.state.health_registry.listing()['items'][0]
            self.assertEqual((last['state'], last['active_spans']), ('stale', 1))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            live.close()
