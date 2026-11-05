"""Explicit synchronous execution after a reviewed, non-renewable claim."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import inspect
import json
import time
import uuid
from urllib.request import Request

from aegis.governance import governed_tool_span
from aegis_policy import Policy, identifier
from . import Runtime, ActionDenied
from .approvals import ApprovalClient, ApprovalUnavailable, canonical_arguments, _hex

EXTRA = {"tool_revision", "review_arguments", "review_digest", "execution_state", "claim_id", "executor", "claimed_at", "finished_at"}
BINDING = ("subject", "tool", "permission", "policy_revision", "policy_digest", "arguments_hmac", "tool_revision", "review_digest", "summary", "ttl_seconds")


def reviewed_snapshot(arguments):
    if type(arguments) is not dict: raise ValueError("reviewed arguments must be a dict")
    raw = canonical_arguments(arguments)
    if len(raw) > 4096:
        raise ValueError("invalid reviewed arguments")
    snapshot = json.loads(raw)
    def check(value):
        if type(value) is str and "\x00" in value: raise ValueError("invalid reviewed arguments")
        if type(value) is dict:
            for key, child in value.items(): check(key); check(child)
        if type(value) is list:
            for child in value: check(child)
    check(snapshot)
    return snapshot, hashlib.sha256(raw).hexdigest()


class ReviewedClient(ApprovalClient):
    def __init__(self, endpoint, *, token, execution_token, binding_key, timeout=3):
        super().__init__(endpoint, token=token, binding_key=binding_key, timeout=timeout)
        # Reuse the exact configuration checks; never infer a token from env.
        ApprovalClient(endpoint, token=execution_token, binding_key=binding_key, timeout=timeout)
        if token == execution_token: raise ValueError("execution credential must be distinct")
        self._execution_token = execution_token

    def _send(self, path, payload, *, execution=False):
        token = self._execution_token if execution else self._token
        request = Request(self._endpoint + path, data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), method="POST",
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200: raise ApprovalUnavailable()
                raw = response.read(65537)
                if len(raw) > 65536: raise ApprovalUnavailable()
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result: raise ApprovalUnavailable()
                        result[key] = value
                    return result
                return json.loads(raw, object_pairs_hook=unique)
        except Exception: raise ApprovalUnavailable() from None

    def _record(self, expected, result, *, claim=False):
        try:
            if type(result) is not dict: raise ApprovalUnavailable()
            metadata = EXTRA | ({"remaining_ms"} if claim else set())
            base = {key: value for key, value in result.items() if key not in metadata}
            base_expected = {key: value for key, value in expected.items() if key not in EXTRA}
            self._validate(base_expected, base)
            if set(result) != set(base) | metadata or any(result[key] != expected[key] for key in ("tool_revision", "review_digest")):
                raise ApprovalUnavailable()
            snapshot, digest = reviewed_snapshot(result["review_arguments"])
            if digest != expected["review_digest"]: raise ApprovalUnavailable()
            state = result["execution_state"]
            if state not in ("available", "claimed", "completed", "failed"): raise ApprovalUnavailable()
            if state == "available":
                if any(result[key] is not None for key in ("claim_id", "executor", "claimed_at", "finished_at")): raise ApprovalUnavailable()
            else:
                if not _hex(result["claim_id"], 32): raise ApprovalUnavailable()
                identifier(result["executor"])
                stamp = datetime.fromisoformat(result["claimed_at"].replace("Z", "+00:00"))
                created = datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
                expires = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
                if stamp.utcoffset().total_seconds() != 0 or not created <= stamp < expires: raise ApprovalUnavailable()
                if state == "claimed" and result["finished_at"] is not None: raise ApprovalUnavailable()
                if state in ("completed", "failed"):
                    finished = datetime.fromisoformat(result["finished_at"].replace("Z", "+00:00"))
                    if finished.utcoffset().total_seconds() != 0 or finished < stamp: raise ApprovalUnavailable()
            if claim and (type(result["remaining_ms"]) is not int or not 0 <= result["remaining_ms"] <= expected["ttl_seconds"] * 1000):
                raise ApprovalUnavailable()
            return result
        except Exception: raise ApprovalUnavailable() from None

    def prepare_reviewed(self, payload):
        result = self._send("/api/v1/reviewed-actions", payload)
        return self._record(payload, result)

    def claim(self, payload):
        if not _hex(payload.get("action_id"), 32): raise ValueError("invalid reviewed action identifier")
        claim_id = uuid.uuid4().hex
        binding = {key: payload[key] for key in BINDING}
        start = time.monotonic()
        result = self._send("/api/v1/reviewed-actions/" + payload["action_id"] + "/claim", {**binding, "claim_id": claim_id}, execution=True)
        result = self._record(payload, result, claim=True)
        if result["status"] != "approved" or result["execution_state"] != "claimed" or result["claim_id"] != claim_id:
            raise ApprovalUnavailable()
        # Subtract the *entire* request duration, including server/parse time.
        deadline = start + result["remaining_ms"] / 1000
        return result, deadline

    def complete(self, payload, claim_id, outcome):
        if not _hex(payload.get("action_id"), 32) or not _hex(claim_id, 32) or outcome not in ("completed", "failed"):
            raise ValueError("invalid reviewed completion")
        result = self._send("/api/v1/reviewed-actions/" + payload["action_id"] + "/complete", {"claim_id": claim_id, "outcome": outcome}, execution=True)
        result = self._record(payload, result)
        if result["execution_state"] != outcome or result["claim_id"] != claim_id: raise ApprovalUnavailable()
        return result


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    value: object
    confirmation: str


class _ReviewedToolCore:
    def _configure(self, function, *, client: ReviewedClient, policy: Policy, subject: str,
                 permission: str, tool: str, tool_revision: str, disclose_arguments=False,
                 client_type=ReviewedClient, asynchronous=False):
        if disclose_arguments is not True: raise ValueError("reviewed execution requires explicit argument disclosure")
        if not inspect.isfunction(function) or inspect.iscoroutinefunction(function) != asynchronous or inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
            raise TypeError("reviewed execution requires an async function" if asynchronous else "reviewed execution requires a synchronous function")
        self._signature = inspect.signature(function)
        if any(param.kind in (param.POSITIONAL_ONLY, param.VAR_POSITIONAL, param.VAR_KEYWORD) for param in self._signature.parameters.values()):
            raise TypeError("reviewed execution requires named parameters")
        if type(client) is not client_type or type(policy) is not Policy: raise ValueError("invalid reviewed execution configuration")
        for value in (subject, permission, tool, tool_revision): identifier(value)
        self._function, self._client = function, client
        self._runtime = Runtime(policy, subject=subject)
        self._permission, self._tool, self._revision = permission, tool, tool_revision

    def _allow(self, action_id):
        decision = self._runtime._decide(self._tool, self._permission)
        if decision.effect not in ("allow", "require_approval"): raise ActionDenied(decision, action_id)
        return decision

    def _prepare(self, action_id, arguments, summary, ttl_seconds, *, trace_id=None, span_id=None):
        if type(arguments) is not dict: raise ValueError("reviewed arguments must be a dict")
        incoming, _ = reviewed_snapshot(arguments)
        bound = self._signature.bind(**incoming)
        bound.apply_defaults()
        snapshot, digest = reviewed_snapshot(dict(bound.arguments))
        payload = self._client._payload(action_id=action_id, subject=self._runtime.subject, tool=self._tool, permission=self._permission,
                                        policy=self._runtime.policy, arguments=snapshot, summary=summary, ttl_seconds=ttl_seconds, trace_id=trace_id, span_id=span_id)
        payload.update(tool_revision=self._revision, review_arguments=snapshot, review_digest=digest)
        self._allow(action_id)
        return payload

class ReviewedTool(_ReviewedToolCore):
    def __init__(self, function, *, client: ReviewedClient, policy: Policy, subject: str,
                 permission: str, tool: str, tool_revision: str, disclose_arguments=False):
        self._configure(function, client=client, policy=policy, subject=subject, permission=permission,
                        tool=tool, tool_revision=tool_revision, disclose_arguments=disclose_arguments)

    def prepare(self, arguments, *, summary, action_id=None, ttl_seconds=300, trace_id=None, span_id=None):
        payload = self._prepare(uuid.uuid4().hex if action_id is None else action_id, arguments, summary, ttl_seconds, trace_id=trace_id, span_id=span_id)
        return self._client.prepare_reviewed(payload)

    def _invoke(self, snapshot, *, deadline):
        return self._function(**snapshot)

    def resume(self, action_id, arguments, *, summary, ttl_seconds=300, trace_id=None, span_id=None):
        payload = self._prepare(action_id, arguments, summary, ttl_seconds, trace_id=trace_id, span_id=span_id)
        record, deadline = self._client.claim(payload)
        decision = self._allow(action_id)
        # The executed kwargs are reconstructed, independent of caller containers.
        snapshot, digest = reviewed_snapshot(payload["review_arguments"])
        if digest != payload["review_digest"] or time.monotonic() >= deadline:
            raise ApprovalUnavailable()
        with governed_tool_span(self._tool, permission=self._permission, subject=self._runtime.subject,
                                action_id=action_id, effect=decision.effect, reason=decision.reason,
                                approval_phase="execute" if decision.effect=="require_approval" else None,
                                policy_revision=decision.policy_revision, rule_id=decision.rule_id):
            self._allow(action_id)
            if time.monotonic() >= deadline:
                raise ApprovalUnavailable()
            try:
                value = self._invoke(snapshot, deadline=deadline)
            except BaseException:
                try: self._client.complete(payload, record["claim_id"], "failed")
                except Exception: pass
                raise
            try:
                self._client.complete(payload, record["claim_id"], "completed")
                confirmation = "confirmed"
            except Exception:
                confirmation = "unknown"
            return ExecutionResult(value, confirmation)
