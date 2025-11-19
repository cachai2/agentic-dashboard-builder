"""OpenTelemetry helpers for the CSV Profiler service."""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:  # Optional OTLP exporter if available
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
except ImportError:  # pragma: no cover - importer guard for minimal environments
    OTLPSpanExporter = None  # type: ignore[assignment]

SERVICE_NAME = "csv-profiler-agent"


@lru_cache(maxsize=1)
def _create_tracer_provider() -> TracerProvider:
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and OTLPSpanExporter is not None:
        insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def configure_tracing(app: FastAPI) -> None:
    """Instrument the FastAPI app once per process."""

    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(_create_tracer_provider())

    if getattr(app.state, "_otel_instrumented", False):
        return
    FastAPIInstrumentor.instrument_app(app)
    app.state._otel_instrumented = True


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(SERVICE_NAME)
