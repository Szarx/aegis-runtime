"""Synthetic committed-response fixture for async cancellation boundaries."""

import copy
from datetime import datetime, timedelta, timezone
import json

import httpx

from aegis_runtime.async_reviewed_execution import AsyncReviewedClient, AsyncReviewedTool
from aegis_runtime.reviewed_execution import BINDING
from tests.fixtures.reviewed import policy


class Stream(httpx.AsyncByteStream):
    def __init__(self, raw): self.raw=raw; self.closed=False
    async def __aiter__(self): yield self.raw
    async def aclose(self): self.closed=True


class Transport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.records={}; self.requests=[]; self.streams=[]; self.hooks={}; self.closed=False; self.remaining_ms=200000

    async def handle_async_request(self, request):
        data=json.loads(await request.aread())
        self.requests.append((request.url.path,copy.deepcopy(data),dict(request.headers)))
        path=request.url.path
        phase='claim' if path.endswith('/claim') else 'complete' if path.endswith('/complete') else 'prepare'
        code=200
        if phase=='prepare':
            now=datetime.now(timezone.utc)
            record={**data,'status':'pending','created_at':now.isoformat(),'expires_at':(now+timedelta(seconds=data['ttl_seconds'])).isoformat(),
                    'decided_at':None,'reviewer':None,'execution_state':'available','claim_id':None,'executor':None,'claimed_at':None,'finished_at':None}
            self.records[data['action_id']]=record
            result=copy.deepcopy(record)
        else:
            action_id=path.split('/')[-2]
            record=self.records[action_id]
            if phase=='claim':
                if record['status']!='approved' or record['execution_state']!='available' or any(record[key]!=data[key] for key in BINDING):
                    code=409;result={'error':'conflict'}
                else:
                    record.update(execution_state='claimed',claim_id=data['claim_id'],executor='local-executor',claimed_at=datetime.now(timezone.utc).isoformat())
                    result={**copy.deepcopy(record),'remaining_ms':self.remaining_ms}
            else:
                if record['claim_id']!=data['claim_id'] or record['execution_state']!='claimed':
                    code=409;result={'error':'conflict'}
                else:
                    record.update(execution_state=data['outcome'],finished_at=datetime.now(timezone.utc).isoformat())
                    result=copy.deepcopy(record)
        if phase in self.hooks:
            await self.hooks[phase](record)
        stream=Stream(json.dumps(result).encode());self.streams.append(stream)
        return httpx.Response(code,stream=stream)

    def approve(self, action_id):
        self.records[action_id].update(status='approved',reviewer='local-reviewer',decided_at=datetime.now(timezone.utc).isoformat())

    async def aclose(self): self.closed=True


def client(transport=None, **changes):
    return AsyncReviewedClient('http://127.0.0.1:8000', **{**dict(token='synthetic-producer',execution_token='synthetic-executor',
                                                            binding_key=b'synthetic-async-binding-key-0012!',transport=transport),**changes})


def tool(function, connection, **changes):
    return AsyncReviewedTool(function, **{**dict(client=connection,policy=policy(),subject='demo-agent',permission='records.write',tool='write',
                                               tool_revision='async-impl-v1',disclose_arguments=True),**changes})
