"""Native asyncio reviewed calls. Cancellation never retries business work."""

import asyncio
import json
import time
import uuid

from aegis.governance import governed_tool_span
from .approvals import ApprovalUnavailable, _hex
from .reviewed_execution import BINDING, ExecutionResult, ReviewedClient, _ReviewedToolCore, reviewed_snapshot


class AsyncReviewedClient(ReviewedClient):
    def __init__(self, endpoint, *, token, execution_token, binding_key, timeout=3, transport=None):
        super().__init__(endpoint, token=token, execution_token=execution_token, binding_key=binding_key, timeout=timeout)
        try:
            import httpx
        except ImportError:
            raise ImportError("install aegis-runtime-control[reviewed-async] to use async reviewed execution") from None
        self._transport = transport if transport is not None else httpx.AsyncHTTPTransport(
            retries=0, limits=httpx.Limits(max_connections=4, max_keepalive_connections=4), trust_env=False)
        self._http = httpx.AsyncClient(transport=self._transport, trust_env=False, follow_redirects=False, timeout=timeout)
        self._loop = None
        self._closing = self._closed = False

    def _bind_loop(self):
        current = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not current:
            raise ValueError("async reviewed client requires its original event loop")
        self._loop = current

    def _open(self):
        self._bind_loop()
        if self._closing or self._closed:
            raise ApprovalUnavailable()

    async def __aenter__(self):
        self._open()
        return self

    async def __aexit__(self, kind, error, traceback):
        try:
            await self.aclose()
        except Exception:
            if kind is None:
                raise

    async def aclose(self):
        self._bind_loop()
        if self._closed:
            return
        self._closing = True
        try:
            async with asyncio.timeout(self._timeout):
                # HTTPX marks itself closed before transport cleanup; an explicit
                # retry after interrupted cleanup must still close our transport.
                if self._http.is_closed:
                    await self._transport.aclose()
                else:
                    await self._http.aclose()
            self._closed = True
        except Exception:
            raise ApprovalUnavailable() from None

    def prepare(self, *args, **kwargs):
        raise TypeError("use await AsyncReviewedTool.prepare for async reviewed execution")

    async def _send_async(self, path, payload, *, execution=False):
        self._open()
        await asyncio.sleep(0)
        self._open()
        token = self._execution_token if execution else self._token
        raw = bytearray()
        try:
            async with asyncio.timeout(self._timeout):
                async with self._http.stream("POST", self._endpoint + path,
                                             content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
                                             headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept-Encoding": "identity"}) as response:
                    if response.status_code != 200 or response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ApprovalUnavailable()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > 65536:
                            raise ApprovalUnavailable()
                        raw.extend(chunk)
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ApprovalUnavailable()
                    result[key] = value
                return result
            return json.loads(bytes(raw), object_pairs_hook=unique)
        except Exception:
            raise ApprovalUnavailable() from None

    async def prepare_reviewed(self, payload):
        result = await self._send_async("/api/v1/reviewed-actions", payload)
        return self._record(payload, result)

    async def claim(self, payload):
        if not _hex(payload.get("action_id"), 32):
            raise ValueError("invalid reviewed action identifier")
        claim_id = uuid.uuid4().hex
        binding = {key: payload[key] for key in BINDING}
        start = time.monotonic()
        result = await self._send_async("/api/v1/reviewed-actions/" + payload["action_id"] + "/claim", {**binding, "claim_id": claim_id}, execution=True)
        result = self._record(payload, result, claim=True)
        if result["status"] != "approved" or result["execution_state"] != "claimed" or result["claim_id"] != claim_id:
            raise ApprovalUnavailable()
        return result, start + result["remaining_ms"] / 1000

    async def complete(self, payload, claim_id, outcome):
        if not _hex(payload.get("action_id"), 32) or not _hex(claim_id, 32) or outcome not in ("completed", "failed"):
            raise ValueError("invalid reviewed completion")
        result = await self._send_async("/api/v1/reviewed-actions/" + payload["action_id"] + "/complete", {"claim_id": claim_id, "outcome": outcome}, execution=True)
        result = self._record(payload, result)
        if result["execution_state"] != outcome or result["claim_id"] != claim_id:
            raise ApprovalUnavailable()
        return result


class AsyncReviewedTool(_ReviewedToolCore):
    def __init__(self, function, *, client: AsyncReviewedClient, policy, subject: str, permission: str,
                 tool: str, tool_revision: str, disclose_arguments=False):
        self._configure(function, client=client, policy=policy, subject=subject, permission=permission,
                        tool=tool, tool_revision=tool_revision, disclose_arguments=disclose_arguments,
                        client_type=AsyncReviewedClient, asynchronous=True)

    async def _invoke(self, snapshot, *, deadline):
        return await self._function(**snapshot)

    async def prepare(self, arguments, *, summary, action_id=None, ttl_seconds=300, trace_id=None, span_id=None):
        await asyncio.sleep(0)
        payload = self._prepare(uuid.uuid4().hex if action_id is None else action_id, arguments, summary, ttl_seconds, trace_id=trace_id, span_id=span_id)
        return await self._client.prepare_reviewed(payload)

    async def resume(self, action_id, arguments, *, summary, ttl_seconds=300, trace_id=None, span_id=None):
        await asyncio.sleep(0)
        payload = self._prepare(action_id, arguments, summary, ttl_seconds, trace_id=trace_id, span_id=span_id)
        record, deadline = await self._client.claim(payload)
        # Cancellation here leaves a consumed claim without starting the tool.
        await asyncio.sleep(0)
        decision = self._allow(action_id)
        snapshot, digest = reviewed_snapshot(payload["review_arguments"])
        if digest != payload["review_digest"] or time.monotonic() >= deadline:
            raise ApprovalUnavailable()
        with governed_tool_span(self._tool, permission=self._permission, subject=self._runtime.subject,
                                action_id=action_id, effect=decision.effect, reason=decision.reason,
                                approval_phase="execute" if decision.effect=="require_approval" else None,
                                policy_revision=decision.policy_revision, rule_id=decision.rule_id):
            await asyncio.sleep(0)
            self._allow(action_id)
            if time.monotonic() >= deadline:
                raise ApprovalUnavailable()
            try:
                value = await self._invoke(snapshot, deadline=deadline)
            except asyncio.CancelledError:
                # A cancelled function may already have side effects. Never
                # label cancellation as failure or schedule detached completion.
                raise
            except BaseException:
                try:
                    await self._client.complete(payload, record["claim_id"], "failed")
                except Exception:
                    pass
                raise
            try:
                await self._client.complete(payload, record["claim_id"], "completed")
                confirmation = "confirmed"
            except Exception:
                confirmation = "unknown"
            return ExecutionResult(value, confirmation)
