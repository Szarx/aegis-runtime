"""Explicit SDK configuration without replacing the host tracer provider."""

from importlib.metadata import version
from collections.abc import Mapping
from pathlib import Path
from threading import Lock, RLock

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter

from .._version import __version__
from ..exporters import JsonlSpanExporter
from ..exporters.batch import BoundedSpanProcessor
from .semantics import validate_label, validate_timeout

_state_lock = RLock()
_default: "SDK | None" = None


class SDK:
    """A privately owned provider, exporter and lifecycle handle."""

    def __init__(
        self,
        service_name: str,
        exporter: SpanExporter,
        max_queue_size: int,
        max_export_batch_size: int,
        schedule_delay_millis: int,
    ):
        self._lock = Lock()
        self._enabled = True
        self._instrumentation_failures = 0
        self.service_name = service_name
        self._health = None
        self._processor = BoundedSpanProcessor(
            exporter, max_queue_size, max_export_batch_size, schedule_delay_millis
        )
        self._provider = TracerProvider(
            resource=Resource(
                {
                    "service.name": service_name,
                    "telemetry.sdk.name": "opentelemetry",
                    "telemetry.sdk.language": "python",
                    "telemetry.sdk.version": version("opentelemetry-sdk"),
                }
            ),
            shutdown_on_exit=False,
            span_limits=SpanLimits(
                max_attributes=32, max_events=8, max_links=8, max_attribute_length=256
            ),
        )
        self._provider.add_span_processor(self._processor)
        self.tracer = self._provider.get_tracer("aegis", __version__)

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def instrumentation_failed(self) -> None:
        with self._lock:
            self._instrumentation_failures += 1

    def diagnostics(self) -> dict[str, int]:
        result = self._processor.diagnostics()
        with self._lock:
            result["instrumentation_failures"] = self._instrumentation_failures
        return result

    def flush(self, timeout_millis: int = 5000) -> bool:
        return self._processor.force_flush(timeout_millis)

    def start_health_reporting(self, endpoint: str, *, token: str | None = None, interval_seconds=10) -> str:
        from ..health import HealthReporter
        with self._lock:
            if not self._enabled or self._health is not None:
                raise RuntimeError('Health reporting requires an active SDK and can start once')
            reporter = HealthReporter(self, endpoint, token, interval_seconds)
            self._health = reporter
            return reporter.start()

    def shutdown(self, timeout_millis: int = 5000) -> bool:
        global _default
        validate_timeout(timeout_millis)
        with _state_lock:
            if _default is self:
                _default = None
        with self._lock:
            first_close = self._enabled
            self._enabled = False
            if self._health is not None:
                self._health.stop()
        if first_close:
            self._provider.shutdown()
        return self._processor.close(timeout_millis)


def current_sdk() -> SDK | None:
    sdk = _default
    return sdk if sdk is not None and sdk.enabled else None


def init(
    service_name: str,
    *,
    output_path: str | Path | None = None,
    exporter: SpanExporter | None = None,
    endpoint: str | None = None,
    export_timeout_millis: int = 3000,
    headers: Mapping[str, str] | None = None,
    max_queue_size: int = 1024,
    max_export_batch_size: int = 64,
    schedule_delay_millis: int = 1000,
) -> SDK:
    """Configure local tracing once, before starting application work."""
    global _default
    validate_label(service_name, "service_name")
    if sum(value is not None for value in (exporter, output_path, endpoint)) > 1:
        raise ValueError("supply only one of exporter, output_path or endpoint")
    if headers is not None and endpoint is None:
        raise ValueError("headers require an OTLP endpoint")
    with _state_lock:
        if current_sdk() is not None:
            raise RuntimeError("Aegis is already initialized; shut down before reinitializing")
        if endpoint is not None:
            from ..exporters.otlp import build_otlp_exporter
            selected = build_otlp_exporter(endpoint, export_timeout_millis, headers)
        else:
            selected = exporter if exporter is not None else JsonlSpanExporter(
                output_path if output_path is not None else "artifacts/traces.jsonl"
            )
        _default = SDK(
            service_name,
            selected,
            max_queue_size,
            max_export_batch_size,
            schedule_delay_millis,
        )
        return _default


def flush(timeout_millis: int = 5000) -> bool:
    validate_timeout(timeout_millis)
    sdk = current_sdk()
    return sdk.flush(timeout_millis) if sdk is not None else True


def shutdown(timeout_millis: int = 5000) -> bool:
    validate_timeout(timeout_millis)
    sdk = current_sdk()
    return sdk.shutdown(timeout_millis) if sdk is not None else True
