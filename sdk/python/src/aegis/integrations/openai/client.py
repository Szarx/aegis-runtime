"""Narrow proxies around public SDK create, iteration and close interfaces."""

import asyncio
from functools import wraps

from openai import AsyncOpenAI, OpenAI

from .tracing import CallTrace


class StreamProxy:
    def __init__(self, stream, call):
        self._stream, self._call = stream, call
        self._iterator = iter(stream)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            with self._call.activate():
                value = next(self._iterator)
        except StopIteration:
            self._call.finish("completed")
            raise
        except BaseException as error:
            self._call.finish("error", error)
            raise
        self._call.capture(value, streaming=True)
        return value

    def close(self):
        try:
            with self._call.activate():
                result = self._stream.close()
        except BaseException as error:
            self._call.finish("error", error)
            raise
        self._call.finish("closed")
        return result

    def __enter__(self):
        try:
            with self._call.activate():
                self._stream.__enter__()
        except BaseException as error:
            self._call.finish("error", error)
            raise
        return self

    def __exit__(self, kind, error, tb):
        try:
            with self._call.activate():
                return self._stream.__exit__(kind, error, tb)
        except BaseException as close_error:
            self._call.finish("error", close_error)
            raise
        finally:
            self._call.finish("closed", error if isinstance(error, asyncio.CancelledError) else None)


class AsyncStreamProxy:
    def __init__(self, stream, call):
        self._stream, self._call = stream, call
        self._iterator = stream.__aiter__()

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            with self._call.activate():
                value = await self._iterator.__anext__()
        except StopAsyncIteration:
            self._call.finish("completed")
            raise
        except BaseException as error:
            self._call.finish("error", error)
            raise
        self._call.capture(value, streaming=True)
        return value

    async def close(self):
        try:
            with self._call.activate():
                result = await self._stream.close()
        except BaseException as error:
            self._call.finish("error", error)
            raise
        self._call.finish("closed")
        return result

    async def aclose(self):
        return await self.close()

    async def __aenter__(self):
        try:
            with self._call.activate():
                await self._stream.__aenter__()
        except BaseException as error:
            self._call.finish("error", error)
            raise
        return self

    async def __aexit__(self, kind, error, tb):
        try:
            with self._call.activate():
                return await self._stream.__aexit__(kind, error, tb)
        except BaseException as close_error:
            self._call.finish("error", close_error)
            raise
        finally:
            self._call.finish("closed", error if isinstance(error, asyncio.CancelledError) else None)


class ResourceProxy:
    def __init__(self, resource, path, asynchronous, provider):
        self._resource, self._path, self._async = resource, path, asynchronous
        self._provider = provider

    def __getattr__(self, name):
        original = getattr(self._resource, name)
        if self._path == "chat" and name == "completions":
            return ResourceProxy(original, "chat.completions", self._async, self._provider)
        if name != "create" or self._path not in ("responses", "chat.completions"):
            return original

        if self._async:
            @wraps(original)
            async def invoke(*args, **kwargs):
                call = CallTrace.start(self._path, kwargs, self._provider)
                if call is None:
                    return await original(*args, **kwargs)
                try:
                    with call.activate():
                        result = await original(*args, **kwargs)
                except BaseException as error:
                    call.finish("error", error)
                    raise
                if kwargs.get("stream") is True:
                    return AsyncStreamProxy(result, call)
                call.capture(result)
                call.finish("completed")
                return result
        else:
            @wraps(original)
            def invoke(*args, **kwargs):
                call = CallTrace.start(self._path, kwargs, self._provider)
                if call is None:
                    return original(*args, **kwargs)
                try:
                    with call.activate():
                        result = original(*args, **kwargs)
                except BaseException as error:
                    call.finish("error", error)
                    raise
                if kwargs.get("stream") is True:
                    return StreamProxy(result, call)
                call.capture(result)
                call.finish("completed")
                return result
        return invoke


class ClientProxy:
    def __init__(self, client, provider="openai"):
        if provider not in ("openai", "deepseek"):
            raise ValueError("provider must be openai or deepseek")
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_async", isinstance(client, AsyncOpenAI))
        object.__setattr__(self, "_provider", provider)

    def __getattr__(self, name):
        original = getattr(self._client, name)
        if name in ("responses", "chat"):
            if self._provider == "deepseek" and name == "responses":
                return original
            return ResourceProxy(original, name, self._async, self._provider)
        if name in ("with_options", "copy"):
            @wraps(original)
            def options(*args, **kwargs):
                return wrap_openai(original(*args, **kwargs), provider=self._provider)
            return options
        return original

    def __setattr__(self, name, value):
        setattr(self._client, name, value)

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, *args):
        return self._client.__exit__(*args)

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self._client.__aexit__(*args)


class AegisOpenAI(ClientProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(OpenAI(*args, **kwargs))


class AegisAsyncOpenAI(ClientProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(AsyncOpenAI(*args, **kwargs))


def wrap_openai(client, *, provider=None):
    if isinstance(client, ClientProxy):
        if provider is not None and provider != client._provider:
            raise ValueError("client is already wrapped with a different provider")
        return client
    if not isinstance(client, (OpenAI, AsyncOpenAI)):
        raise TypeError("wrap_openai requires an official OpenAI or AsyncOpenAI client")
    return ClientProxy(client, "openai" if provider is None else provider)
