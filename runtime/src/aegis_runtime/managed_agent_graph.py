"""Borrowed graph calls and streams with an Application-owned execution lease."""
import asyncio
from threading import Lock


class ManagedGraph:
    def __init__(self,application,observed):self._application=application;self._observed=observed
    def invoke(self,*args,**kwargs):
        with self._application._lease():return self._observed.invoke(*args,**kwargs)
    async def ainvoke(self,*args,**kwargs):
        with self._application._lease():return await self._observed.ainvoke(*args,**kwargs)
    def with_config(self,*args,**kwargs):
        with self._application._lease():return ManagedGraph(self._application,self._observed.with_config(*args,**kwargs))
    def stream(self,*args,**kwargs):
        with self._application._lease():return ManagedGraphStream(self._application,self._observed.stream(*args,**kwargs))
    def astream(self,*args,**kwargs):
        with self._application._lease():return ManagedAsyncGraphStream(self._application,self._observed.astream(*args,**kwargs))


class _Stream:
    def __init__(self,application,source):
        self._application=application;self._source=source;self._lease=None
        self._finished=False;self._failed=False;self._operation=Lock()
    def _enter_operation(self):
        if not self._operation.acquire(False):raise RuntimeError('Graph stream already has an operation')
    def _start(self):
        if self._failed:raise RuntimeError('Graph stream cleanup required before Application close')
        if self._lease is None:
            lease=self._application._lease();lease.__enter__();self._lease=lease
    def _finish(self):
        self._finished=True
        if self._lease is not None:
            lease=self._lease;self._lease=None;lease.__exit__(None,None,None)


class ManagedGraphStream(_Stream):
    def __iter__(self):return self
    def __next__(self):
        self._enter_operation()
        try:
            if self._finished:raise StopIteration
            self._start()
            try:return next(self._source)
            except StopIteration:
                self._finish();raise
            except BaseException:
                self._failed=True
                try:self._source.close()
                except BaseException:pass
                else:self._finish()
                raise
        finally:self._operation.release()
    def _close(self,error=None):
        self._enter_operation()
        try:
            if self._finished:return None
            try:
                result=self._source.close() if error is None else self._source.__exit__(type(error),error,error.__traceback__)
            except BaseException:
                self._failed=True;raise
            self._finish();return result
        finally:self._operation.release()
    def close(self):return self._close()
    def __enter__(self):return self
    def __exit__(self,kind,error,tb):
        try:self._close(error)
        except BaseException:
            if error is None:raise
        return False


class ManagedAsyncGraphStream(_Stream):
    def __init__(self,application,source):super().__init__(application,source);self._loop=None
    def _bind_loop(self):
        loop=asyncio.get_running_loop()
        if self._loop is not None and loop is not self._loop:raise RuntimeError('Graph stream requires its original event loop')
        self._loop=loop
    def __aiter__(self):return self
    async def __anext__(self):
        self._bind_loop();self._enter_operation()
        try:
            if self._finished:raise StopAsyncIteration
            self._start()
            try:return await self._source.__anext__()
            except StopAsyncIteration:
                self._finish();raise
            except BaseException:
                self._failed=True
                try:await self._source.aclose()
                except BaseException:pass
                else:self._finish()
                raise
        finally:self._operation.release()
    async def _close(self,error=None):
        self._bind_loop();self._enter_operation()
        try:
            if self._finished:return None
            try:
                result=await self._source.aclose() if error is None else await self._source.__aexit__(type(error),error,error.__traceback__)
            except BaseException:
                self._failed=True;raise
            self._finish();return result
        finally:self._operation.release()
    async def aclose(self):return await self._close()
    async def __aenter__(self):return self
    async def __aexit__(self,kind,error,tb):
        try:await self._close(error)
        except BaseException:
            if error is None:raise
        return False
