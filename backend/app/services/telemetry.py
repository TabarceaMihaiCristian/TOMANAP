"""Vendor-neutral OpenTelemetry traces and metrics exported over OTLP/HTTP."""

from typing import Any

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings


class Telemetry:
    """Own instrumentation providers so each application can shut down cleanly."""

    def __init__(
        self,
        settings: Settings,
        *,
        span_exporter: SpanExporter | None = None,
        metric_reader: MetricReader | None = None,
    ) -> None:
        self.settings = settings
        self._app: FastAPI | None = None
        self._engine: Any | None = None
        self.tracer_provider: TracerProvider | None = None
        self.meter_provider: MeterProvider | None = None
        if not settings.telemetry_enabled:
            return

        endpoint = settings.telemetry_otlp_endpoint
        if endpoint is None:
            raise ValueError("An OTLP endpoint is required when telemetry is enabled")
        resource = Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": settings.app_version,
                "deployment.environment.name": settings.environment.value,
            }
        )
        resolved_span_exporter = span_exporter or OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces"
        )
        resolved_metric_reader = metric_reader or PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
            export_interval_millis=settings.telemetry_export_interval_seconds * 1000,
        )
        self.tracer_provider = TracerProvider(resource=resource)
        self.tracer_provider.add_span_processor(
            BatchSpanProcessor(resolved_span_exporter)
        )
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[resolved_metric_reader],
        )

    def instrument(self, app: FastAPI, engine: AsyncEngine) -> None:
        """Instrument inbound HTTP/WebSocket work and SQLAlchemy operations."""
        if self.tracer_provider is None or self.meter_provider is None:
            return
        self._app = app
        self._engine = engine.sync_engine
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
            exclude_spans=["receive", "send"],
        )
        SQLAlchemyInstrumentor().instrument(
            engine=self._engine,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
        )

    def force_flush(self) -> None:
        """Flush providers for tests and controlled process shutdown."""
        if self.tracer_provider is not None:
            self.tracer_provider.force_flush()
        if self.meter_provider is not None:
            self.meter_provider.force_flush()

    def shutdown(self) -> None:
        """Detach instrumentation and flush exporter-owned resources."""
        if self._app is not None:
            FastAPIInstrumentor.uninstrument_app(self._app)
            self._app = None
        if self._engine is not None:
            SQLAlchemyInstrumentor().uninstrument(engine=self._engine)
            self._engine = None
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()
        if self.meter_provider is not None:
            self.meter_provider.shutdown()
