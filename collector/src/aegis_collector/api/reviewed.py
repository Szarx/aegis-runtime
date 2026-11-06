"""Reviewed action protocol; business functions never enter the server."""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from starlette.concurrency import run_in_threadpool

from .approvals import ApprovalRequest, ApprovalRecord, ApprovalDecision
from ..storage import StorageError
from ..storage.approvals import ApprovalConflict, ApprovalMissing

ID = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
HASH = r"^[0-9a-f]{64}$"


def review_digest(arguments):
    # HTTP JSON has already eliminated custom objects and cycles. Validate every
    # scalar, depth and bound independently of the host SDK before hashing.
    def visit(value, depth=0):
        if depth > 16: raise ValueError("invalid reviewed arguments")
        kind = type(value)
        if value is None or kind is bool: return
        if kind is int and -(2**63) <= value < 2**63: return
        if kind is str and len(value) <= 2048 and "\x00" not in value: return
        if kind not in (list, dict) or len(value) > 128: raise ValueError("invalid reviewed arguments")
        if kind is dict:
            for key, child in value.items():
                if type(key) is not str or len(key) > 2048 or "\x00" in key: raise ValueError("invalid reviewed arguments")
                visit(child, depth + 1)
        else:
            for child in value: visit(child, depth + 1)
    if type(arguments) is not dict: raise ValueError("reviewed arguments must be an object")
    visit(arguments)
    try:
        raw = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except UnicodeError: raise ValueError("invalid reviewed arguments") from None
    if len(raw) > 4096: raise ValueError("reviewed argument limit exceeded")
    return hashlib.sha256(raw).hexdigest()


class ReviewedRequest(ApprovalRequest):
    tool_revision: StrictStr = Field(pattern=ID)
    review_arguments: dict[str, Any]
    review_digest: StrictStr = Field(pattern=HASH)

    @model_validator(mode="after")
    def valid_review(self):
        if review_digest(self.review_arguments) != self.review_digest:
            raise ValueError("invalid review digest")
        return self


class ReviewedRecord(ApprovalRecord):
    tool_revision: str
    review_arguments: dict[str, Any]
    review_digest: str
    execution_state: Literal["available", "claimed", "completed", "failed"]
    claim_id: str | None
    executor: str | None
    claimed_at: datetime | None
    finished_at: datetime | None


class ReviewedList(BaseModel):
    items: list[ReviewedRecord]
    total: int
    limit: int
    offset: int


class ReviewedDecision(ApprovalDecision):
    review_digest: StrictStr = Field(pattern=HASH)


class ClaimBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: StrictStr = Field(pattern=ID)
    tool: StrictStr = Field(pattern=ID)
    permission: StrictStr = Field(pattern=ID)
    policy_revision: StrictStr = Field(pattern=ID)
    policy_digest: StrictStr = Field(pattern=HASH)
    arguments_hmac: StrictStr = Field(pattern=HASH)
    tool_revision: StrictStr = Field(pattern=ID)
    review_digest: StrictStr = Field(pattern=HASH)
    summary: StrictStr = Field(min_length=1, max_length=512)
    ttl_seconds: StrictInt = Field(ge=30, le=600)
    claim_id: StrictStr = Field(pattern=r"^[0-9a-f]{32}$")

    @model_validator(mode="after")
    def nonzero(self):
        if not int(self.claim_id, 16): raise ValueError("invalid claim identifier")
        return self


class ClaimedRecord(ReviewedRecord):
    remaining_ms: StrictInt = Field(ge=0, le=600000)


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: StrictStr = Field(pattern=r"^[0-9a-f]{32}$")
    outcome: Literal["completed", "failed"]


def install_routes(app, store, reviewer, executor, body, errors):
    from .app import json_error

    async def write(request, model, operation, *args):
        value = await body(request, model)
        if not isinstance(value, model): return value
        try:
            return await run_in_threadpool(operation, *args, value.model_dump())
        except ApprovalMissing: return json_error(404, "reviewed action not found")
        except ApprovalConflict: return json_error(409, "reviewed action conflict")
        except StorageError: return json_error(503, "storage unavailable")

    def schema(model):
        return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}

    @app.post("/api/v1/reviewed-actions", response_model=ReviewedRecord, responses=errors, openapi_extra=schema(ReviewedRequest))
    async def prepare(request: Request):
        return await write(request, ReviewedRequest, store.create_reviewed)

    @app.get("/api/v1/reviewed-actions", response_model=ReviewedList, responses=errors)
    def listing(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        action_id: Annotated[str | None, Query(pattern=r"^[0-9a-f]{32}$")] = None,
    ):
        if action_id == "0" * 32:
            return json_error(400, "invalid action ID")
        try:
            return store.list_reviewed(limit=limit, offset=offset, action_id=action_id)
        except StorageError: return json_error(503, "storage unavailable")

    @app.post("/api/v1/reviewed-actions/{action_id}/decision", response_model=ReviewedRecord, responses=errors, openapi_extra=schema(ReviewedDecision))
    async def decide(request: Request, action_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
        return await write(request, ReviewedDecision, lambda data: store.decide_reviewed(action_id, data["decision"], data["review_digest"], reviewer))

    @app.post("/api/v1/reviewed-actions/{action_id}/claim", response_model=ClaimedRecord, responses=errors, openapi_extra=schema(ClaimBinding))
    async def claim(request: Request, action_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
        return await write(request, ClaimBinding, lambda data: store.claim_reviewed(action_id, data, executor))

    @app.post("/api/v1/reviewed-actions/{action_id}/complete", response_model=ReviewedRecord, responses=errors, openapi_extra=schema(Completion))
    async def complete(request: Request, action_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
        return await write(request, Completion, lambda data: store.complete_reviewed(action_id, data["claim_id"], data["outcome"], executor))
