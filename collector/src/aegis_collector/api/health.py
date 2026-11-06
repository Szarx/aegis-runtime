"""Bounded, process-local health snapshots; not durable execution evidence."""
from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(ge=0, le=9007199254740991)]
Identifier = Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')]


class Diagnostics(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    accepted_spans: Count
    exported_spans: Count
    failed_spans: Count
    dropped_spans: Count
    pending_spans: Count
    export_failures: Count
    instrumentation_failures: Count


class HealthReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    instance_id: Identifier
    sequence: Annotated[int, Field(ge=1, le=9007199254740991)]
    service_name: Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[^\x00-\x1f\x7f]+$')]
    active_spans: Count
    active_traces: Annotated[list[Identifier], Field(max_length=16)]
    activity_truncated: bool
    diagnostics: Diagnostics
    health_failures: Count

    @model_validator(mode='after')
    def consistent(self):
        identifiers = [self.instance_id, *self.active_traces]
        d = self.diagnostics
        if (any(value == '0' * 32 for value in identifiers)
                or len(set(self.active_traces)) != len(self.active_traces)
                or len(self.active_traces) > self.active_spans
                or d.accepted_spans != d.exported_spans + d.failed_spans + d.pending_spans):
            raise ValueError('Inconsistent health snapshot')
        return self


class HealthRegistry:
    def __init__(self, *, capacity=1024, clock=monotonic):
        self._rows = OrderedDict()
        self._lock = Lock()
        self._clock = clock
        self._capacity = capacity
        self._evicted = 0

    def receive(self, report):
        with self._lock:
            prior = self._rows.get(report.instance_id)
            if prior:
                if prior[0].service_name != report.service_name:
                    raise ValueError('Instance service binding changed')
                if prior[0].sequence >= report.sequence:
                    return
            self._rows[report.instance_id] = (report, self._clock(), datetime.now(timezone.utc).isoformat())
            self._rows.move_to_end(report.instance_id)
            if len(self._rows) > self._capacity:
                self._rows.popitem(last=False)
                self._evicted += 1

    def listing(self):
        with self._lock:
            now = self._clock()
            items = []
            for report, received, timestamp in reversed(self._rows.values()):
                age = max(0, round((now - received) * 1000))
                items.append(dict(**report.model_dump(), age_ms=age, last_received_at=timestamp,
                                  state='stale' if age >= 45000 else 'reporting'))
            return dict(items=items, evicted_instances=self._evicted, stale_after_ms=45000,
                        scope='collector_process')


def install_routes(app):
    from .app import json_error
    registry = HealthRegistry()
    app.state.health_registry = registry

    @app.post('/v1/health', responses={400: {}, 401: {}, 413: {}})
    async def receive(request: Request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            return json_error(400, 'JSON health report required')
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 16384:
                return json_error(413, 'health report too large')
        try:
            report = HealthReport.model_validate_json(bytes(content))
            registry.receive(report)
        except ValueError:
            return json_error(400, 'invalid health report')
        return {'status': 'accepted'}

    @app.get('/api/v1/health')
    def listing():
        from fastapi.responses import JSONResponse
        return JSONResponse(registry.listing(), headers={'Cache-Control': 'no-store', 'Vary': 'Authorization'})
