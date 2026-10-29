from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import AsyncSessionLocal, engine
from app.core.telemetry import otlp_traces_endpoint
from app.main import app, tracer_provider

# One exporter attached to the app's real provider for the whole module — the SDK
# has no way to detach a span processor, so per-test attachment would pile them up.
_exporter = InMemorySpanExporter()
tracer_provider.add_span_processor(SimpleSpanProcessor(_exporter))


@pytest.fixture
def spans() -> Generator[InMemorySpanExporter]:
    _exporter.clear()
    yield _exporter
    _exporter.clear()


async def test_request_produces_server_span(spans: InMemorySpanExporter) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200

    server_spans = [s for s in spans.get_finished_spans() if s.kind == SpanKind.SERVER]
    assert len(server_spans) == 1
    span = server_spans[0]
    assert span.attributes is not None
    assert span.attributes["http.route"] == "/health"
    assert span.attributes["http.status_code"] == 200
    assert span.resource.attributes["service.name"] == "dzo-backend"


async def test_query_on_app_engine_produces_db_span(spans: InMemorySpanExporter) -> None:
    # Uses the app's own pooled engine (not the tests' NullPool one) since that's
    # the engine setup_telemetry instruments; disposed afterwards so no pooled
    # connection outlives this test's event loop.
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    finally:
        await engine.dispose()

    db_spans = [
        s
        for s in spans.get_finished_spans()
        if s.attributes and s.attributes.get("db.system") == "postgresql"
    ]
    assert any(s.attributes and s.attributes.get("db.statement") == "SELECT 1" for s in db_spans)


def test_otlp_endpoint_unset_disables_export() -> None:
    assert otlp_traces_endpoint(Settings(otel_exporter_otlp_endpoint=None)) is None


def test_otlp_endpoint_appends_traces_path() -> None:
    settings = Settings(otel_exporter_otlp_endpoint="http://localhost:4318/")
    assert otlp_traces_endpoint(settings) == "http://localhost:4318/v1/traces"
