import asyncio
import builtins
import unittest
from unittest.mock import patch

import httpx
import aegis
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from aegis_policy import Policy
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from tests.fixtures.async_reviewed import Transport, Stream, client, tool
from tests.fixtures.reviewed import payload


class AsyncReviewedExecution(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self): aegis.shutdown()

    async def prepare(self, governed, transport, arguments=None):
        ticket=await governed.prepare(arguments or {},summary='Synthetic async')
        transport.approve(ticket['action_id'])
        return ticket

    async def test_ac1201_async_only_explicit_disclosure_signature_and_laziness(self):
        transport=Transport()
        async with client(transport) as connection:
            def sync(): pass
            async def variadic(**kwargs): pass
            async def generator(): yield 1
            async def write(value=1): return value
            for function in (sync,variadic,generator):
                with self.assertRaises(TypeError): tool(function,connection)
            with self.assertRaises(ValueError):tool(write,connection,disclose_arguments=False)
            governed=tool(write,connection)
            before=governed.prepare({},summary='demo');resume=governed.resume('1'*32,{},summary='demo')
            self.assertEqual(transport.requests,[])
            before.close();resume.close()
            task=asyncio.create_task(governed.resume('1'*32,{},summary='demo'));task.cancel('before-start')
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(transport.requests,[])
            with self.assertRaises(TypeError):connection.prepare()
            with self.assertRaises(ValueError):await governed.prepare({'value':1.2},summary='demo')
        self.assertTrue(transport.closed)

    async def test_ac1202_fixed_faults_no_redirect_retry_credentials_or_large_response(self):
        for raw,status,headers in ((b'private invalid',200,{}),(b'x'*65537,200,{}),(b'{}',307,{'Location':'http://localhost/other'}),
                                   (b'{}',200,{'Content-Encoding':'gzip'}),(b'{"x":1,"x":2}',200,{}),(b'private server',503,{})):
            calls=[];streams=[]
            async def send(request):
                calls.append(request);stream=Stream(raw);streams.append(stream)
                return httpx.Response(status,headers=headers,stream=stream)
            async with client(httpx.MockTransport(send)) as connection:
                with self.assertRaisesRegex(ApprovalUnavailable,'^approval service unavailable$'):await connection.prepare_reviewed(payload())
                self.assertEqual(len(calls),1)
                self.assertEqual(calls[0].headers['authorization'],'Bearer synthetic-producer')
                self.assertNotIn('synthetic-producer',str(calls[0].url))
                self.assertTrue(all(stream.closed for stream in streams))

    async def test_ac1202_total_deadline_nonblocking_stream_and_close(self):
        entered=asyncio.Event();closed=[];ticks=[]
        class SlowStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                entered.set()
                while True:
                    await asyncio.sleep(.01);yield b' '
            async def aclose(self):closed.append(True)
        async def send(request):return httpx.Response(200,stream=SlowStream())
        async with client(httpx.MockTransport(send),timeout=.04) as connection:
            async def tick():
                await entered.wait()
                for _ in range(3):await asyncio.sleep(0);ticks.append(1)
            ticker=asyncio.create_task(tick())
            with self.assertRaises(ApprovalUnavailable):await asyncio.wait_for(connection.prepare_reviewed(payload()),.5)
            await ticker
            self.assertEqual(ticks,[1,1,1]);self.assertEqual(closed,[True])
        await connection.aclose()
        with self.assertRaises(ApprovalUnavailable):await connection.prepare_reviewed(payload())

    async def test_ac1202_missing_optional_dependency_loop_ownership_and_close_errors(self):
        original=builtins.__import__
        def absent(name,*args,**kwargs):
            if name=='httpx':raise ImportError('private missing path')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=absent),self.assertRaisesRegex(ImportError,r'^install aegis-runtime-control\[reviewed-async\]'):
            client()
        connection=client(Transport())
        async with connection:pass
        other=object()
        with patch('aegis_runtime.async_reviewed_execution.asyncio.get_running_loop',return_value=other),self.assertRaises(ValueError):await connection.aclose()
        original_error=ValueError('business original')
        class Broken(Transport):
            broken=True
            async def aclose(self):
                if self.broken:raise OSError('private cleanup')
                await super().aclose()
        connection=client(Broken())
        with self.assertRaises(ValueError) as context:
            async with connection:raise original_error
        self.assertIs(context.exception,original_error)
        connection._transport.broken=False
        await connection.aclose()
        self.assertTrue(connection._transport.closed)
        entered=asyncio.Event()
        class Interrupted(Transport):
            attempts=0
            async def aclose(self):
                self.attempts+=1
                if self.attempts==1:entered.set();await asyncio.Event().wait()
                await super().aclose()
        connection=client(Interrupted())
        task=asyncio.create_task(connection.aclose());await entered.wait();task.cancel('close cancelled')
        with self.assertRaises(asyncio.CancelledError):await task
        with self.assertRaises(ApprovalUnavailable):await connection.prepare_reviewed(payload())
        await connection.aclose();await connection.aclose()
        self.assertTrue(connection._transport.closed);self.assertEqual(connection._transport.attempts,2)

    async def test_ac1203_cancel_prepare_and_claim_inflight_preserves_signal_and_never_executes(self):
        for phase in ('prepare','claim'):
            transport=Transport();entered=asyncio.Event();seen=[];calls=[]
            async def hold(record):entered.set();await asyncio.Event().wait()
            async def write(value=1):calls.append(1)
            async with client(transport) as connection:
                governed=tool(write,connection)
                if phase=='claim':ticket=await self.prepare(governed,transport)
                transport.hooks[phase]=hold
                async def operation():
                    try:
                        return await (governed.prepare({},summary='Synthetic async') if phase=='prepare' else governed.resume(ticket['action_id'],{},summary='Synthetic async'))
                    except asyncio.CancelledError as error:seen.append(error);raise
                task=asyncio.create_task(operation());await entered.wait();task.cancel('private cancel reason')
                with self.assertRaises(asyncio.CancelledError) as context:await task
                self.assertIs(context.exception,seen[0]);self.assertEqual(calls,[])
                self.assertFalse(any(path.endswith('/complete') for path,_,_ in transport.requests))
                self.assertEqual(next(iter(transport.records.values()))['execution_state'],'available' if phase=='prepare' else 'claimed')

    async def test_ac1203_cancel_after_claim_before_function_never_completes_or_retries(self):
        transport=Transport();calls=[]
        async def write(value=1):calls.append(1)
        async with client(transport) as connection:
            governed=tool(write,connection);ticket=await self.prepare(governed,transport)
            claim=connection.claim
            async def cancel_after(payload):
                result=await claim(payload);asyncio.current_task().cancel('after claim');return result
            connection.claim=cancel_after
            task=asyncio.create_task(governed.resume(ticket['action_id'],{},summary='Synthetic async'))
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(calls,[]);self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'claimed')
            connection.claim=claim
            with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic async')
            self.assertEqual(calls,[])
            self.assertFalse(any(path.endswith('/complete') for path,_,_ in transport.requests))

    async def test_ac1203_cancel_in_function_is_unknown_with_original_identity_and_cancelled_span(self):
        transport=Transport();entered=asyncio.Event();seen=[];calls=[]
        exporter=InMemorySpanExporter();aegis.init('async-reviewed-test',exporter=exporter)
        async def write(value='private-argument'):
            calls.append(1);entered.set()
            try:await asyncio.Event().wait()
            except asyncio.CancelledError as error:seen.append(error);raise
        async with client(transport) as connection:
            governed=tool(write,connection);ticket=await self.prepare(governed,transport)
            task=asyncio.create_task(governed.resume(ticket['action_id'],{},summary='Synthetic async'))
            await entered.wait();task.cancel('private-cancel-message')
            with self.assertRaises(asyncio.CancelledError) as context:await task
            self.assertIs(context.exception,seen[0]);self.assertEqual(calls,[1])
            self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'claimed')
            self.assertFalse(any(path.endswith('/complete') for path,_,_ in transport.requests))
            with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic async')
        self.assertTrue(aegis.flush())
        spans=exporter.get_finished_spans();self.assertEqual(len(spans),1)
        self.assertEqual(spans[0].attributes['aegis.action.outcome'],'cancelled')
        self.assertNotIn('private-',repr(spans[0].attributes)+repr(spans[0].events))

    async def test_ac1203_cancel_during_success_or_failure_confirmation_never_repeats(self):
        for failure in (False,True):
            transport=Transport();entered=asyncio.Event();calls=[]
            async def hold(record):entered.set();await asyncio.Event().wait()
            transport.hooks['complete']=hold
            original=ValueError('private business error')
            async def write(value=1):
                calls.append(1)
                if failure:raise original
                return calls
            async with client(transport) as connection:
                governed=tool(write,connection);ticket=await self.prepare(governed,transport)
                task=asyncio.create_task(governed.resume(ticket['action_id'],{},summary='Synthetic async'))
                await entered.wait();task.cancel('confirmation cancelled')
                with self.assertRaises(asyncio.CancelledError):await task
                self.assertEqual(calls,[1]);self.assertEqual(transport.records[ticket['action_id']]['execution_state'],'failed' if failure else 'completed')
                with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic async')
                self.assertEqual(calls,[1])

    async def test_ac1203_success_failure_unknown_policy_and_deadline(self):
        transport=Transport();calls=[];value=object()
        async def write(item=1):calls.append(1);return value
        async with client(transport) as connection:
            governed=tool(write,connection);ticket=await self.prepare(governed,transport)
            outcome=await governed.resume(ticket['action_id'],{},summary='Synthetic async')
            self.assertIs(outcome.value,value);self.assertEqual(outcome.confirmation,'confirmed')
            transport.remaining_ms=0;ticket=await self.prepare(governed,transport)
            with self.assertRaises(ApprovalUnavailable):await governed.resume(ticket['action_id'],{},summary='Synthetic async')
            self.assertEqual(calls,[1])
            denied=tool(write,connection,policy=Policy('deny',()))
            before=len(transport.requests)
            with self.assertRaises(ActionDenied):await denied.prepare({},summary='Synthetic async')
            self.assertEqual(len(transport.requests),before)
        for failure in (False,True):
            transport=Transport();original=ValueError('original identity');calls=[]
            async def fail_confirmation(record):raise OSError('private transport')
            transport.hooks['complete']=fail_confirmation
            async def business(item=1):
                calls.append(1)
                if failure:raise original
                return value
            async with client(transport) as connection:
                governed=tool(business,connection);ticket=await self.prepare(governed,transport)
                if failure:
                    with self.assertRaises(ValueError) as context:await governed.resume(ticket['action_id'],{},summary='Synthetic async')
                    self.assertIs(context.exception,original)
                else:
                    result=await governed.resume(ticket['action_id'],{},summary='Synthetic async')
                    self.assertIs(result.value,value);self.assertEqual(result.confirmation,'unknown')
                self.assertEqual(calls,[1])

    async def test_ac1204_concurrent_agents_keep_parentage_identity_and_no_orphan_tasks(self):
        transport=Transport();started=[];barrier=asyncio.Event();exporter=InMemorySpanExporter()
        aegis.init('async-reviewed-concurrency',exporter=exporter)
        baseline=set(asyncio.all_tasks())
        async def write(value):
            started.append(value)
            if len(started)==2:barrier.set()
            await barrier.wait()
            return value
        async with client(transport) as connection:
            governed=tool(write,connection)
            async def run(label):
                @aegis.observe(name='agent-'+label)
                async def agent():
                    ticket=await self.prepare(governed,transport,{'value':'private-'+label})
                    return (await governed.resume(ticket['action_id'],{'value':'private-'+label},summary='Synthetic async')).value
                return await agent()
            self.assertEqual(await asyncio.gather(run('a'),run('b')),['private-a','private-b'])
        await asyncio.sleep(0)
        self.assertEqual(set(asyncio.all_tasks()),baseline)
        self.assertTrue(aegis.flush())
        spans=exporter.get_finished_spans();agents={s.context.trace_id:s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent'}
        tools=[s for s in spans if s.attributes['gen_ai.operation.name']=='execute_tool']
        self.assertEqual(len(agents),2);self.assertEqual(len(tools),2)
        for span in tools:self.assertEqual(span.parent.span_id,agents[span.context.trace_id].context.span_id)
        self.assertFalse(trace.get_current_span().get_span_context().is_valid)
        self.assertNotIn('private-',repr([dict(s.attributes) for s in spans]))
