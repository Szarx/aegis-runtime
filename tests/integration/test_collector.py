"""SPEC-002 acceptance against a real, explicitly configured PostgreSQL database."""

import concurrent.futures
import importlib.util
import os
from pathlib import Path
import socket
import threading
import time
import unittest
import uuid

import aegis
import httpx
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
import uvicorn
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

from aegis_collector.api import create_app
from aegis_collector.ingestion.otlp import decode
from aegis_collector.storage import PostgresSpanStore, StorageError
from tests.fixtures.otlp import BASE_TIME, combine, request_for

DATABASE = os.environ.get("AEGIS_TEST_DATABASE_URL")


@unittest.skipUnless(DATABASE, "set AEGIS_TEST_DATABASE_URL to a dedicated PostgreSQL test database")
class PostgresAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown()
        self.schema = "test_" + uuid.uuid4().hex
        self.store = PostgresSpanStore(DATABASE, self.schema)
        self.store.migrate()
        self.client = TestClient(create_app(self.store))

    def tearDown(self):
        aegis.shutdown()
        self.client.close()
        # Delete only the uniquely named schema created by this test.
        with psycopg.connect(DATABASE, connect_timeout=3) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def post(self, request):
        return self.client.post("/v1/traces", content=request.SerializeToString(), headers={"Content-Type": "application/x-protobuf"})

    def test_ac203_retransmission_and_first_write_wins(self):
        request = request_for()
        self.assertEqual(self.post(request).status_code, 200)
        self.assertEqual(self.post(request).status_code, 200)
        changed = request_for(agent="changed-but-same-identifiers", error=True)
        self.assertEqual(self.post(changed).status_code, 200)
        detail = self.store.trace_detail(f"{1:032x}")
        self.assertEqual(detail["trace"]["span_count"], 1)
        self.assertEqual(detail["trace"]["status"], "UNSET")
        self.assertEqual(detail["trace"]["agent_names"], ["demo-agent"])

    def test_ac203_concurrent_retransmission(self):
        records, _ = decode(request_for().SerializeToString())
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            counts = list(pool.map(lambda _: self.store.insert(records), range(8)))
        self.assertEqual(sum(counts), 1)
        self.assertEqual(self.store.trace_detail(f"{1:032x}")["trace"]["span_count"], 1)

    def test_ac204_migration_and_service_reconstruction(self):
        self.post(request_for())
        self.store.migrate()
        recreated = PostgresSpanStore(DATABASE, self.schema)
        recreated.migrate()
        with TestClient(create_app(recreated)) as client:
            self.assertEqual(client.get("/api/v1/traces").json()["total"], 1)
            self.assertEqual(client.get("/api/v1/traces/" + f"{1:032x}").json()["trace"]["span_count"], 1)
        with self.store.connection() as connection:
            connection.execute(sql.SQL("INSERT INTO {}.schema_version VALUES (99)").format(sql.Identifier(self.schema)))
        with self.assertRaises(StorageError):
            recreated.migrate()
        self.assertEqual(self.store.trace_detail(f"{1:032x}")["trace"]["span_count"], 1)

    def test_ac205_late_parent_and_missing_external_parent(self):
        child = request_for(span=2, parent=1, operation="execute_tool", start=150, end=200, error=True)
        self.post(child)
        detail = self.client.get("/api/v1/traces/" + f"{1:032x}").json()
        self.assertEqual(detail["missing_parent_ids"], [f"{1:016x}"])
        self.assertEqual(detail["trace"]["span_count"], 1)
        self.post(request_for(start=100, end=300))
        detail = self.client.get("/api/v1/traces/" + f"{1:032x}").json()
        self.assertEqual(detail["missing_parent_ids"], [])
        self.assertEqual(detail["trace"]["span_count"], 2)
        self.assertEqual(detail["trace"]["duration_ns"], 200)
        self.assertEqual(detail["trace"]["status"], "ERROR")
        self.assertEqual([s["span_id"] for s in detail["spans"]], [f"{1:016x}", f"{2:016x}"])
        self.post(request_for(trace=2, span=3, parent=99))
        self.assertEqual(self.store.trace_detail(f"{2:032x}")["missing_parent_ids"], [f"{99:016x}"])

    def test_ac206_filter_entire_trace_pagination_and_time_boundaries(self):
        self.post(combine(
            request_for(trace=1, agent="alpha", service="first-service"),
            request_for(trace=1, span=2, parent=1, operation="execute_tool", agent="beta", start=150, end=200, error=True),
            request_for(trace=2, agent="gamma", start=400, end=450),
            request_for(trace=3, agent="delta"),
        ))
        response = self.client.get("/api/v1/traces", params={"agent_name": "alpha", "status": "ERROR", "service_name": "first-service"}).json()
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["items"][0]["span_count"], 2)
        self.assertEqual(response["items"][0]["agent_names"], ["alpha", "beta"])
        self.assertNotIn("total_tokens", response["items"][0])
        page = self.client.get("/api/v1/traces", params={"limit": 1, "offset": 0}).json()
        self.assertEqual(page["total"], 3)
        self.assertEqual(page["items"][0]["trace_id"], f"{2:032x}")
        tied = self.client.get("/api/v1/traces", params={"offset": 1}).json()
        self.assertEqual([r["trace_id"] for r in tied["items"]], [f"{1:032x}", f"{3:032x}"])
        empty = self.client.get("/api/v1/traces", params={"offset": 100}).json()
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["total"], 3)
        exact = self.client.get("/api/v1/traces", params={"started_after_ns": BASE_TIME + 100, "started_before_ns": BASE_TIME + 100}).json()
        self.assertEqual(exact["total"], 2)
        injection = self.client.get("/api/v1/traces", params={"agent_name": "'; DROP TABLE spans; --"})
        self.assertEqual(injection.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/traces").json()["total"], 3)

    def test_ac204_transaction_failure_rolls_back_whole_batch(self):
        records, _ = decode(combine(request_for(trace=1), request_for(trace=2)).SerializeToString())
        with self.store.connection() as connection:
            connection.execute(sql.SQL("ALTER TABLE {}.spans ADD CONSTRAINT reject_second CHECK (trace_id <> {})").format(sql.Identifier(self.schema), sql.Literal(f"{2:032x}")))
        with self.assertRaises(StorageError):
            self.store.insert(records)
        self.assertEqual(self.store.list_traces()["total"], 0)

    def test_ac201_ac210_official_exporter_to_live_collector(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(self.store), log_level="error", lifespan="off"))
        worker = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(server.started)
            sdk = aegis.init("order-service", endpoint=f"http://127.0.0.1:{port}/v1/traces", export_timeout_millis=2000)
            repo = Path(__file__).resolve().parents[2]
            spec = importlib.util.spec_from_file_location("aegis_native_demo", repo / "examples/native-python/agent.py")
            demo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(demo)
            self.assertEqual(demo.customer_agent("demo-001")["status"], "shipped")
            with self.assertRaises(LookupError):
                demo.customer_agent("missing")
            self.assertTrue(aegis.flush())
            self.assertEqual(sdk.diagnostics()["exported_spans"], 4)
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
                listing = client.get("/api/v1/traces").json()
                self.assertEqual(listing["total"], 2)
                for summary in listing["items"]:
                    detail = client.get("/api/v1/traces/" + summary["trace_id"]).json()
                    self.assertEqual(len(detail["spans"]), 2)
                    self.assertEqual(detail["missing_parent_ids"], [])
                    payload = str(detail)
                    self.assertNotIn("missing", payload.replace("missing_parent_ids", ""))
                    self.assertNotIn("demo-001", payload)
            self.assertTrue(sdk.shutdown())
        finally:
            aegis.shutdown()
            server.should_exit = True
            worker.join(5)
            listener.close()
            self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
