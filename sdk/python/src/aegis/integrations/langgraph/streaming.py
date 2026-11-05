"""Lazy graph tracing without keeping an attached context across a yield."""

import asyncio
from contextlib import contextmanager
from threading import RLock

from opentelemetry import context, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from ...tracing.client import current_sdk
from ...tracing.context import _AGENT_NAME
from ...tracing.semantics import GRAPH_MAPPING_VERSION


class _GraphCall:
    def __init__(self, sdk, name, mode):
        self.sdk, self.name, self.mode = sdk, name, mode
        self.parent = context.get_current()
        self.span = None
        self._started = self._finished = False
        self._lock = RLock()

    @contextmanager
    def activate(self, *, start=False):
        token = None
        try:
            with self._lock:
                if start and not self._started and not self._finished:
                    self._started = True
                    if self.sdk.enabled:
                        self.span = self.sdk.tracer.start_span(
                            f"invoke_agent {self.name}", context=self.parent, kind=SpanKind.INTERNAL,
                            attributes={"aegis.mapping.version": GRAPH_MAPPING_VERSION,
                                        "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": self.name,
                                        "aegis.graph.mode": self.mode},
                        )
                if self.span is not None and not self._finished:
                    active = context.set_value(_AGENT_NAME, self.name, trace.set_span_in_context(self.span, self.parent))
                    token = context.attach(active)
        except Exception:
            self.sdk.instrumentation_failed()
        try:
            yield
        finally:
            if token is not None:
                try: context.detach(token)
                except Exception: self.sdk.instrumentation_failed()

    def finish(self, outcome, error=None):
        with self._lock:
            if self._finished: return
            self._finished = True
            if self.span is None: return
            if error is not None:
                outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
            try:
                self.span.set_attribute("aegis.graph.outcome", outcome)
                if error is not None:
                    kind = f"{type(error).__module__}.{type(error).__qualname__}"[:256]
                    self.span.set_attribute("error.type", kind)
                    self.span.set_status(Status(StatusCode.ERROR))
                    self.span.add_event("exception", {"exception.type": kind})
            except Exception:
                self.sdk.instrumentation_failed()
            finally:
                try: self.span.end()
                except Exception: self.sdk.instrumentation_failed()


class GraphStream:
    def __init__(self, stream, call):
        self._stream, self._call = stream, call

    def __iter__(self): return self

    def __next__(self):
        try:
            with self._call.activate(start=True):
                return next(self._stream)
        except StopIteration:
            self._call.finish("completed")
            raise
        except BaseException as error:
            self._call.finish("error", error)
            raise

    def _close(self, primary=None):
        try:
            with self._call.activate():
                result = self._stream.close()
        except BaseException as error:
            self._call.finish("error", primary if isinstance(primary, asyncio.CancelledError) else error)
            raise
        self._call.finish("closed", primary if isinstance(primary, asyncio.CancelledError) else None)
        return result

    def close(self): return self._close()
    def __enter__(self): return self

    def __exit__(self, kind, error, tb):
        try: self._close(error)
        except BaseException:
            if error is None: raise
        return False


class AsyncGraphStream:
    def __init__(self, stream, call):
        self._stream, self._call = stream, call

    def __aiter__(self): return self

    async def __anext__(self):
        try:
            with self._call.activate(start=True):
                return await self._stream.__anext__()
        except StopAsyncIteration:
            self._call.finish("completed")
            raise
        except BaseException as error:
            self._call.finish("error", error)
            raise

    async def _close(self, primary=None):
        try:
            with self._call.activate():
                result = await self._stream.aclose()
        except BaseException as error:
            self._call.finish("error", primary if isinstance(primary, asyncio.CancelledError) else error)
            raise
        self._call.finish("closed", primary if isinstance(primary, asyncio.CancelledError) else None)
        return result

    async def aclose(self): return await self._close()
    async def __aenter__(self): return self

    async def __aexit__(self, kind, error, tb):
        try: await self._close(error)
        except BaseException:
            if error is None: raise
        return False


def observe_stream(stream, name, *, asynchronous=False):
    sdk = current_sdk()
    if sdk is None: return stream
    call = _GraphCall(sdk, name, "astream" if asynchronous else "stream")
    return (AsyncGraphStream if asynchronous else GraphStream)(stream, call)
