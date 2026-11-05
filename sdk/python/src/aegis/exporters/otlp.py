"""Opt-in official OTLP/HTTP transport."""

from collections.abc import Mapping
from urllib.parse import urlsplit


def build_otlp_exporter(endpoint: str, timeout_millis: int, headers: Mapping[str, str] | None):
    if not isinstance(endpoint, str):
        raise ValueError("invalid OTLP endpoint")
    try:
        target = urlsplit(endpoint)
        port = target.port
    except (TypeError, ValueError):
        raise ValueError("invalid OTLP endpoint") from None
    if (
        target.scheme not in ("http", "https") or not target.hostname
        or target.username is not None or target.password is not None
        or target.query or target.fragment or not target.path.endswith("/v1/traces")
        or port == 0
    ):
        raise ValueError("endpoint must be a full HTTP /v1/traces URL without credentials, query or fragment")
    if type(timeout_millis) is not int or not 1 <= timeout_millis <= 30000:
        raise ValueError("export_timeout_millis must be between 1 and 30000")
    if headers is not None and not isinstance(headers, Mapping):
        raise ValueError("headers must be a string mapping")
    if headers is not None and any(
        not isinstance(key, str) or not isinstance(value, str)
        or "\r" in key + value or "\n" in key + value
        for key, value in headers.items()
    ):
        raise ValueError("invalid exporter headers")
    try:
        from opentelemetry.exporter.otlp.proto.http import Compression
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        raise RuntimeError("install aegis-runtime-sdk[otlp] to enable network export") from None
    return OTLPSpanExporter(
        endpoint=endpoint, timeout=timeout_millis / 1000,
        headers=dict(headers or {}), compression=Compression.NoCompression,
    )
