"""Local debugging format, intentionally distinct from OTLP."""

import json
from collections.abc import Sequence
from pathlib import Path
from threading import Lock

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from ..tracing.semantics import ATTRIBUTE_KEYS, RESOURCE_KEYS, LLM_MAPPING_VERSION, LLM_STRING_KEYS, TOKEN_KEYS, GRAPH_MAPPING_VERSION, GRAPH_KEYS
from ..tracing.semantics import GOVERNANCE_MAPPING_VERSION, GOVERNANCE_KEYS, APPROVAL_GOVERNANCE_KEYS


def span_record(span: ReadableSpan) -> dict:
    """Serialize only the metadata allowed by SPEC-001's local contract."""
    context = span.context
    scope = span.instrumentation_scope
    llm = (span.attributes or {}).get("aegis.mapping.version") == LLM_MAPPING_VERSION
    graph = (span.attributes or {}).get("aegis.mapping.version") == GRAPH_MAPPING_VERSION
    governance = (span.attributes or {}).get("aegis.mapping.version") in (GOVERNANCE_MAPPING_VERSION,'aegis.governance.v2')
    allowed = (ATTRIBUTE_KEYS - {"gen_ai.tool.name", "aegis.tool.permission"}) | LLM_STRING_KEYS | TOKEN_KEYS if llm else GRAPH_KEYS if graph else ATTRIBUTE_KEYS
    if governance: allowed = APPROVAL_GOVERNANCE_KEYS if (span.attributes or {}).get('aegis.mapping.version')=='aegis.governance.v2' else GOVERNANCE_KEYS
    return {
        "schema_version": "aegis.span.v5" if (span.attributes or {}).get("aegis.mapping.version")=="aegis.governance.v2" else "aegis.span.v4" if governance else "aegis.span.v3" if graph else "aegis.span.v2" if llm else "aegis.span.v1",
        "trace_id": f"{context.trace_id:032x}",
        "span_id": f"{context.span_id:016x}",
        "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
        "name": span.name,
        "kind": span.kind.name,
        "start_time_unix_nano": span.start_time,
        "end_time_unix_nano": span.end_time,
        "status": "ERROR" if span.status.status_code is StatusCode.ERROR else "UNSET",
        "resource": {
            key: value
            for key, value in span.resource.attributes.items()
            if key in RESOURCE_KEYS
        },
        "scope": {"name": scope.name, "version": scope.version},
        "attributes": {
            key: value for key, value in (span.attributes or {}).items() if key in allowed
        },
        "events": [
            {
                "name": "exception",
                "time_unix_nano": event.timestamp,
                "attributes": {"exception.type": event.attributes["exception.type"]},
            }
            for event in span.events
            if event.name == "exception" and "exception.type" in event.attributes
        ],
    }


class JsonlSpanExporter(SpanExporter):
    """Append batches to a local file; the processor isolates I/O failures."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        payload = "".join(
            json.dumps(span_record(span), ensure_ascii=False, allow_nan=False) + "\n"
            for span in spans
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        # There is no persistent file handle to close.
        pass
