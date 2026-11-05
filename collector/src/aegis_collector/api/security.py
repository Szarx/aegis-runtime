"""Read-only projection of received governance spans, not an auth authority."""
from typing import Annotated, Literal
from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ..storage import StorageError

IDENTIFIER = r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
HEX32 = r'^[0-9a-f]{32}$'
MAX_NANO = 2**63-1


class SecurityEvent(BaseModel):
    trace_id: str
    span_id: str
    action_id: str
    tool: str
    subject: str | None
    permission: str | None
    policy_revision: str | None
    rule_id: str | None
    effect: Literal['allow','deny','require_approval']
    reason: str
    outcome: Literal['denied','completed','error','cancelled','awaiting_approval']
    service_name: str
    agent_name: str | None
    status: Literal['UNSET','ERROR']
    start_time_unix_nano: int
    end_time_unix_nano: int


class SecurityEventList(BaseModel):
    items: list[SecurityEvent]
    total: int
    limit: int
    offset: int


def install_routes(app, store):
    from .models import ApiError
    @app.get('/api/v1/security-events',response_model=SecurityEventList,
             responses={code:{'model':ApiError} for code in (400,401,503,'4XX')})
    def security_events(
        limit: Annotated[int,Query(ge=1,le=100)]=20,
        offset: Annotated[int,Query(ge=0,le=10000)]=0,
        subject: Annotated[str|None,Query(pattern=IDENTIFIER)]=None,
        tool: Annotated[str|None,Query(pattern=IDENTIFIER)]=None,
        permission: Annotated[str|None,Query(pattern=IDENTIFIER)]=None,
        service_name: Annotated[str|None,Query(min_length=1,max_length=128)]=None,
        action_id: Annotated[str|None,Query(pattern=HEX32)]=None,
        trace_id: Annotated[str|None,Query(pattern=HEX32)]=None,
        effect: Literal['allow','deny','require_approval']|None=None,
        outcome: Literal['denied','completed','error','cancelled','awaiting_approval']|None=None,
        started_after_ns: Annotated[int|None,Query(ge=1,le=MAX_NANO)]=None,
        started_before_ns: Annotated[int|None,Query(ge=1,le=MAX_NANO)]=None,
    ):
        headers={'Cache-Control':'no-store','Vary':'Authorization'}
        if (service_name is not None and (not service_name.strip() or any(ord(c)<32 for c in service_name))) or any(value=='0'*32 for value in (action_id,trace_id)) or (started_after_ns is not None and started_before_ns is not None and started_after_ns>started_before_ns):
            return JSONResponse({'error':'invalid query or path parameter'},400,headers=headers)
        try:
            return JSONResponse(store.list_security_events(limit=limit,offset=offset,subject=subject,tool=tool,
                permission=permission,service_name=service_name,action_id=action_id,trace_id=trace_id,effect=effect,outcome=outcome,
                started_after_ns=started_after_ns,started_before_ns=started_before_ns),headers=headers)
        except StorageError:
            return JSONResponse({'error':'storage unavailable'},503,headers=headers)
