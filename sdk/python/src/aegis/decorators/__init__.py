"""Explicit function boundaries for native Python agents and tools."""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from ..tracing.context import operation_span
from ..tracing.semantics import validate_label

P = ParamSpec("P")
R = TypeVar("R")


def _decorate(function: Callable[P, R], operation: str, name: str | None, permission: str | None):
    if inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
        raise TypeError("generator tracing is not supported by SPEC-001")
    label = validate_label(name if name is not None else function.__name__, "name")
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs):
            with operation_span(operation, label, permission):
                return await function(*args, **kwargs)
        return async_wrapper

    @wraps(function)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs):
        with operation_span(operation, label, permission):
            return function(*args, **kwargs)
    return sync_wrapper


def observe(function: Callable[P, R] | None = None, *, name: str | None = None):
    """Trace an agent boundary; supports bare and configured decorator forms."""
    if name is not None:
        validate_label(name, "name")
    def decorate(target):
        return _decorate(target, "invoke_agent", name, None)
    return decorate(function) if function is not None else decorate


def tool(
    function: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    permission: str | None = None,
):
    """Trace one tool call; permission is metadata, not policy enforcement."""
    if name is not None:
        validate_label(name, "name")
    if permission is not None:
        validate_label(permission, "permission")
    def decorate(target):
        return _decorate(target, "execute_tool", name, permission)
    return decorate(function) if function is not None else decorate


__all__ = ["observe", "tool"]
