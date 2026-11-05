"""SPEC-004: official OpenAI SDK + HTTPX2, synthetic HTTP/SSE only."""

import asyncio
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import aegis
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    import openai
    from aegis.openai import AegisAsyncOpenAI, AegisOpenAI, wrap_openai
    from examples.openai.offline import Fixture, PRIVATE_TEXT
    from aegis.integrations.openai.tracing import CallTrace
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'install SDK openai extra')
class OpenAIAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown()
        self.exporter = InMemorySpanExporter()
        self.sdk = aegis.init('openai-tests', exporter=self.exporter, schedule_delay_millis=10000)
        self.clients = []

    def tearDown(self):
        aegis.shutdown()
        for client in self.clients:
            client.close()

    def client(self, fixture=None, **kwargs):
        fixture = fixture or Fixture()
        client = AegisOpenAI(api_key='offline-synthetic-key', base_url='https://offline.invalid/v1', http_client=fixture.http_client(), max_retries=kwargs.pop('max_retries', 0), **kwargs)
        self.clients.append(client)
        return client, fixture

    def spans(self):
        self.assertTrue(aegis.flush())
        return self.exporter.get_finished_spans()

    @staticmethod
    def invoke(client, api, **kwargs):
        method = client.responses.create if api == 'responses' else client.chat.completions.create
        inputs = {'input': PRIVATE_TEXT} if api == 'responses' else {'messages': [{'role':'user', 'content':PRIVATE_TEXT}]}
        return method(model='offline-model', **inputs, **kwargs)

    def test_ac401_sync_apis_preserve_response_identity_and_parameters(self):
        client, fixture = self.client()
        for api in ('responses', 'chat.completions'):
            resource = client._client.responses if api == 'responses' else client._client.chat.completions
            original, captured = resource.create, []
            def call(**kwargs):
                value = original(**kwargs); captured.append(value); return value
            with patch.object(resource, 'create', call):
                value = self.invoke(client, api)
            self.assertIs(value, captured[0])
        self.assertEqual(len(fixture.requests), 2)
        for span in self.spans():
            self.assertEqual(span.attributes['gen_ai.usage.input_tokens'], 7)
            self.assertEqual(span.attributes['gen_ai.usage.output_tokens'], 3)
            self.assertEqual(span.attributes['aegis.call.outcome'], 'completed')
            self.assertEqual(span.kind.name, 'CLIENT')

    def test_ac401_options_mutable_config_idempotent_wrap_and_sdk_retry(self):
        client, fixture = self.client(Fixture(http_errors=1), max_retries=1)
        client.api_key = 'other-offline-key'
        self.assertEqual(client._client.api_key, 'other-offline-key')
        self.assertIs(wrap_openai(client), client)
        clone = client.with_options(timeout=2)
        self.invoke(clone, 'responses')
        self.assertEqual(len(fixture.requests), 2)
        self.assertEqual(len(self.spans()), 1)
        self.assertEqual(clone.timeout, 2)

    def test_ac402_sync_streams_no_prefetch_event_identity_eof_and_close(self):
        client, fixture = self.client()
        for api in ('responses', 'chat.completions'):
            options = {'stream': True}
            if api != 'responses': options['stream_options'] = {'include_usage': True}
            observed, original = [], CallTrace.capture
            def capture(call, event, **kwargs):
                observed.append(event); return original(call, event, **kwargs)
            with patch.object(CallTrace, 'capture', capture):
                stream = self.invoke(client, api, **options)
                self.assertEqual(fixture.streams[-1].reads, 0)
                events = list(stream)
                self.assertTrue(all(a is b for a, b in zip(events, observed)))
                stream.close(); stream.close()
            self.assertTrue(stream.response.is_closed)
        spans = self.spans()
        self.assertEqual(len(spans), 2)
        self.assertTrue(all(span.attributes['gen_ai.usage.input_tokens'] == 7 for span in spans))

    def test_ac402_early_close_incomplete_eof_and_context_body_error(self):
        for api in ('responses', 'chat.completions'):
            client, _ = self.client()
            with self.invoke(client, api, stream=True) as stream:
                next(stream)
            self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'], 'closed')
            self.assertNotIn('gen_ai.usage.input_tokens', self.spans()[-1].attributes)
            client, _ = self.client(Fixture(terminal=False))
            list(self.invoke(client, api, stream=True))
            self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'], 'incomplete')
        sentinel = ValueError(PRIVATE_TEXT)
        with self.assertRaises(ValueError) as raised:
            with self.invoke(client, 'responses', stream=True): raise sentinel
        self.assertIs(raised.exception, sentinel)
        self.assertEqual(self.spans()[-1].status.status_code.name, 'UNSET')

    def test_ac403_parent_context_restored_between_chunks_and_disabled_passthrough(self):
        client, _ = self.client()
        @aegis.tool
        def consume(): return trace.get_current_span().get_span_context().span_id
        @aegis.observe
        def agent():
            parent = trace.get_current_span().get_span_context().span_id
            with self.invoke(client, 'responses', stream=True) as stream:
                next(stream)
                self.assertEqual(trace.get_current_span().get_span_context().span_id, parent)
                consume()
        agent()
        spans = self.spans()
        agent_span = next(span for span in spans if span.attributes['gen_ai.operation.name'] == 'invoke_agent')
        self.assertTrue(all(span.parent.span_id == agent_span.context.span_id for span in spans if span is not agent_span))
        aegis.shutdown()
        raw = self.invoke(client, 'responses', stream=True)
        self.assertIsInstance(raw, openai.Stream)
        raw.close()

    def test_ac404_failed_incomplete_and_zero_unknown_usage(self):
        for state, expected in (('failed','error'), ('incomplete','incomplete')):
            client, _ = self.client(Fixture(state=state))
            response = self.invoke(client, 'responses')
            self.assertEqual(response.status, state)
            self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'], expected)
        client, _ = self.client(Fixture(usage=False))
        self.invoke(client, 'responses')
        self.assertNotIn('gen_ai.usage.input_tokens', self.spans()[-1].attributes)
        call = CallTrace.start('responses', {'model':'offline-model'})
        from types import SimpleNamespace
        call.capture(SimpleNamespace(model='offline-model', status='completed', usage=SimpleNamespace(input_tokens=0, output_tokens=True)))
        call.finish('completed')
        self.assertEqual(self.spans()[-1].attributes['gen_ai.usage.input_tokens'], 0)
        self.assertNotIn('gen_ai.usage.output_tokens', self.spans()[-1].attributes)

    def test_ac405_original_sdk_error_and_content_privacy(self):
        client, _ = self.client(Fixture(http_errors=1))
        with self.assertRaises(openai.APIStatusError) as raised:
            self.invoke(client, 'responses')
        self.assertIn(PRIVATE_TEXT, str(raised.exception))
        from aegis.exporters.jsonl import span_record
        record = span_record(self.spans()[-1])
        serialized = json.dumps(record)
        for secret in (PRIVATE_TEXT, 'offline-synthetic-key', 'offline.invalid', 'resp_offline_private'):
            self.assertNotIn(secret, serialized)
        self.assertEqual(record['schema_version'], 'aegis.span.v2')
        self.assertEqual(record['status'], 'ERROR')
        sentinel = openai.APIError(PRIVATE_TEXT, request=raised.exception.request, body=None)
        with patch.object(client._client.responses, 'create', side_effect=sentinel):
            with self.assertRaises(openai.APIError) as caught: self.invoke(client, 'responses')
            self.assertIs(caught.exception, sentinel)

    def test_ac405_instrumentation_failure_does_not_retry_or_fail_business(self):
        client, fixture = self.client()
        with patch.object(self.sdk.tracer, 'start_span', side_effect=RuntimeError('observer broken')):
            self.assertEqual(self.invoke(client, 'responses').status, 'completed')
        self.assertEqual(len(fixture.requests), 1)
        self.assertEqual(self.sdk.diagnostics()['instrumentation_failures'], 1)

    def test_ac402_async_apis_streams_context_and_usage(self):
        async def run():
            for api in ('responses', 'chat.completions'):
                fixture = Fixture(asynchronous=True)
                async with AegisAsyncOpenAI(api_key='offline-key', http_client=fixture.http_client(), max_retries=0) as client:
                    value = await self.invoke(client, api)
                    self.assertTrue(value.model)
                    options = {'stream':True}
                    if api != 'responses': options['stream_options'] = {'include_usage':True}
                    async with await self.invoke(client, api, **options) as stream:
                        self.assertEqual(fixture.streams[-1].reads, 0)
                        events = [event async for event in stream]
                        self.assertTrue(events)
                    await stream.aclose()
                    self.assertTrue(stream.response.is_closed)
            self.assertEqual(len(self.spans()), 4)
            self.assertTrue(all(span.attributes['aegis.call.outcome'] == 'completed' for span in self.spans()))
        asyncio.run(run())

    def test_ac402_async_cancellation_and_interleaved_stream_context(self):
        async def run():
            fixture = Fixture(asynchronous=True)
            async with AegisAsyncOpenAI(api_key='offline-key', http_client=fixture.http_client(), max_retries=0) as client:
                @aegis.observe
                async def agent():
                    parent = trace.get_current_span().get_span_context().span_id
                    async with await self.invoke(client, 'responses', stream=True) as stream:
                        await anext(stream)
                        self.assertEqual(trace.get_current_span().get_span_context().span_id, parent)
                        await asyncio.sleep(0)
                await asyncio.gather(agent(), agent())
                sentinel = asyncio.CancelledError()
                async def cancelled(**kwargs): raise sentinel
                with patch.object(client._client.responses, 'create', cancelled):
                    with self.assertRaises(asyncio.CancelledError) as caught: await self.invoke(client, 'responses')
                    self.assertIs(caught.exception, sentinel)
            spans = self.spans()
            self.assertEqual(len({span.context.trace_id for span in spans if span.attributes.get('aegis.call.mode') == 'stream'}), 2)
            self.assertEqual(spans[-1].attributes['aegis.call.outcome'], 'cancelled')
        asyncio.run(run())

    def test_ac402_stream_errors_and_failed_response_events(self):
        client, _ = self.client(Fixture(stream_error=True, terminal=False))
        with self.assertRaises(openai.APIError):
            list(self.invoke(client, 'responses', stream=True))
        self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'], 'error')
        client, _ = self.client(Fixture(state='failed'))
        events = list(self.invoke(client, 'responses', stream=True))
        self.assertEqual(events[-1].type, 'response.failed')
        self.assertEqual(self.spans()[-1].attributes['error.type'], 'openai.response.failed')

    def test_ac404_repeated_usage_overwrites_and_rejects_noninteger_counts(self):
        from types import SimpleNamespace
        call = CallTrace.start('responses', {'model':'offline-model'})
        for number in (7, 7):
            call.capture(SimpleNamespace(model='offline-model', status='completed', usage=SimpleNamespace(input_tokens=number, output_tokens=0)))
        call.finish('completed'); call.finish('closed')
        self.assertEqual(len(self.spans()), 1)
        self.assertEqual(self.spans()[0].attributes['gen_ai.usage.input_tokens'], 7)
        self.assertEqual(self.spans()[0].attributes['gen_ai.usage.output_tokens'], 0)
        for invalid in (-1, 1.2, '3', True, 2**63):
            call = CallTrace.start('responses', {'model':'offline-model'})
            call.capture(SimpleNamespace(model='offline-model', status='completed', usage=SimpleNamespace(input_tokens=invalid, output_tokens=None)))
            call.finish('completed')
            self.assertNotIn('gen_ai.usage.input_tokens', self.spans()[-1].attributes)

    def test_ac402_cancel_during_async_next_ends_once_and_closes_transport(self):
        from examples.openai.offline import AsyncBytes
        async def run():
            waiting, never = asyncio.Event(), asyncio.Event()
            async def blocked(stream):
                yield stream.parts[0]
                waiting.set()
                await never.wait()
            fixture = Fixture(asynchronous=True)
            with patch.object(AsyncBytes, '__aiter__', blocked):
                async with AegisAsyncOpenAI(api_key='offline-key', http_client=fixture.http_client(), max_retries=0) as client:
                    stream = await self.invoke(client, 'responses', stream=True)
                    await anext(stream)
                    task = asyncio.create_task(anext(stream))
                    await waiting.wait(); task.cancel()
                    with self.assertRaises(asyncio.CancelledError): await task
                    await stream.aclose()
                    self.assertTrue(stream.response.is_closed)
            self.assertEqual(len(self.spans()), 1)
            self.assertEqual(self.spans()[0].attributes['aegis.call.outcome'], 'cancelled')
        asyncio.run(run())
