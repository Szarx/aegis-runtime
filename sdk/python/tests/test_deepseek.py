"""SPEC-005 uses the official SDK with synthetic DeepSeek-shaped transport."""

import asyncio
import os
import unittest
from unittest.mock import patch

import aegis
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans

try:
    import openai
    from aegis.deepseek import AegisDeepSeek, AegisAsyncDeepSeek
    from aegis.openai import wrap_openai
    from examples.deepseek.offline import Fixture, PRIVATE_TEXT
    from examples.deepseek.agent import run_agent, run_async_agent, run_tool_agent
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'install SDK deepseek extra')
class DeepSeekAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown()
        self.exporter = InMemorySpanExporter()
        self.sdk = aegis.init('deepseek-tests',exporter=self.exporter)
    def tearDown(self):
        aegis.shutdown()
    def spans(self):
        self.assertTrue(aegis.flush())
        return self.exporter.get_finished_spans()

    def test_ac501_independent_key_configuration_provider_and_copy(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'not-deepseek'}, clear=True):
            with self.assertRaisesRegex(ValueError,'DEEPSEEK_API_KEY'): AegisDeepSeek()
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'synthetic-deepseek-key'}):
            fixture = Fixture()
            with AegisDeepSeek(http_client=fixture.http_client(),max_retries=0) as client:
                self.assertEqual(client.api_key,'synthetic-deepseek-key')
                self.assertEqual(str(client.base_url),'https://api.deepseek.com')
                self.assertIs(wrap_openai(client),client)
                self.assertIs(wrap_openai(client,provider='deepseek'),client)
                with self.assertRaises(ValueError): wrap_openai(client,provider='openai')
                for method in (client.copy, client.with_options):
                    clone = method(timeout=2)
                    run_agent(clone,model='offline-deepseek')
                    self.assertEqual(clone.timeout,2)
                client.responses.create(model='offline-model',input=PRIVATE_TEXT)
        models = [s for s in self.spans() if s.kind.name=='CLIENT']
        self.assertEqual(len(models),2)  # Responses delegated, outside DeepSeek matrix.
        self.assertTrue(all(s.attributes['gen_ai.provider.name']=='deepseek' for s in models))
        raw = openai.OpenAI(api_key='synthetic',http_client=Fixture().http_client())
        with raw:
            with self.assertRaises(ValueError): wrap_openai(raw,provider='unknown')

    def test_ac502_sync_json_sse_terminal_usage_and_privacy(self):
        fixture = Fixture()
        with AegisDeepSeek(api_key='synthetic-deepseek-key',http_client=fixture.http_client()) as client:
            for streaming in (False, True):
                self.assertEqual(run_agent(client,model='offline-deepseek',stream=streaming)['status'],'shipped')
        models = [s for s in self.spans() if s.kind.name=='CLIENT']
        self.assertEqual(len(models),2)
        for model in models:
            self.assertEqual(model.attributes['gen_ai.usage.input_tokens'],7)
            self.assertEqual(model.attributes['gen_ai.usage.output_tokens'],3)
            self.assertEqual(model.attributes['aegis.call.outcome'],'completed')
        self.assertEqual(len(fixture.requests),2)
        self.assertEqual(fixture.requests[1]['extra_body'] if 'extra_body' in fixture.requests[1] else fixture.requests[1]['thinking'], {'type':'disabled'})
        payload = encode_spans(self.spans()).SerializeToString()
        for secret in (PRIVATE_TEXT, 'synthetic-deepseek-key','deepseek-private-response','private-tool-id','api.deepseek.com'):
            self.assertNotIn(secret.encode(),payload)

    def test_ac502_async_json_sse_and_agent_context(self):
        async def execute():
            async with AegisAsyncDeepSeek(api_key='synthetic',http_client=Fixture(asynchronous=True).http_client()) as client:
                await asyncio.gather(*(run_async_agent(client,model='offline-deepseek',stream=value) for value in (False,True)))
        asyncio.run(execute())
        spans = self.spans()
        agents = {s.context.span_id for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent'}
        self.assertEqual(len(agents),2)
        children = [s for s in spans if s.attributes['gen_ai.operation.name']!='invoke_agent']
        self.assertEqual(len(children),4)
        self.assertTrue(all(s.parent.span_id in agents for s in children))

    def test_ac502_stream_error_identity_unknown_usage_and_early_close(self):
        with AegisDeepSeek(api_key='synthetic',http_client=Fixture(usage=False).http_client()) as client:
            with client.chat.completions.create(model='offline-deepseek',messages=[],stream=True) as events:
                next(events)
            self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'],'closed')
            self.assertNotIn('gen_ai.usage.input_tokens',self.spans()[-1].attributes)
        with AegisDeepSeek(api_key='synthetic',max_retries=0,http_client=Fixture(http_errors=1).http_client()) as client:
            captured = []
            original = client._client.chat.completions.create
            def invoke(**kwargs):
                try: return original(**kwargs)
                except Exception as error:
                    captured.append(error)
                    raise
            with patch.object(client._client.chat.completions,'create',invoke):
                with self.assertRaises(openai.AuthenticationError) as raised:
                    client.chat.completions.create(model='offline-deepseek',messages=[])
            self.assertIs(raised.exception,captured[0])
        self.assertEqual(self.spans()[-1].attributes['aegis.call.outcome'],'error')

    def test_ac502_async_stream_cancellation_ends_once(self):
        async def execute():
            async with AegisAsyncDeepSeek(api_key='synthetic',http_client=Fixture(asynchronous=True).http_client()) as client:
                events = await client.chat.completions.create(model='offline-deepseek',messages=[],stream=True)
                error = asyncio.CancelledError()
                with self.assertRaises(asyncio.CancelledError) as raised:
                    async with events:
                        await events.__anext__()
                        raise error
                self.assertIs(raised.exception,error)
                await events.aclose()
        asyncio.run(execute())
        models = [s for s in self.spans() if s.kind.name=='CLIENT']
        self.assertEqual(len(models),1)
        self.assertEqual(models[0].attributes['aegis.call.outcome'],'cancelled')

    def test_ac505_synthetic_tool_loop_runs_tool_once_and_preserves_parent(self):
        fixture = Fixture()
        with AegisDeepSeek(api_key='synthetic',http_client=fixture.http_client()) as client:
            result = run_tool_agent(client,model='offline-deepseek')
        self.assertEqual(result,{'status':'shipped','tool_calls':1,'model_calls':2})
        spans = self.spans()
        root = next(s for s in spans if s.attributes['gen_ai.operation.name']=='invoke_agent')
        self.assertEqual(len(spans),4)
        self.assertTrue(all(s.parent.span_id == root.context.span_id for s in spans if s is not root))
        self.assertEqual(len(fixture.requests),2)
        self.assertEqual(fixture.requests[1]['tool_choice'],'none')
