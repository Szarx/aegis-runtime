"""Local development API defined by SPEC-002."""

import secrets
import re
from typing import Annotated, Literal

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from google.rpc.status_pb2 import Status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
from starlette.concurrency import run_in_threadpool

from .. import __version__
from ..ingestion.otlp import MAX_BODY_BYTES, MAX_NANO, InvalidPayload, TooManySpans, decode
from ..storage import PostgresSpanStore, StorageError
from .models import ApiError, TraceDetail, TraceList

MEDIA_TYPE = "application/x-protobuf"


def protocol_error(code: int, message: str) -> Response:
    return Response(Status(message=message).SerializeToString(), status_code=code, media_type=MEDIA_TYPE)


def json_error(code: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=code)


def create_app(store: PostgresSpanStore, *, api_token: str | None = None,
               approval_request_token: str | None = None, approval_review_token: str | None = None,
               approval_reviewer: str = "local-reviewer", approval_execution_token: str | None = None,
               approval_executor: str = "local-executor") -> FastAPI:
    configured = (approval_request_token, approval_review_token)
    if any(value is not None for value in configured):
        if any(type(value) is not str or not value or any(ord(c) < 33 or ord(c) > 126 for c in value) for value in configured) or len(set(configured)) != 2 or api_token in configured:
            raise ValueError("invalid approval authentication configuration")
    if type(approval_reviewer) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", approval_reviewer):
        raise ValueError("invalid approval reviewer configuration")
    if approval_execution_token is not None:
        if approval_request_token is None or type(approval_execution_token) is not str or not approval_execution_token or approval_execution_token in (*configured, api_token) or any(ord(c) < 33 or ord(c) > 126 for c in approval_execution_token):
            raise ValueError("invalid approval execution configuration")
    if type(approval_executor) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", approval_executor):
        raise ValueError("invalid approval executor configuration")
    app = FastAPI(title="Aegis Collector", version=__version__)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        reviewed = request.url.path == "/api/v1/reviewed-actions" or request.url.path.startswith("/api/v1/reviewed-actions/")
        approval = reviewed or request.url.path == "/api/v1/approvals" or request.url.path.startswith("/api/v1/approvals/")
        if approval:
            if approval_request_token is None or (reviewed and approval_execution_token is None):
                return json_error(503, "approvals disabled")
            producer = request.method == "POST" and request.url.path in ("/api/v1/approvals", "/api/v1/reviewed-actions")
            execution = reviewed and request.method == "POST" and request.url.path.endswith(("/claim", "/complete"))
            expected = "Bearer " + (approval_request_token if producer else approval_execution_token if execution else approval_review_token)
            if not secrets.compare_digest(request.headers.get("authorization", "").encode(), expected.encode()):
                result = json_error(401, "unauthorized")
                result.headers["WWW-Authenticate"] = "Bearer"
                return result
            result = await call_next(request)
            result.headers["Cache-Control"] = "no-store"
            result.headers["Vary"] = "Authorization"
            return result
        protected = request.url.path in ("/v1/traces", "/v1/health") or request.url.path.startswith("/api/v1/")
        if protected and api_token:
            supplied = request.headers.get("authorization", "")
            expected = f"Bearer {api_token}"
            if not secrets.compare_digest(supplied.encode(), expected.encode()):
                result = protocol_error(401, "unauthorized") if request.url.path == "/v1/traces" else json_error(401, "unauthorized")
                result.headers["WWW-Authenticate"] = "Bearer"
                if request.url.path == '/api/v1/security-events':
                    result.headers['Cache-Control']='no-store';result.headers['Vary']='Authorization'
                return result
        result = await call_next(request)
        if request.url.path == '/api/v1/security-events':
            result.headers['Cache-Control']='no-store';result.headers['Vary']='Authorization'
        return result

    @app.exception_handler(RequestValidationError)
    async def invalid_parameters(request, error):
        return json_error(400, "invalid query or path parameter")

    from .health import install_routes as install_health
    install_health(app)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", responses={503: {"model": ApiError}})
    def ready():
        try:
            store.ping()
        except StorageError:
            return json_error(503, "not ready")
        return {"status": "ok"}

    @app.post(
        "/v1/traces",
        response_class=Response,
        responses={code: {"content": {MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}}} for code in (200, 400, 401, 413, 415, 503)},
        openapi_extra={"requestBody": {"required": True, "content": {MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}}}},
    )
    async def receive(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != MEDIA_TYPE:
            return protocol_error(415, "unsupported content type")
        if request.headers.get("content-encoding", "identity").lower() != "identity":
            return protocol_error(415, "unsupported content encoding")
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError
            except ValueError:
                return protocol_error(400, "invalid content length")
            if length > MAX_BODY_BYTES:
                return protocol_error(413, "request limit exceeded")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return protocol_error(413, "request limit exceeded")
            body.extend(chunk)
        try:
            accepted, rejected = decode(bytes(body))
        except InvalidPayload:
            return protocol_error(400, "invalid protobuf request")
        except TooManySpans:
            return protocol_error(413, "batch span limit exceeded")
        try:
            if accepted:
                await run_in_threadpool(store.insert, accepted)
        except StorageError:
            return protocol_error(503, "storage unavailable")
        result = ExportTraceServiceResponse()
        if rejected:
            result.partial_success.rejected_spans = rejected
            result.partial_success.error_message = "unsupported or invalid native spans"
        return Response(result.SerializeToString(), media_type=MEDIA_TYPE)

    @app.get("/api/v1/traces", response_model=TraceList,
             responses={code: {"model": ApiError} for code in (400, 401, 503, "4XX")})
    def trace_list(
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        agent_name: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        service_name: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        status: Literal["UNSET", "ERROR"] | None = None,
        started_after_ns: Annotated[int | None, Query(ge=1, le=MAX_NANO)] = None,
        started_before_ns: Annotated[int | None, Query(ge=1, le=MAX_NANO)] = None,
    ):
        if any(value is not None and (not value.strip() or "\x00" in value) for value in (agent_name, service_name)):
            return json_error(400, "invalid filter")
        if started_after_ns is not None and started_before_ns is not None and started_after_ns > started_before_ns:
            return json_error(400, "invalid time interval")
        try:
            return store.list_traces(
                limit=limit, offset=offset, agent_name=agent_name, service_name=service_name,
                status=status, started_after_ns=started_after_ns, started_before_ns=started_before_ns,
            )
        except StorageError:
            return json_error(503, "storage unavailable")

    @app.get("/api/v1/traces/{trace_id}", response_model=TraceDetail,
             responses={code: {"model": ApiError} for code in (400, 401, 404, 503, "4XX")})
    def trace_detail(trace_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
        if not int(trace_id, 16):
            return json_error(400, "invalid trace identifier")
        try:
            result = store.trace_detail(trace_id)
        except StorageError:
            return json_error(503, "storage unavailable")
        return result if result is not None else json_error(404, "trace not found")

    from .approvals import install_routes
    install_routes(app, store, approval_reviewer, approval_executor)
    from .security import install_routes as install_security
    install_security(app, store)
    return app
