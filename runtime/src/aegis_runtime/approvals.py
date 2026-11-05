"""Approval preparation only. This module never receives or executes a tool."""

import hashlib
import hmac
import json
import math
import re
from dataclasses import asdict
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from aegis_policy import Policy, identifier


class ApprovalUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("approval service unavailable")


def canonical_arguments(value) -> bytes:
    """Bounded exact JSON types, without invoking user-defined conversion hooks."""
    active = set()
    nodes = 0

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if nodes > 16384:
            raise ValueError("invalid approval arguments")
        if depth > 16:
            raise ValueError("invalid approval arguments")
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is int and -(2**63) <= item < 2**63:
            return
        if kind is str and len(item) <= 2048:
            return
        if kind not in (dict, list) or len(item) > 128 or id(item) in active:
            raise ValueError("invalid approval arguments")
        active.add(id(item))
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str or len(key) > 2048:
                        raise ValueError("invalid approval arguments")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(id(item))

    visit(value, 0)
    try:
        raw = bytearray()
        for chunk in json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False).iterencode(value):
            encoded = chunk.encode("utf-8")
            if len(raw) + len(encoded) > 16384:
                raise ValueError("invalid approval arguments")
            raw.extend(encoded)
    except (ValueError, UnicodeError):
        raise ValueError("invalid approval arguments") from None
    return bytes(raw)


def policy_digest(policy: Policy) -> str:
    if type(policy) is not Policy:
        raise ValueError("invalid approval policy")
    snapshot = {"schema_version": "aegis.policy.v1", **asdict(policy)}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _hex(value, width):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", value) and int(value, 16) != 0


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ApprovalClient:
    def __init__(self, endpoint: str, *, token: str, binding_key: bytes, timeout: float = 3):
        try:
            url = urlsplit(endpoint)
            valid = url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost", "::1") and not (
                url.username or url.password or url.query or url.fragment or url.path
            )
            port = url.port
            valid = valid and (port is None or 1 <= port <= 65535)
        except (ValueError, TypeError):
            valid = False
        if not valid or type(token) is not str or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("invalid approval client configuration")
        if type(binding_key) is not bytes or len(binding_key) < 32 or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
            raise ValueError("invalid approval client configuration")
        self._endpoint, self._token, self._key, self._timeout = endpoint, token, binding_key, timeout
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _payload(self, *, action_id: str, subject: str, tool: str, permission: str, policy: Policy,
                arguments, summary: str, ttl_seconds: int = 300, trace_id: str | None = None,
                span_id: str | None = None) -> dict:
        if not _hex(action_id, 32) or type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 600:
            raise ValueError("invalid approval request")
        for value in (subject, tool, permission):
            identifier(value)
        if type(summary) is not str or not summary.strip() or len(summary) > 512 or any(ord(c) < 32 for c in summary):
            raise ValueError("invalid approval summary")
        try:
            summary.encode("utf-8")
        except UnicodeError:
            raise ValueError("invalid approval summary") from None
        if not (trace_id is span_id is None) and not (_hex(trace_id, 32) and _hex(span_id, 16)):
            raise ValueError("invalid approval trace")
        digest = policy_digest(policy)
        payload = dict(action_id=action_id, subject=subject, tool=tool, permission=permission,
                       policy_revision=policy.revision, policy_digest=digest,
                       arguments_hmac=hmac.new(self._key, canonical_arguments(arguments), hashlib.sha256).hexdigest(),
                       summary=summary, ttl_seconds=ttl_seconds, trace_id=trace_id, span_id=span_id)
        return payload

    def prepare(self, *, action_id: str, subject: str, tool: str, permission: str, policy: Policy,
                arguments, summary: str, ttl_seconds: int = 300, trace_id: str | None = None,
                span_id: str | None = None) -> dict:
        payload = self._payload(action_id=action_id, subject=subject, tool=tool, permission=permission, policy=policy, arguments=arguments, summary=summary, ttl_seconds=ttl_seconds, trace_id=trace_id, span_id=span_id)
        request = Request(self._endpoint + "/api/v1/approvals", data=json.dumps(payload).encode(), method="POST",
                          headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise ApprovalUnavailable()
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ApprovalUnavailable()
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ApprovalUnavailable()
                        result[key] = value
                    return result
                result = json.loads(raw, object_pairs_hook=unique)
            return self._validate(payload, result)
        except Exception:
            raise ApprovalUnavailable() from None

    @staticmethod
    def _validate(payload, result):
        if type(result) is not dict or set(result) != set(payload) | {"status", "created_at", "expires_at", "decided_at", "reviewer"} or any(result.get(key) != value or type(result.get(key)) is not type(value) for key, value in payload.items()):
            raise ApprovalUnavailable()
        if result.get("status") not in ("pending", "approved", "rejected", "expired"):
            raise ApprovalUnavailable()
        times = [datetime.fromisoformat(result[key].replace("Z", "+00:00")) for key in ("created_at", "expires_at")]
        if any(t.tzinfo is None or t.utcoffset().total_seconds() != 0 for t in times) or (times[1] - times[0]).total_seconds() != payload["ttl_seconds"]:
            raise ApprovalUnavailable()
        decided, reviewer = result.get("decided_at"), result.get("reviewer")
        if (decided is None) != (reviewer is None) or (result["status"] == "pending" and decided is not None) or (result["status"] in ("approved", "rejected") and decided is None):
            raise ApprovalUnavailable()
        if decided is not None:
            stamp = datetime.fromisoformat(decided.replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0 or not times[0] <= stamp < times[1]:
                raise ApprovalUnavailable()
            identifier(reviewer)
        return result
