"""Bounded batch adapter over OpenTelemetry's public SpanProcessor API."""

from collections import deque
from threading import Condition, Thread
from time import monotonic

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from ..tracing.semantics import validate_timeout


class BoundedSpanProcessor(SpanProcessor):
    def __init__(
        self,
        exporter: SpanExporter,
        max_queue_size: int,
        max_export_batch_size: int,
        schedule_delay_millis: int,
    ):
        for value in (max_queue_size, max_export_batch_size, schedule_delay_millis):
            if type(value) is not int or value <= 0:
                raise ValueError("queue size, batch size and schedule delay must be positive integers")
        if max_export_batch_size > max_queue_size:
            raise ValueError("batch size cannot exceed queue size")
        self._exporter = exporter
        self._capacity = max_queue_size
        self._batch_size = max_export_batch_size
        self._delay = schedule_delay_millis / 1000
        self._condition = Condition()
        self._queue: deque[ReadableSpan] = deque()
        self._closing = False
        self._submitted = 0
        self._completed = 0
        self._flush_target = 0
        self._exported = 0
        self._failed = 0
        self._dropped = 0
        self._export_failures = 0
        self._active = {}
        self._active_count = 0
        self._worker = Thread(target=self._run, name="aegis-span-export", daemon=True)
        self._worker.start()

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        with self._condition:
            self._active_count += 1
            context = span.get_span_context()
            if len(self._active) < 128:
                self._active[context.span_id] = format(context.trace_id, '032x')

    def on_end(self, span: ReadableSpan) -> None:
        with self._condition:
            self._active_count = max(0, self._active_count - 1)
            self._active.pop(span.context.span_id, None)
            if self._closing or len(self._queue) >= self._capacity:
                self._dropped += 1
                return
            self._submitted += 1
            self._queue.append(span)
            self._condition.notify_all()

    def _run(self) -> None:
        try:
            while True:
                with self._condition:
                    while not self._queue and not self._closing:
                        self._condition.wait()
                    if not self._queue and self._closing:
                        break
                    deadline = monotonic() + self._delay
                    while (
                        len(self._queue) < self._batch_size
                        and not self._closing
                        and self._completed >= self._flush_target
                    ):
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            break
                        self._condition.wait(remaining)
                    batch = [self._queue.popleft() for _ in range(min(len(self._queue), self._batch_size))]
                try:
                    succeeded = self._exporter.export(batch) is SpanExportResult.SUCCESS
                except Exception:
                    # Exporter messages/tracebacks can contain sensitive application data.
                    succeeded = False
                with self._condition:
                    self._completed += len(batch)
                    if succeeded:
                        self._exported += len(batch)
                    else:
                        self._failed += len(batch)
                        self._export_failures += 1
                    self._condition.notify_all()
        finally:
            try:
                self._exporter.shutdown()
            except Exception:
                with self._condition:
                    self._export_failures += 1

    def force_flush(self, timeout_millis: int = 5000) -> bool:
        validate_timeout(timeout_millis)
        deadline = monotonic() + timeout_millis / 1000
        with self._condition:
            target = self._submitted
            self._flush_target = max(target, self._flush_target)
            self._condition.notify_all()
            while self._completed < target:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return self._export_failures == 0

    def close(self, timeout_millis: int) -> bool:
        validate_timeout(timeout_millis)
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        self._worker.join(timeout_millis / 1000)
        with self._condition:
            return not self._worker.is_alive() and self._export_failures == 0

    def shutdown(self) -> None:
        # The SDK lifecycle handle owns the bounded wait, including exporter shutdown.
        self.close(0)

    def diagnostics(self) -> dict[str, int]:
        with self._condition:
            return {
                "accepted_spans": self._submitted,
                "exported_spans": self._exported,
                "failed_spans": self._failed,
                "dropped_spans": self._dropped,
                "pending_spans": self._submitted - self._completed,
                "export_failures": self._export_failures,
            }

    def activity(self):
        with self._condition:
            traces = sorted(set(self._active.values()))
            return {'active_spans': self._active_count, 'active_traces': traces[:16],
                    'activity_truncated': self._active_count > len(self._active) or len(traces) > 16}
