"""Shared OpenTelemetry setup.

Tracing is ON by default (the framework's audit story depends on it). It
degrades gracefully: a missing or unreachable collector never blocks startup
or requests. Set ``OTEL_SDK_DISABLED=true`` to opt out entirely.
"""

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from euroclaw.settings import current_settings

logger = logging.getLogger("euroclaw.tracing")

_CONFIGURED = False


def configure_tracing(service_name: str = "euroclaw") -> None:
    """Idempotently install a tracer provider + OTLP exporter if configured."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    settings = current_settings()
    if settings.otel_disabled:
        logger.info("OpenTelemetry disabled via OTEL_SDK_DISABLED; skipping exporter")
        return

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        try:
            trace.set_tracer_provider(provider)
        except Exception:  # noqa: BLE001 - provider already set by another module
            provider = trace.get_tracer_provider()

    endpoint = settings.otel_endpoint
    if not endpoint:
        logger.info("No OTLP endpoint configured; traces are local-only")
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        logger.info("OTLP exporter attached to %s", endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telemetry exporter unavailable; continuing without remote traces: %s",
            exc,
        )


def get_tracer(name: str):
    return trace.get_tracer(name)
