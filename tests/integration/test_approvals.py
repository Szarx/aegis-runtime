import concurrent.futures
import os
import unittest
import uuid

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_collector.storage.approvals import ApprovalConflict
from tests.fixtures.otlp import request_for
from aegis_collector.ingestion.otlp import decode
from collector.tests.test_approvals import payload

DATABASE = os.environ.get("AEGIS_TEST_DATABASE_URL")


@unittest.skipUnless(DATABASE, "dedicated PostgreSQL required")
class ApprovalPostgres(unittest.TestCase):
    def setUp(self):
        self.schema = "test_approval_" + uuid.uuid4().hex
        self.store = PostgresSpanStore(DATABASE, self.schema)
        self.store.migrate()

    def tearDown(self):
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def expire(self, action):
        # Test clock fixture only; there is no production update/renew endpoint.
        with self.store.connection() as connection:
            connection.execute(sql.SQL("UPDATE {}.approvals SET created_at=clock_timestamp()-INTERVAL '601 seconds', expires_at=clock_timestamp()-INTERVAL '1 second' WHERE action_id=%s").format(sql.Identifier(self.schema)), [action])

    def test_ac1003_idempotent_binding_rejects_changes_and_preserves_deadline(self):
        data = payload(); first = self.store.create_approval(data)
        self.assertEqual(self.store.create_approval(data), first)
        for key, value in data.items():
            if key == "action_id": continue
            change = {key: 301 if key == "ttl_seconds" else "c"*64 if key in ("arguments_hmac", "policy_digest") else "changed"}
            if key in ("trace_id", "span_id"):
                change = dict(trace_id="1"*32, span_id="2"*16)
            with self.subTest(key=key), self.assertRaises(ApprovalConflict): self.store.create_approval({**data, **change})
        self.assertEqual(self.store.list_approvals()["items"], [first])

    def test_ac1003_opposing_concurrent_decisions_only_one_wins(self):
        self.store.create_approval(payload())
        def decide(value):
            try: return self.store.decide_approval("1"*32, value, "server-reviewer")
            except ApprovalConflict: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, ("approved", "rejected")))
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        first = winners[0]
        self.assertEqual(self.store.decide_approval("1"*32, first["status"], "different-reviewer"), first)
        self.assertEqual(first["reviewer"], "server-reviewer")

    def test_ac1003_expired_pending_approved_and_rejected(self):
        for index, decision in enumerate((None, "approved", "rejected"), 1):
            data = {**payload(), "action_id": f"{index:032x}"}
            self.store.create_approval(data)
            if decision: self.store.decide_approval(data["action_id"], decision, "reviewer")
            self.expire(data["action_id"])
            record = self.store.create_approval(data)
            self.assertEqual(record["status"], "rejected" if decision == "rejected" else "expired")
            with self.assertRaises(ApprovalConflict): self.store.decide_approval(data["action_id"], decision or "approved", "reviewer")

    def test_ac1003_schema2_upgrade_preserves_spans_and_rebuild_preserves_approvals(self):
        self.store.insert(decode(request_for().SerializeToString())[0])
        with self.store.connection() as connection:
            connection.execute(sql.SQL("DROP TABLE {}.reviewed_actions").format(sql.Identifier(self.schema)))
            connection.execute(sql.SQL("DROP TABLE {}.approvals").format(sql.Identifier(self.schema)))
            connection.execute(sql.SQL("DELETE FROM {}.schema_version WHERE version IN (3,4)").format(sql.Identifier(self.schema)))
        self.store.migrate()
        first = self.store.create_approval(payload())
        reconstructed = PostgresSpanStore(DATABASE, self.schema)
        reconstructed.migrate(); reconstructed.ping()
        self.assertEqual(reconstructed.list_approvals()["items"], [first])
        self.assertEqual(reconstructed.list_traces()["total"], 1)

    def test_ac1005_http_create_review_and_conflicts_use_server_reviewer(self):
        with TestClient(create_app(self.store, api_token="trace", approval_request_token="producer", approval_review_token="review", approval_reviewer="server-reviewer")) as client:
            producer = {"Authorization": "Bearer producer"}; reviewer = {"Authorization": "Bearer review"}
            response = client.post("/api/v1/approvals", headers=producer, json=payload())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "pending")
            self.assertEqual(client.post("/api/v1/approvals", headers=producer, json={**payload(), "summary": "other"}).status_code, 409)
            route = "/api/v1/approvals/"+"1"*32+"/decision"
            first = client.post(route, headers=reviewer, json={"decision": "approved"})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["reviewer"], "server-reviewer")
            self.assertEqual(client.post(route, headers=reviewer, json={"decision": "approved"}).json(), first.json())
            self.assertEqual(client.post(route, headers=reviewer, json={"decision": "rejected"}).status_code, 409)
            self.assertEqual(client.get("/api/v1/approvals", headers=reviewer).json()["total"], 1)
