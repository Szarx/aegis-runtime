"""SPEC-007: real graph iterators, without provider network requests."""

import asyncio
import inspect
import os
from typing import TypedDict
import unittest
from unittest.mock import patch

import aegis
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from aegis.exporters.jsonl import span_record

try:
    from aegis.langgraph import observe_graph
    from examples.langgraph.agent import build_agent,initial_state,business_view
    from examples.deepseek.offline import Fixture,PRIVATE_TEXT
    from langgraph.graph import StateGraph,START,END
    from langgraph.config import get_stream_writer
    from langchain_core.messages import BaseMessage
    from langchain_core.callbacks import BaseCallbackHandler
    from openai import OpenAI,AsyncOpenAI
    AVAILABLE=True
except ImportError:
    AVAILABLE=False


def normalize(value):
    if isinstance(value,BaseMessage):return value.model_dump(exclude={'id'})
    if isinstance(value,dict):return {key:normalize(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [normalize(item) for item in value]
    return value


@unittest.skipUnless(AVAILABLE,'install LangGraph, model and OTLP extras')
class GraphStreamAcceptance(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'})
        self.env.start();aegis.shutdown()
        self.exporter=InMemorySpanExporter()
        self.sdk=aegis.init('graph-stream-tests',exporter=self.exporter)
    def tearDown(self):aegis.shutdown();self.env.stop()
    def spans(self):
        self.assertTrue(aegis.flush())
        return self.exporter.get_finished_spans()
    def graphs(self):return [s for s in self.spans() if s.attributes.get('aegis.mapping.version')=='aegis.graph.v1']
    def client(self):return OpenAI(api_key='synthetic-key',base_url='https://offline.invalid/v1',http_client=Fixture().http_client(),max_retries=0)

    def test_ac701_real_modes_versions_identity_and_custom_payload_privacy(self):
        class Callback(BaseCallbackHandler):
            def __init__(self):self.starts=0
            def on_chain_start(self,*args,**kwargs):self.starts+=1
        with self.client() as client:
            for options in ({'stream_mode':'updates'},{'stream_mode':'values','version':'v2'},{'stream_mode':['updates','values'],'version':'v2'}):
                before,bc=build_agent(client)
                after,ac=build_agent(client,traced=True)
                callback=Callback();config={'callbacks':[callback],'metadata':{'private':PRIVATE_TEXT}}
                before=before.with_config(tags=['preserved-tag'])
                after=after.with_config(tags=['preserved-tag'])
                expected=list(before.stream(initial_state(),config=config,**options))
                starts=callback.starts
                result=list(after.stream(initial_state(),config=config,**options))
                self.assertEqual(callback.starts,starts*2)
                self.assertEqual(normalize(expected),normalize(result))
                self.assertEqual(ac,bc)
                self.assertEqual(ac,{'model_calls':2,'tool_calls':1})
        class State(TypedDict):value:int
        payload={'private':PRIVATE_TEXT}
        def node(state):get_stream_writer()(payload);return {'value':2}
        raw=StateGraph(State).add_node('step',node).add_edge(START,'step').add_edge('step',END).compile()
        captured=[];original=raw.stream
        def source(*args,**kwargs):
            for value in original(*args,**kwargs):captured.append(value);yield value
        with patch.object(raw,'stream',source):
            result=list(observe_graph(raw).stream({'value':1},stream_mode=['custom','updates'],version='v2'))
        self.assertTrue(all(a is b for a,b in zip(result,captured)))
        self.assertEqual(result[0]['data'],payload)
        self.assertEqual(len(self.graphs()),4)
        record=span_record(self.graphs()[-1])
        self.assertEqual(record['schema_version'],'aegis.span.v3')
        self.assertNotIn(PRIVATE_TEXT,str(record))

    def test_ac701_lazy_unused_close_and_sdk_shutdown_before_first_next(self):
        with self.client() as client:
            graph,counts=build_agent(client,traced=True)
            stream=graph.stream(initial_state())
            self.assertEqual(counts,{'model_calls':0,'tool_calls':0})
            stream.close();stream.close()
            self.assertEqual(self.spans(),())
            other=graph.stream(initial_state())
            aegis.shutdown()
            list(other)
            self.assertEqual(self.exporter.get_finished_spans(),())
            raw=graph.stream(initial_state())
            self.assertTrue(inspect.isgenerator(raw));raw.close()

    def test_ac702_ac703_early_close_and_consumer_tool_parent_restored(self):
        @aegis.tool(name='consumer-tool')
        def consumer():return None
        with self.client() as client:
            graph,counts=build_agent(client,traced=True)
            @aegis.observe(name='consumer-agent')
            def run():
                parent=trace.get_current_span().get_span_context().span_id
                with graph.stream(initial_state(),stream_mode='updates') as stream:
                    next(stream)
                    self.assertEqual(trace.get_current_span().get_span_context().span_id,parent)
                    consumer()
                stream.close()
            run()
        spans=self.spans();graph_span=self.graphs()[0]
        outer=next(s for s in spans if s.name=='invoke_agent consumer-agent')
        tool=next(s for s in spans if s.name=='execute_tool consumer-tool')
        self.assertEqual(tool.parent.span_id,outer.context.span_id)
        self.assertEqual(graph_span.parent.span_id,outer.context.span_id)
        self.assertEqual(graph_span.attributes['aegis.graph.outcome'],'closed')
        self.assertEqual(counts,{'model_calls':1,'tool_calls':0})

    def test_ac702_graph_handled_error_keeps_completed_lifecycle(self):
        with self.client() as client:
            graph,_=build_agent(client,traced=True,fail_tool=True,handle_tool_errors=True)
            list(graph.stream(initial_state()))
        self.assertEqual(self.graphs()[0].attributes['aegis.graph.outcome'],'completed')
        self.assertEqual(self.graphs()[0].status.status_code.name,'UNSET')
        self.assertEqual(sum(s.status.status_code.name=='ERROR' for s in self.spans()),1)

    def test_ac702_unhandled_error_and_normal_consumer_error_identity(self):
        error=ValueError(PRIVATE_TEXT)
        with self.client() as client:
            graph,_=build_agent(client,traced=True,fail_tool=True,tool_error=error)
            with self.assertRaises(ValueError) as raised:list(graph.stream(initial_state()))
            self.assertIs(raised.exception,error)
            other,_=build_agent(client,traced=True)
            with self.assertRaises(ValueError) as raised:
                with other.stream(initial_state(),stream_mode='values') as events:
                    next(events);raise error
            self.assertIs(raised.exception,error)
        self.assertEqual([s.attributes['aegis.graph.outcome'] for s in self.graphs()],['error','closed'])

    def test_ac701_ac703_async_complete_close_and_concurrent_context(self):
        @aegis.tool(name='async-consumer')
        def consumer():return None
        async def execute():
            async with AsyncOpenAI(api_key='synthetic',http_client=Fixture(asynchronous=True).http_client()) as client:
                graph,counts=build_agent(client,traced=True,asynchronous=True)
                async def consume():
                    values=[]
                    async with graph.astream(initial_state(),stream_mode='updates',version='v2') as stream:
                        async for value in stream:values.append(value);consumer()
                    return values
                a,b=await asyncio.gather(consume(),consume())
                self.assertEqual(normalize(a),normalize(b))
                other,_=build_agent(client,traced=True,asynchronous=True)
                async with other.astream(initial_state(),stream_mode='values') as stream:
                    await stream.__anext__()
                await stream.aclose()
                self.assertEqual(counts,{'model_calls':4,'tool_calls':2})
        asyncio.run(execute())
        graphs=self.graphs()
        self.assertEqual([s.attributes['aegis.graph.outcome'] for s in graphs].count('completed'),2)
        self.assertEqual(len({s.context.trace_id for s in graphs}),3)
        self.assertTrue(all(s.parent is None for s in self.spans() if s.name=='execute_tool async-consumer'))
        for root in graphs:
            children=[s for s in self.spans() if s.context.trace_id==root.context.trace_id and s is not root]
            self.assertTrue(all(s.parent.span_id==root.context.span_id for s in children))

    def test_ac702_async_cancel_during_next_preserves_original_error(self):
        async def execute():
            class State(TypedDict):value:int
            started=asyncio.Event()
            async def node(state):started.set();await asyncio.Event().wait()
            raw=StateGraph(State).add_node('wait',node).add_edge(START,'wait').add_edge('wait',END).compile()
            captured=[];original=raw.astream
            async def source(*args,**kwargs):
                try:
                    async for value in original(*args,**kwargs):yield value
                except BaseException as error:captured.append(error);raise
            with patch.object(raw,'astream',source):
                stream=observe_graph(raw).astream({'value':1},stream_mode='updates')
                task=asyncio.create_task(stream.__anext__())
                await started.wait();task.cancel()
                with self.assertRaises(asyncio.CancelledError) as raised:await task
                self.assertIs(raised.exception,captured[0])
                await stream.aclose()
        asyncio.run(execute())
        self.assertEqual(len(self.graphs()),1)
        self.assertEqual(self.graphs()[0].attributes['aegis.graph.outcome'],'cancelled')

    def test_ac702_async_context_consumer_cancel_and_unconsumed_close(self):
        async def execute():
            async with AsyncOpenAI(api_key='synthetic',http_client=Fixture(asynchronous=True).http_client()) as client:
                graph,_=build_agent(client,traced=True,asynchronous=True)
                unused=graph.astream(initial_state());await unused.aclose()
                self.assertEqual(self.spans(),())
                error=asyncio.CancelledError()
                with self.assertRaises(asyncio.CancelledError) as raised:
                    async with graph.astream(initial_state(),stream_mode='values') as stream:
                        await stream.__anext__();raise error
                self.assertIs(raised.exception,error)
        asyncio.run(execute())
        self.assertEqual(len(self.graphs()),1)
        self.assertEqual(self.graphs()[0].attributes['aegis.graph.outcome'],'cancelled')

    def test_ac702_close_failure_and_existing_context_error_preserved(self):
        class State(TypedDict):value:int
        raw=StateGraph(State).add_node('step',lambda s:{'value':2}).add_edge(START,'step').add_edge('step',END).compile()
        original=raw.stream;cleanup_error=RuntimeError(PRIVATE_TEXT)
        class BrokenClose:
            def __init__(self,*args,**kwargs):self.source=original(*args,**kwargs)
            def __next__(self):return next(self.source)
            def close(self):self.source.close();raise cleanup_error
        with patch.object(raw,'stream',BrokenClose):
            graph=observe_graph(raw)
            stream=graph.stream({'value':1},stream_mode='values');next(stream)
            with self.assertRaises(RuntimeError) as raised:stream.close()
            self.assertIs(raised.exception,cleanup_error)
            body_error=ValueError('consumer only')
            with self.assertRaises(ValueError) as raised:
                with graph.stream({'value':1},stream_mode='values') as other:
                    next(other);raise body_error
            self.assertIs(raised.exception,body_error)
        async def execute():
            original_async=raw.astream
            class BrokenAsyncClose:
                def __init__(self,*args,**kwargs):self.source=original_async(*args,**kwargs)
                async def __anext__(self):return await self.source.__anext__()
                async def aclose(self):await self.source.aclose();raise cleanup_error
            with patch.object(raw,'astream',BrokenAsyncClose):
                graph=observe_graph(raw)
                stream=graph.astream({'value':1},stream_mode='values');await stream.__anext__()
                with self.assertRaises(RuntimeError) as raised:await stream.aclose()
                self.assertIs(raised.exception,cleanup_error)
                with self.assertRaises(ValueError) as raised:
                    async with graph.astream({'value':1},stream_mode='values') as other:
                        await other.__anext__();raise body_error
                self.assertIs(raised.exception,body_error)
        asyncio.run(execute())
        self.assertEqual(len(self.graphs()),4)
        self.assertTrue(all(s.attributes['aegis.graph.outcome']=='error' for s in self.graphs()))

    def test_ac704_observation_failure_does_not_repeat_business(self):
        with self.client() as client:
            graph,counts=build_agent(client,traced=True)
            with patch.object(self.sdk.tracer,'start_span',side_effect=RuntimeError('observability only')):
                result=list(graph.stream(initial_state(),stream_mode='updates'))
        self.assertEqual(len(result),3)
        self.assertEqual(counts,{'model_calls':2,'tool_calls':1})
        self.assertEqual(self.spans(),())
        self.assertGreater(self.sdk.diagnostics()['instrumentation_failures'],0)
