"""Public query response schemas; distinct from OTLP and local JSONL."""

from typing import Literal

from pydantic import BaseModel, StrictInt, StrictStr


class ApiError(BaseModel):
    error: str


class TraceSummary(BaseModel):
    trace_id: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    duration_ns: int
    span_count: int
    status: Literal["UNSET", "ERROR"]
    agent_names: list[str]
    graph_outcome: Literal["completed", "closed", "error", "cancelled"] | None = None
    governance_signal: Literal["denied", "tool_error", "approval_requested", "review_tool_returned"] | None = None


class TraceList(BaseModel):
    items: list[TraceSummary]
    total: int
    limit: int
    offset: int


class SpanView(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    operation: Literal["invoke_agent", "execute_tool", "chat"]
    kind: Literal["INTERNAL", "CLIENT"]
    status: Literal["UNSET", "ERROR"]
    service_name: str
    agent_name: str | None
    start_time_unix_nano: int
    end_time_unix_nano: int
    resource: dict[str, str]
    scope: dict[str, str]
    attributes: dict[str, StrictStr | StrictInt]
    events: list[dict]
    resource_schema_url: str
    scope_schema_url: str


class TraceDetail(BaseModel):
    trace: TraceSummary
    spans: list[SpanView]
    missing_parent_ids: list[str]
