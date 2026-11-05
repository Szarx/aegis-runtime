import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from aegis_collector.api import create_app


def payload():
    return dict(action_id="1"*32, subject="agent", tool="write", permission="records.write", policy_revision="r1",
                policy_digest="a"*64, arguments_hmac="b"*64, summary="Synthetic request", ttl_seconds=300, trace_id=None, span_id=None)


class ApprovalAPI(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.list_approvals.return_value = dict(items=[], total=0, limit=20, offset=0)
        self.client = TestClient(create_app(self.store, api_token="trace", approval_request_token="producer", approval_review_token="reviewer"))

    def test_ac1002_roles_are_independent_and_auth_precedes_body(self):
        for method, path, correct in (("GET", "/api/v1/approvals", "reviewer"), ("POST", "/api/v1/approvals", "producer"), ("POST", "/api/v1/approvals/"+"1"*32+"/decision", "reviewer")):
            for token in ("", "trace", "producer", "reviewer"):
                if token == correct: continue
                response = self.client.request(method, path, headers={"Authorization": "Bearer "+token}, content=b"invalid")
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"error": "unauthorized"})
        self.assertEqual(self.client.get("/api/v1/approvals", headers={"Authorization": "Bearer reviewer"}).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/traces", headers={"Authorization": "Bearer reviewer"}).status_code, 401)
        self.store.create_approval.assert_not_called(); self.store.decide_approval.assert_not_called()

    def test_ac1002_disabled_and_invalid_partial_or_reused_secrets(self):
        self.assertEqual(TestClient(create_app(None)).get("/api/v1/approvals").status_code, 503)
        for config in (dict(approval_request_token="x"), dict(approval_request_token="x", approval_review_token="x"),
                       dict(api_token="x", approval_request_token="x", approval_review_token="y"),
                       dict(approval_request_token="", approval_review_token="y"), dict(approval_reviewer="bad actor")):
            with self.assertRaisesRegex(ValueError, "^invalid approval"): create_app(None, **config)

    def test_ac1002_strict_fields_and_limits(self):
        headers = {"Authorization": "Bearer producer"}
        for change in ({"ttl_seconds": True}, {"ttl_seconds": "30"}, {"ttl_seconds": 29}, {"ttl_seconds": 601},
                       {"actor": "admin"}, {"arguments": {"private": "x"}}, {"action_id": "0"*32},
                       {"subject": "bad\n"}, {"trace_id": "1"*32}, {"summary": "\x00"}):
            with self.subTest(change=change):
                self.assertEqual(self.client.post("/api/v1/approvals", headers=headers, json={**payload(), **change}).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/approvals", headers={**headers, "Content-Type": "application/json"}, content=b"x"*16385).status_code, 413)
        chunks = (b"x"*8192 for _ in range(3))
        self.assertEqual(self.client.post("/api/v1/approvals", headers={**headers, "Content-Type": "application/json"}, content=chunks).status_code, 413)
        self.assertEqual(self.client.post("/api/v1/approvals", headers={**headers, "Content-Type": "application/json"}, content=b'{"summary":"\\ud800"}').status_code, 400)
        self.assertEqual(self.client.post("/api/v1/approvals", headers={**headers, "Content-Type": "text/plain"}, content=b"{}").status_code, 415)
        self.assertEqual(self.client.post("/api/v1/approvals", headers={**headers, "Content-Type": "application/json"}, content=b'{"decision":"approved","decision":"rejected"}').status_code, 400)
        self.store.create_approval.assert_not_called()

    def test_ac1002_decision_rejects_actor_and_pagination_is_bounded(self):
        headers = {"Authorization": "Bearer reviewer"}
        for data in ({"decision": "approved", "reviewer": "other"}, {"decision": True}, {"decision": "execute"}):
            self.assertEqual(self.client.post("/api/v1/approvals/"+"1"*32+"/decision", headers=headers, json=data).status_code, 400)
        for query in ("limit=0", "limit=101", "offset=10001", "offset=-1"):
            self.assertEqual(self.client.get("/api/v1/approvals?"+query, headers=headers).status_code, 400)
        self.store.decide_approval.assert_not_called()
