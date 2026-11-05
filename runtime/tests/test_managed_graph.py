import asyncio
import json
from pathlib import Path
import tempfile
from threading import Event,Thread
from typing import TypedDict
import unittest
from unittest.mock import patch
import aegis
from aegis_runtime.application import Application,load_application
from langgraph.graph import StateGraph,START,END
from opentelemetry import trace
from tests.fixtures.application_config import write_application


class State(TypedDict):value:int


def graph_for(node):return StateGraph(State).add_node('step',node).add_edge(START,'step').add_edge('step',END).compile()


class ManagedGraph(unittest.TestCase):
    def setUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.addCleanup(aegis.shutdown)
        self.folder=Path(self.tmp.name);self.settings=load_application(write_application(self.folder))
    def records(self):return [json.loads(line) for line in (self.folder/'traces.jsonl').read_text().splitlines()]

    def test_ac2801_invoke_configuration_identity_limited_methods_and_closed_rejection(self):
        result={'value':2};seen=[]
        def node(state,config):seen.append(config['tags']);return result
        raw=graph_for(node)
        with Application(self.settings,subject='reader') as app:
            graph=app.graph(raw,name='managed');configured=graph.with_config(tags=['kept'])
            self.assertEqual(configured.invoke({'value':1}),result);self.assertEqual(seen,[['kept']])
            for name in ('get_state','update_state','batch','astream_events'):
                with self.assertRaises(AttributeError):getattr(graph,name)
            with self.assertRaises(TypeError):app.graph(object())
            with self.assertRaises(TypeError):app.graph(graph)
        for operation in (lambda:graph.invoke({'value':1}),lambda:graph.stream({'value':1}),lambda:graph.astream({'value':1}),lambda:graph.with_config(tags=[]),lambda:app.graph(raw)):
            with self.assertRaises(RuntimeError):operation()
        self.assertEqual(app.status()['active_calls'],0)

    def test_ac2802_unused_stream_is_lazy_and_cannot_start_after_application_close(self):
        calls=[]
        with Application(self.settings,subject='reader') as app:
            graph=app.graph(graph_for(lambda state:calls.append(1) or {'value':2}))
            unused=graph.stream({'value':1});closed=graph.stream({'value':1});closed.close();closed.close()
            self.assertEqual(app.status()['active_calls'],0);self.assertEqual(calls,[])
        with self.assertRaises(RuntimeError):next(unused)
        unused.close();self.assertEqual(calls,[]);self.assertEqual(app.status()['diagnostics']['exported_spans'],0)

    def test_ac2802_eof_holds_lease_until_exhaustion_and_preserves_payload_identity(self):
        raw=graph_for(lambda state:{'value':2});captured=[];original=raw.stream
        def source(*args,**kwargs):
            for item in original(*args,**kwargs):captured.append(item);yield item
        with Application(self.settings,subject='reader') as app,patch.object(raw,'stream',source):
            stream=app.graph(raw).stream({'value':1},stream_mode='values',version='v2')
            first=next(stream);self.assertIs(first,captured[0]);self.assertEqual(app.status()['active_calls'],1)
            with self.assertRaises(RuntimeError):app.close()
            rest=list(stream);self.assertTrue(all(a is b for a,b in zip(rest,captured[1:])))
            self.assertEqual(app.status()['active_calls'],0);stream.close()
        record=self.records()[0];self.assertEqual(record['attributes']['aegis.graph.outcome'],'completed')

    def test_ac2802_early_close_restores_parent_context_between_yields(self):
        with Application(self.settings,subject='reader') as app:
            consumer=app.tool(lambda:None,name='lookup_order');graph=app.graph(graph_for(lambda state:{'value':2}),name='inner')
            @app.agent(name='outer')
            def run():
                parent=trace.get_current_span().get_span_context().span_id
                with graph.stream({'value':1},stream_mode='values') as stream:
                    next(stream);self.assertEqual(trace.get_current_span().get_span_context().span_id,parent);consumer()
            run();self.assertEqual(app.status()['active_calls'],0)
        records=self.records();outer=next(r for r in records if r['name']=='invoke_agent outer')
        inner=next(r for r in records if r['name']=='invoke_agent inner');tool=next(r for r in records if r['name']=='execute_tool lookup_order')
        self.assertEqual(inner['attributes']['aegis.graph.outcome'],'closed')
        self.assertEqual((inner['parent_span_id'],tool['parent_span_id']),(outer['span_id'],outer['span_id']))

    def test_ac2802_node_error_identity_and_consumer_error_are_preserved(self):
        error=ValueError('private-node-error')
        def node(state):raise error
        with Application(self.settings,subject='reader') as app:
            with self.assertRaises(ValueError) as caught:list(app.graph(graph_for(node)).stream({'value':1}))
            self.assertIs(caught.exception,error);self.assertEqual(app.status()['active_calls'],0)
            with self.assertRaises(ValueError) as caught:
                with app.graph(graph_for(lambda state:{'value':2})).stream({'value':1},stream_mode='values') as stream:
                    next(stream);raise error
            self.assertIs(caught.exception,error);self.assertEqual(app.status()['active_calls'],0)
        self.assertEqual([r['attributes']['aegis.graph.outcome'] for r in self.records()],['error','closed'])
        self.assertNotIn('private-node-error',str(self.records()))

    def test_ac2802_failed_cleanup_keeps_lease_and_original_error_until_retry_close(self):
        original=ValueError('private-original');cleanup=RuntimeError('private-cleanup')
        class Source:
            def __init__(self):self.closed=0
            def __next__(self):raise original
            def close(self):
                self.closed+=1
                if self.closed==1:raise cleanup
        raw=graph_for(lambda state:{'value':2});source=Source()
        with Application(self.settings,subject='reader') as app,patch.object(raw,'stream',return_value=source):
            stream=app.graph(raw).stream({'value':1})
            with self.assertRaises(ValueError) as caught:next(stream)
            self.assertIs(caught.exception,original);self.assertEqual(app.status()['active_calls'],1)
            with self.assertRaises(RuntimeError):app.close()
            with self.assertRaises(RuntimeError):next(stream)
            stream.close();self.assertEqual(source.closed,2);self.assertEqual(app.status()['active_calls'],0)

    def test_ac2802_sync_concurrent_pull_and_close_are_rejected_without_releasing_lease(self):
        entered=Event();release=Event();results=[]
        def node(state):entered.set();release.wait(5);return {'value':2}
        with Application(self.settings,subject='reader') as app:
            stream=app.graph(graph_for(node)).stream({'value':1});worker=Thread(target=lambda:results.append(next(stream)))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(RuntimeError):next(stream)
                with self.assertRaises(RuntimeError):stream.close()
                with self.assertRaises(RuntimeError):app.close()
            finally:release.set();worker.join(5)
            self.assertFalse(worker.is_alive());self.assertEqual(len(results),1);stream.close()


class ManagedAsyncGraph(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        aegis.shutdown();self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.settings=load_application(write_application(self.folder))
    async def asyncTearDown(self):aegis.shutdown();self.tmp.cleanup()

    async def test_ac2801_ainvoke_and_astream_eof_with_config_and_borrowed_graph(self):
        calls=[]
        async def node(state,config):calls.append(config['tags']);return {'value':2}
        raw=graph_for(node)
        with Application(self.settings,subject='reader') as app:
            graph=app.graph(raw).with_config(tags=['kept']);self.assertEqual(await graph.ainvoke({'value':1}),{'value':2})
            stream=graph.astream({'value':1},stream_mode='values',version='v2');self.assertEqual(app.status()['active_calls'],0)
            await stream.__anext__();self.assertEqual(app.status()['active_calls'],1)
            sibling=graph.astream({'value':1},stream_mode='values');await sibling.__anext__()
            self.assertEqual(app.status()['active_calls'],2);await sibling.aclose();self.assertEqual(app.status()['active_calls'],1)
            self.assertTrue([item async for item in stream]);self.assertEqual(app.status()['active_calls'],0);await stream.aclose()
            unused=graph.astream({'value':1})
        with self.assertRaises(RuntimeError):await unused.__anext__()
        await unused.aclose();self.assertEqual(calls,[['kept'],['kept']])
        self.assertEqual(await raw.ainvoke({'value':1},config={'tags':['borrowed']}),{'value':2})

    async def test_ac2802_cancel_during_pull_preserves_exception_and_releases_after_cleanup(self):
        started=asyncio.Event();captured=[]
        async def node(state):
            started.set()
            try:await asyncio.Event().wait()
            except asyncio.CancelledError as error:captured.append(error);raise
        with Application(self.settings,subject='reader') as app:
            stream=app.graph(graph_for(node)).astream({'value':1});task=asyncio.create_task(stream.__anext__())
            await asyncio.wait_for(started.wait(),5)
            with self.assertRaises(RuntimeError):await stream.__anext__()
            with self.assertRaises(RuntimeError):await stream.aclose()
            with self.assertRaises(RuntimeError):app.close()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError) as caught:await task
            self.assertIs(caught.exception,captured[0]);self.assertEqual(app.status()['active_calls'],0);await stream.aclose()
        records=[json.loads(line) for line in (self.folder/'traces.jsonl').read_text().splitlines()]
        self.assertEqual(records[0]['attributes']['aegis.graph.outcome'],'cancelled')

    async def test_ac2802_cleanup_cancel_keeps_lease_and_requires_original_loop_for_retry(self):
        error=asyncio.CancelledError('private-close-cancel')
        class Source:
            def __init__(self):self.closes=0
            async def __anext__(self):return {'synthetic':True}
            async def aclose(self):
                self.closes+=1
                if self.closes==1:raise error
        raw=graph_for(lambda state:{'value':2});source=Source()
        with Application(self.settings,subject='reader') as app,patch.object(raw,'astream',return_value=source):
            stream=app.graph(raw).astream({'value':1});await stream.__anext__()
            with self.assertRaises(asyncio.CancelledError) as caught:await stream.aclose()
            self.assertIs(caught.exception,error);self.assertEqual(app.status()['active_calls'],1)
            with self.assertRaises(RuntimeError):await stream.__anext__()
            def other_loop():
                async def close():
                    with self.assertRaises(RuntimeError):await stream.aclose()
                asyncio.run(close())
            await asyncio.to_thread(other_loop);self.assertEqual(source.closes,1)
            with self.assertRaises(RuntimeError):app.close()
            await stream.aclose();self.assertEqual(app.status()['active_calls'],0)

    async def test_ac2802_primary_async_error_survives_cleanup_failure_and_host_can_finish(self):
        primary=ValueError('private-pull');cleanup=RuntimeError('private-cleanup')
        class Source:
            def __init__(self):self.closes=0
            async def __anext__(self):raise primary
            async def aclose(self):
                self.closes+=1
                if self.closes==1:raise cleanup
        raw=graph_for(lambda state:{'value':2});source=Source()
        with Application(self.settings,subject='reader') as app,patch.object(raw,'astream',return_value=source):
            stream=app.graph(raw).astream({'value':1})
            with self.assertRaises(ValueError) as caught:await stream.__anext__()
            self.assertIs(caught.exception,primary);self.assertEqual(app.status()['active_calls'],1)
            await stream.aclose();await stream.aclose();self.assertEqual(source.closes,2)

    async def test_ac2802_consumer_cancellation_context_ends_graph_without_leaking_context(self):
        error=asyncio.CancelledError('private-consumer')
        with Application(self.settings,subject='reader') as app:
            stream=app.graph(graph_for(lambda state:{'value':2})).astream({'value':1},stream_mode='values')
            with self.assertRaises(asyncio.CancelledError) as caught:
                async with stream:
                    await stream.__anext__();self.assertFalse(trace.get_current_span().get_span_context().is_valid);raise error
            self.assertIs(caught.exception,error);self.assertEqual(app.status()['active_calls'],0)
        records=[json.loads(line) for line in (self.folder/'traces.jsonl').read_text().splitlines()]
        self.assertEqual(records[0]['attributes']['aegis.graph.outcome'],'cancelled');self.assertNotIn('private-consumer',str(records))
