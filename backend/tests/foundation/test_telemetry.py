"""Tests for vendor-neutral HTTP, database, trace, and metric telemetry."""

from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.core.config import Settings
from app.main import create_app
from app.services.telemetry import Telemetry


def test_fastapi_requests_emit_traces_and_metrics(settings: Settings) -> None:
    telemetry_settings = settings.model_copy(
        update={
            "telemetry_enabled": True,
            "telemetry_otlp_endpoint": "http://localhost:4318",
        }
    )
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    telemetry = Telemetry(
        telemetry_settings,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )

    with TestClient(create_app(telemetry_settings, telemetry=telemetry)) as client:
        assert client.get("/health").status_code == 200
        telemetry.force_flush()
        metrics = metric_reader.get_metrics_data()

    spans = span_exporter.get_finished_spans()
    assert any(span.attributes.get("http.route") == "/health" for span in spans)
    assert metrics is not None
    metric_names = {
        metric.name
        for resource_metric in metrics.resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
    }
    assert "http.server.duration" in metric_names
