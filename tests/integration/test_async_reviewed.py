import asyncio
import os
import unittest
import uuid

import aegis
import httpx
import psycopg
from psycopg import sql
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans

from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from aegis_runtime.reviewed_execution import ExecutionResult
from tests.fixtures.async_reviewed import tool
from tests.fixtures.live_server import LiveServer

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class AsyncReviewedPostgres(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.schema='test_async_reviewed_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        app=create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',
                       approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor')
        self.host=LiveServer(app).start()

    def tearDown(self):
        aegis.shutdown();self.host.close()
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def client(self, transport=None):
        return AsyncReviewedClient(self.host.endpoint,token='synthetic-producer',execution_token='synthetic-executor',
                                   binding_key=b'synthetic-async-integration-key!!',transport=transport)

    async def approve(self, ticket):
        async with httpx.AsyncClient(trust_env=False,timeout=3) as reviewer:
            response=await reviewer.post(self.host.endpoint+'/api/v1/reviewed-actions/'+ticket['action_id']+'/decision',
                                         headers={'Authorization':'Bearer synthetic-reviewer'},json={'decision':'approved','review_digest':ticket['review_digest']})
            self.assertEqual(response.status_code,200)

    async def prepare(self, governed):
        ticket=await governed.prepare({},summary='Synthetic async HTTP')
        await self.approve(ticket)
        return ticket

    async def test_ac1205_actual_async_success_error_cancel_and_concurrent_claim_with_otlp(self):
        calls=[];value=object();exporter=InMemorySpanExporter();aegis.init('async-reviewed-http',exporter=exporter)
        async def write(value='private-argument'):
            calls.append('success');await asyncio.sleep(0);return returned
        returned=value
        async with self.client() as connection:
            governed=tool(write,connection);ticket=await self.prepare(governed)
            results=await asyncio.gather(*(governed.resume(ticket['action_id'],{},summary='Synthetic async HTTP') for _ in range(2)),return_exceptions=True)
            self.assertEqual(sum(type(result) is ExecutionResult for result in results),1)
            self.assertEqual(sum(isinstance(result,ApprovalUnavailable) for result in results),1)
            result=next(result for result in results if type(result) is ExecutionResult)
            self.assertIs(result.value,value);self.assertEqual(result.confirmation,'confirmed')
            original=ValueError('private-business-message')
            async def fail(value='private-argument'):calls.append('failure');raise original
            governed=tool(fail,connection,tool_revision='async-failure-v1');failed=await self.prepare(governed)
            with self.assertRaises(ValueError) as context:await governed.resume(failed['action_id'],{},summary='Synthetic async HTTP')
            self.assertIs(context.exception,original)
            entered=asyncio.Event();seen=[]
            async def cancel(value='private-argument'):
                calls.append('cancelled');entered.set()
                try:await asyncio.Event().wait()
                except asyncio.CancelledError as error:seen.append(error);raise
            governed=tool(cancel,connection,tool_revision='async-cancel-v1');cancelled=await self.prepare(governed)
            task=asyncio.create_task(governed.resume(cancelled['action_id'],{},summary='Synthetic async HTTP'))
            await asyncio.wait_for(entered.wait(),3);task.cancel('private-cancel-message')
            with self.assertRaises(asyncio.CancelledError) as context:await task
            self.assertIs(context.exception,seen[0])
            with self.assertRaises(ApprovalUnavailable):await governed.resume(cancelled['action_id'],{},summary='Synthetic async HTTP')
        self.assertEqual(calls,['success','failure','cancelled'])
        rows=self.store.list_reviewed()['items']
        self.assertEqual({row['execution_state'] for row in rows},{'completed','failed','claimed'})
        self.assertTrue(aegis.flush());spans=exporter.get_finished_spans()
        self.assertEqual({s.attributes['aegis.action.outcome'] for s in spans},{'completed','error','cancelled'})
        async with httpx.AsyncClient(trust_env=False,timeout=3) as http:
            response=await http.post(self.host.endpoint+'/v1/traces',headers={'Authorization':'Bearer synthetic-trace','Content-Type':'application/x-protobuf'},content=encode_spans(spans).SerializeToString())
            self.assertEqual(response.status_code,200)
            listing=(await http.get(self.host.endpoint+'/api/v1/traces',headers={'Authorization':'Bearer synthetic-trace'})).json()
            self.assertEqual(listing['total'],3)
            for trace in listing['items']:
                detail=(await http.get(self.host.endpoint+'/api/v1/traces/'+trace['trace_id'],headers={'Authorization':'Bearer synthetic-trace'})).json()
                self.assertNotIn('private-',str(detail))

    async def test_ac1205_committed_claim_and_complete_cancelled_response_never_repeat(self):
        entered=asyncio.Event();calls=[]
        class HoldResponse(httpx.AsyncBaseTransport):
            phase='claim'
            def __init__(self):self.native=httpx.AsyncHTTPTransport(retries=0,trust_env=False)
            async def handle_async_request(self, request):
                response=await self.native.handle_async_request(request)
                if request.url.path.endswith('/'+self.phase) and response.status_code==200:
                    await response.aread()  # The real server has committed and responded.
                    entered.set()
                    try:await asyncio.Event().wait()
                    except BaseException:await response.aclose();raise
                return response
            async def aclose(self):await self.native.aclose()
        transport=HoldResponse()
        async def write(value=1):calls.append(1);return value
        async with self.client(transport) as connection:
            governed=tool(write,connection)
            claimed=await self.prepare(governed)
            task=asyncio.create_task(governed.resume(claimed['action_id'],{},summary='Synthetic async HTTP'))
            await asyncio.wait_for(entered.wait(),3);task.cancel('lost claim response')
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(calls,[])
            entered.clear();transport.phase='complete'
            completed=await self.prepare(governed)
            task=asyncio.create_task(governed.resume(completed['action_id'],{},summary='Synthetic async HTTP'))
            await asyncio.wait_for(entered.wait(),3);task.cancel('lost completion response')
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(calls,[1])
            for ticket in (claimed,completed):
                with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic async HTTP')
            self.assertEqual(calls,[1])
        rebuilt=PostgresSpanStore(DATABASE,self.schema);rebuilt.migrate()
        self.assertEqual({row['execution_state'] for row in rebuilt.list_reviewed()['items']},{'claimed','completed'})
