"""Short-lived activation and exactly-once completion of a logical model call."""

import asyncio
from contextlib import contextmanager
from threading import RLock

from opentelemetry import context, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from ...tracing.client import current_sdk
from ...tracing.context import _AGENT_NAME
from ...tracing.semantics import LLM_MAPPING_VERSION


def label(value):
    return value if isinstance(value, str) and value.strip() and len(value) <= 128 and "\x00" not in value else None


class CallTrace:
    @classmethod
    def start(cls, api, kwargs, provider="openai"):
        sdk = current_sdk()
        if sdk is None:
            return None
        try:
            return cls(sdk, api, kwargs, provider)
        except Exception:
            sdk.instrumentation_failed()
            return None

    def __init__(self, sdk, api, kwargs, provider):
        self.sdk, self.api = sdk, api
        self._lock, self._finished = RLock(), False
        self.terminal, self.provider_error = None, False
        self.parent = context.get_current()
        model = label(kwargs.get("model")) or "unknown_model"
        attributes = {
            "aegis.mapping.version": LLM_MAPPING_VERSION,
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": provider,
            "gen_ai.request.model": model,
            "aegis.call.api": api,
            "aegis.call.mode": "stream" if kwargs.get("stream") is True else "non_stream",
        }
        agent = context.get_value(_AGENT_NAME, self.parent)
        if agent is not None:
            attributes["gen_ai.agent.name"] = agent
        self.span = sdk.tracer.start_span(f"chat {model}", context=self.parent, kind=SpanKind.CLIENT, attributes=attributes)

    @contextmanager
    def activate(self):
        token = None
        try:
            if not self._finished:
                token = context.attach(trace.set_span_in_context(self.span, self.parent))
        except Exception:
            self.sdk.instrumentation_failed()
        try:
            yield
        finally:
            if token is not None:
                try:
                    context.detach(token)
                except Exception:
                    self.sdk.instrumentation_failed()

    def capture(self, value, *, streaming=False):
        try:
            if self._finished:
                return
            response = value
            if self.api == "responses" and streaming:
                event_type = getattr(value, "type", None)
                if event_type not in ("response.completed", "response.failed", "response.incomplete"):
                    return
                response = value.response
            model = label(getattr(response, "model", None))
            if model:
                self.span.set_attribute("gen_ai.response.model", model)
            usage = getattr(response, "usage", None)
            for destination, source in (("input", "input" if self.api == "responses" else "prompt"), ("output", "output" if self.api == "responses" else "completion")):
                number = getattr(usage, source + "_tokens", None)
                if type(number) is int and 0 <= number <= 2**63 - 1:
                    self.span.set_attribute(f"gen_ai.usage.{destination}_tokens", number)
            if self.api == "responses":
                state = getattr(response, "status", None)
                if state == "failed":
                    self.terminal, self.provider_error = "error", True
                elif state in ("completed", "incomplete"):
                    self.terminal = state
                elif not streaming:
                    self.terminal = "incomplete"
            elif not streaming or any(getattr(choice, "finish_reason", None) is not None for choice in getattr(value, "choices", [])):
                self.terminal = "completed"
        except Exception:
            self.sdk.instrumentation_failed()

    def finish(self, outcome, error=None):
        with self._lock:
            if self._finished:
                return
            self._finished = True
            if error is not None:
                outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
            elif outcome in ("completed", "closed") and self.terminal:
                outcome = self.terminal
            elif outcome == "completed":
                outcome = "incomplete"
            try:
                self.span.set_attribute("aegis.call.outcome", outcome)
                if error is not None or self.provider_error:
                    error_type = f"{type(error).__module__}.{type(error).__qualname__}"[:256] if error is not None else "openai.response.failed"
                    self.span.set_attribute("error.type", error_type)
                    self.span.set_status(Status(StatusCode.ERROR))
                    self.span.add_event("exception", {"exception.type": error_type})
            except Exception:
                self.sdk.instrumentation_failed()
            finally:
                try:
                    self.span.end()
                except Exception:
                    self.sdk.instrumentation_failed()
