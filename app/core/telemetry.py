from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings


def otlp_traces_endpoint(settings: Settings) -> str | None:
    """Full OTLP/HTTP traces URL for the configured collector, or None if unset.
    (The exporter takes the full URL when passed explicitly, so /v1/traces is
    appended here rather than by the exporter.)"""
    if not settings.otel_exporter_otlp_endpoint:
        return None
    return settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"


def build_tracer_provider(settings: Settings) -> TracerProvider:
    """
    A TracerProvider tagged with this service's identity. Spans are only exported
    when `otel_exporter_otlp_endpoint` is set — otherwise they're created and
    dropped, so tests and CI never need a collector running.
    """
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)
    endpoint = otlp_traces_endpoint(settings)
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return provider


def setup_telemetry(app: FastAPI, engine: AsyncEngine, settings: Settings) -> TracerProvider:
    """
    Trace every HTTP request, with each SQL query the request runs as a child span.
    The provider is passed explicitly rather than set globally, so tests can attach
    their own span processor to the returned provider.
    """
    provider = build_tracer_provider(settings)
    # exclude_spans drops the per-chunk ASGI receive/send spans, which add noise
    # to every trace without saying anything about the request.
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, exclude_spans=["receive", "send"]
    )
    # SQLAlchemy's event hooks live on the sync engine underneath the async one.
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
    return provider
