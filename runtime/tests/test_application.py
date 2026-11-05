import asyncio
from dataclasses import FrozenInstanceError,replace
import inspect
import json
import os
from pathlib import Path
import tempfile
from threading import Event,Thread
import unittest
from unittest.mock import patch
import aegis
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application,ApplicationConfig,Telemetry,ToolBinding,inspect_application,load_application
from tests.fixtures.application_config import write_application


class ApplicationAcceptance(unittest.TestCase):
    def setUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.addCleanup(aegis.shutdown)
        self.folder=Path(self.tmp.name);self.path=write_application(self.folder);self.config=load_application(self.path)

    def test_ac2501_relative_paths_and_immutable_policy_snapshot(self):
        self.assertEqual(self.config.telemetry.output_path,self.folder/'traces.jsonl')
        (self.folder/'policy.json').write_text('invalid-new-policy')
        self.assertEqual(self.config.policy.revision,'onboarding-demo-v1')
        with self.assertRaises(FrozenInstanceError):self.config.service_name='changed'
        self.assertFalse((self.folder/'traces.jsonl').exists())

    def test_ac2501_strict_schema_unknown_keys_duplicate_json_and_size(self):
        original=json.loads(self.path.read_text())
        for change in (dict(schema_version='future'),dict(subject='reader'),dict(tools=[]),dict(service_name='bad *'),dict(policy_file='missing.json')):
            self.path.write_text(json.dumps({**original,**change}))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^invalid or unreadable application configuration$'):load_application(self.path)
        for raw in (b'\xff',b'{"schema_version":1,"schema_version":2}',b'x'*65537):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):load_application(self.path)

    def test_ac2501_binding_names_permissions_and_direct_constructor_validation(self):
        with self.assertRaises(ValueError):ToolBinding('lookup_order','*')
        with self.assertRaises(ValueError):replace(self.config,tools=list(self.config.tools))
        with self.assertRaises(ValueError):replace(self.config,tools=(self.config.tools[0],self.config.tools[0]))
        with self.assertRaises(ValueError):replace(self.config,policy=None)
        doc=json.loads(self.path.read_text());doc['tools'][0]['headers']={'private':'secret'};self.path.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):load_application(self.path)

    def test_ac2501_otlp_endpoint_and_environment_references_are_strict(self):
        for url in ('http://example.com/v1/traces','https://user:secret@example.com/v1/traces','https://example.com/other','https://example.com/v1/traces?secret=x','http://127.0.0.1:0/v1/traces'):
            with self.subTest(url=url),self.assertRaises(ValueError):Telemetry('otlp',endpoint=url)
        with self.assertRaises(ValueError):Telemetry('otlp',endpoint='https://example.com/v1/traces',token_env='inline-token-value')
        with self.assertRaises(ValueError):Telemetry('otlp',endpoint='https://example.com/v1/traces',timeout_millis=True)
        self.assertEqual(Telemetry('otlp',endpoint='http://127.0.0.1:8000/v1/traces').mode,'otlp')

    def test_ac2501_inspect_is_read_only_and_does_not_disclose_token_or_paths(self):
        config=load_application(write_application(self.folder,endpoint='http://127.0.0.1:8000/v1/traces'))
        with patch('aegis.init',side_effect=AssertionError('must not initialize')):
            report=inspect_application(config,subject='reader',environment={'SYNTHETIC_TRACE_TOKEN':'synthetic-private-token'})
        self.assertEqual(report['status'],'valid');self.assertEqual(report['tools'][0]['decision']['effect'],'allow')
        raw=json.dumps(report);self.assertNotIn('synthetic-private',raw);self.assertNotIn('127.0.0.1',raw);self.assertNotIn(str(self.folder),raw)
        self.assertFalse((self.folder/'traces.jsonl').exists())

    def test_ac2501_inspect_missing_dependency_or_invalid_token_blocks_without_network(self):
        config=load_application(write_application(self.folder,endpoint='http://127.0.0.1:8000/v1/traces'))
        self.assertEqual(inspect_application(config,subject='reader',environment={})['checks']['token'],'invalid')
        from importlib.metadata import PackageNotFoundError
        with patch('aegis_runtime.application.metadata.version',side_effect=PackageNotFoundError('synthetic')):
            report=inspect_application(config,subject='reader',environment={'SYNTHETIC_TRACE_TOKEN':'synthetic'})
        self.assertEqual(report['status'],'blocked');self.assertEqual(report['checks']['otlp_package'],'missing')

    def test_ac2502_tool_signature_return_object_and_explicit_deny_zero_calls(self):
        calls=[];sentinel=object()
        def lookup_order(order_id:str,*,flag:bool=False)->object:calls.append(order_id);return sentinel
        with Application(self.config,subject='reader') as app:
            wrapped=app.tool(lookup_order);self.assertEqual(inspect.signature(wrapped),inspect.signature(lookup_order))
            self.assertIs(wrapped('demo'),sentinel)
        with Application(self.config,subject='blocked') as app:
            wrapped=app.tool(lookup_order)
            with self.assertRaises(ActionDenied) as caught:wrapped('not-executed')
            self.assertEqual(caught.exception.decision.reason,'explicit_deny')
        self.assertEqual(calls,['demo'])

    def test_ac2502_unknown_duplicate_and_generator_bindings_are_rejected(self):
        def lookup_order():return 'synthetic'
        def generator():yield 1
        with Application(self.config,subject='reader') as app:
            with self.assertRaises(ValueError):app.tool(lookup_order,name='unconfigured')
            with self.assertRaises(TypeError):app.tool(generator,name='lookup_order')
            app.tool(lookup_order)
            with self.assertRaises(ValueError):app.tool(lookup_order)
            with self.assertRaises(TypeError):app.agent(generator)
            self.assertEqual(app.status()['bound_tools'],['lookup_order']);self.assertEqual(app.status()['unbound_tools'],['write_record'])

    def test_ac2502_agent_tool_parent_relationship_and_content_privacy(self):
        with Application(self.config,subject='reader') as app:
            @app.tool
            def lookup_order(value):return value
            @app.agent(name='configured-test')
            def agent():return lookup_order('synthetic-private-body')
            self.assertEqual(agent(),'synthetic-private-body')
        raw=(self.folder/'traces.jsonl').read_text();self.assertNotIn('synthetic-private-body',raw)
        spans=[json.loads(line) for line in raw.splitlines()]
        tool=next(s for s in spans if s['attributes']['gen_ai.operation.name']=='execute_tool')
        parent=next(s for s in spans if s['attributes']['gen_ai.operation.name']=='invoke_agent')
        self.assertEqual(tool['parent_span_id'],parent['span_id']);self.assertEqual(tool['trace_id'],parent['trace_id'])
        self.assertEqual(tool['attributes']['aegis.tool.permission'],'orders.read')

    def test_ac2502_business_exception_identity_is_preserved_and_session_closes(self):
        original=ValueError('synthetic private business exception');app=Application(self.config,subject='reader')
        with self.assertRaises(ValueError) as caught:
            with app:
                @app.tool(name='lookup_order')
                def fail():raise original
                fail()
        self.assertIs(caught.exception,original);self.assertEqual(app.status()['state'],'closed');self.assertTrue(app.status()['shutdown'])

    def test_ac2502_async_await_stays_in_caller_task_and_cancellation_releases_lease(self):
        cancellation=asyncio.CancelledError('synthetic');seen=[]
        with Application(self.config,subject='reader') as app:
            @app.tool(name='lookup_order')
            async def controlled():seen.append(asyncio.current_task());raise cancellation
            self.assertTrue(inspect.iscoroutinefunction(controlled))
            async def run():
                current=asyncio.current_task()
                with self.assertRaises(asyncio.CancelledError) as caught:await controlled()
                self.assertIs(caught.exception,cancellation);self.assertIs(seen[0],current)
            asyncio.run(run());self.assertEqual(app.status()['active_calls'],0)

    def test_ac2502_before_start_after_close_and_reentry_never_execute(self):
        app=Application(self.config,subject='reader');calls=[]
        def lookup_order():calls.append(1)
        with self.assertRaises(RuntimeError):app.tool(lookup_order)
        with app:tool=app.tool(lookup_order);agent=app.agent(lambda:tool(),name='entry')
        for function in (tool,agent):
            with self.assertRaises(RuntimeError):function()
        with self.assertRaises(RuntimeError):app.__enter__()
        self.assertEqual(calls,[]);self.assertTrue(app.close())

    def test_ac2501_active_external_sdk_is_not_taken_over_or_closed(self):
        external=aegis.init('external',output_path=self.folder/'external.jsonl');app=Application(self.config,subject='reader')
        with self.assertRaisesRegex(RuntimeError,'^Application startup failed$'):app.__enter__()
        self.assertEqual(app.status()['state'],'failed');app.close();self.assertTrue(external.enabled)
        external.shutdown()

    def test_ac2502_old_application_close_does_not_close_later_external_sdk(self):
        with Application(self.config,subject='reader') as app:pass
        external=aegis.init('later',output_path=self.folder/'later.jsonl');self.assertTrue(app.close());self.assertTrue(external.enabled)
        external.shutdown()

    def test_ac2502_inflight_sync_work_refuses_close_until_joined(self):
        entered=Event();release=Event();results=[];app=Application(self.config,subject='reader');app.__enter__()
        @app.tool(name='lookup_order')
        def controlled():entered.set();release.wait(5);return 'synthetic'
        worker=Thread(target=lambda:results.append(controlled()));worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaises(RuntimeError):app.close()
            self.assertEqual(app.status()['state'],'active')
        finally:release.set();worker.join(5);app.close()
        self.assertFalse(worker.is_alive());self.assertEqual(results,['synthetic'])

    def test_ac2502_inflight_async_work_refuses_close_until_awaited(self):
        with Application(self.config,subject='reader') as app:
            async def run():
                entered=asyncio.Event();release=asyncio.Event()
                @app.tool(name='lookup_order')
                async def controlled():entered.set();await release.wait();return 'synthetic'
                task=asyncio.create_task(controlled());await entered.wait()
                with self.assertRaises(RuntimeError):app.close()
                release.set();self.assertEqual(await task,'synthetic')
            asyncio.run(run());self.assertEqual(app.status()['active_calls'],0)

    def test_ac2502_flush_failure_does_not_retry_business_and_is_visible(self):
        calls=[];app=Application(self.config,subject='reader');app.__enter__()
        @app.tool(name='lookup_order')
        def controlled():calls.append(1);return 'synthetic'
        self.assertEqual(controlled(),'synthetic')
        with patch.object(app._sdk,'flush',return_value=False):self.assertFalse(app.close())
        self.assertFalse(app.status()['flush']);self.assertTrue(app.status()['shutdown']);self.assertEqual(calls,[1])
        later=aegis.init('later',output_path=self.folder/'later.jsonl')
        self.assertTrue(app.close());self.assertTrue(later.enabled);later.shutdown();self.assertEqual(calls,[1])

    def test_ac2502_shutdown_fault_does_not_mask_business_error_and_close_can_drain_again(self):
        app=Application(self.config,subject='reader');app.__enter__();original=ValueError('business')
        with patch.object(app._sdk,'shutdown',side_effect=RuntimeError('private shutdown failure')):
            with self.assertRaises(ValueError) as caught:
                try:raise original
                finally:app.__exit__(ValueError,original,None)
        self.assertIs(caught.exception,original);self.assertFalse(app.status()['shutdown']);self.assertTrue(app.close())

    def test_ac2501_missing_or_control_token_fails_before_tracing_start(self):
        config=load_application(write_application(self.folder,endpoint='http://127.0.0.1:8000/v1/traces'))
        for value in ('','private\nsecret','space token'):
            with patch.dict(os.environ,{'SYNTHETIC_TRACE_TOKEN':value}):
                app=Application(config,subject='reader')
                with self.assertRaisesRegex(RuntimeError,'^Application startup failed$'):app.__enter__()
                self.assertEqual(app.status()['state'],'failed');self.assertIsNone(app.status()['diagnostics'])
