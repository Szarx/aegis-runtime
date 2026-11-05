"""Bounded approval preparation endpoints; no execution capability."""

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, model_validator
from starlette.concurrency import run_in_threadpool

from ..storage import StorageError
from ..storage.approvals import ApprovalConflict, ApprovalMissing
from .models import ApiError


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action_id: StrictStr = Field(pattern=r"^[0-9a-f]{32}$")
    subject: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    tool: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    permission: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    policy_revision: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    policy_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    arguments_hmac: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    summary: StrictStr = Field(min_length=1, max_length=512)
    ttl_seconds: StrictInt = Field(ge=30, le=600)
    trace_id: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    span_id: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def valid_binding(self):
        try:
            self.summary.encode("utf-8")
        except UnicodeError:
            raise ValueError("invalid approval summary") from None
        if int(self.action_id, 16) == 0 or not self.summary.strip() or any(ord(c) < 32 for c in self.summary):
            raise ValueError("invalid approval binding")
        if (self.trace_id is None) != (self.span_id is None):
            raise ValueError("invalid approval trace")
        if self.trace_id is not None and (not int(self.trace_id, 16) or not int(self.span_id, 16)):
            raise ValueError("invalid approval trace")
        return self


class ApprovalRecord(ApprovalRequest):
    status: Literal["pending", "approved", "rejected", "expired"]
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    reviewer: str | None


class ApprovalList(BaseModel):
    items: list[ApprovalRecord]
    total: int
    limit: int
    offset: int


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["approved", "rejected"]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def install_routes(app, store, reviewer, executor="local-executor"):
    # Import here to keep response helpers in the existing API module.
    from .app import json_error

    async def body(request, model):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json" or request.headers.get("content-encoding", "identity").lower() != "identity":
            return json_error(415, "unsupported content type or encoding")
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError
            except ValueError:
                return json_error(400, "invalid content length")
            if length > 16384:
                return json_error(413, "request limit exceeded")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 16384:
                return json_error(413, "request limit exceeded")
            raw.extend(chunk)
        try:
            value = json.loads(bytes(raw), object_pairs_hook=_unique)
            return model.model_validate(value)
        except (ValueError, ValidationError, UnicodeError, RecursionError):
            return json_error(400, "invalid approval request")

    errors = {code: {"model": ApiError} for code in (400, 401, 404, 409, 413, 415, 503, "4XX")}

    @app.post("/api/v1/approvals", response_model=ApprovalRecord, responses=errors,
              openapi_extra={"requestBody": {"required": True, "content": {"application/json": {"schema": ApprovalRequest.model_json_schema()}}}})
    async def prepare(request: Request):
        value = await body(request, ApprovalRequest)
        if not isinstance(value, ApprovalRequest):
            return value
        try:
            return await run_in_threadpool(store.create_approval, value.model_dump())
        except ApprovalConflict:
            return json_error(409, "approval binding conflict")
        except StorageError:
            return json_error(503, "storage unavailable")

    from .reviewed import install_routes as install_reviewed
    install_reviewed(app, store, reviewer, executor, body, errors)

    @app.get("/api/v1/approvals", response_model=ApprovalList, responses=errors)
    def listing(limit: Annotated[int, Query(ge=1, le=100)] = 20,
                offset: Annotated[int, Query(ge=0, le=10000)] = 0):
        try:
            return store.list_approvals(limit=limit, offset=offset)
        except StorageError:
            return json_error(503, "storage unavailable")

    @app.post("/api/v1/approvals/{action_id}/decision", response_model=ApprovalRecord, responses=errors,
              openapi_extra={"requestBody": {"required": True, "content": {"application/json": {"schema": ApprovalDecision.model_json_schema()}}}})
    async def decide(request: Request, action_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
        if not int(action_id, 16):
            return json_error(400, "invalid action identifier")
        value = await body(request, ApprovalDecision)
        if not isinstance(value, ApprovalDecision):
            return value
        try:
            return await run_in_threadpool(store.decide_approval, action_id, value.decision, reviewer)
        except ApprovalMissing:
            return json_error(404, "approval not found")
        except ApprovalConflict:
            return json_error(409, "approval decision conflict")
        except StorageError:
            return json_error(503, "storage unavailable")
