import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    redis_host: str
    otel_endpoint: str
    execution_mode: str
    allowed_workspaces: tuple[str, ...]


def validate_settings() -> Settings:
    redis_host = os.getenv("REDIS_HOST", "").strip()
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    execution_mode = os.getenv("EXECUTION_MODE", "local").strip().lower()
    allowed_workspaces_raw = os.getenv("ALLOWED_WORKSPACES", "").strip()

    if not redis_host:
        raise ValueError("REDIS_HOST must be configured")
    if not otel_endpoint:
        raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT must be configured")
    if execution_mode not in {"local", "distributed"}:
        raise ValueError("EXECUTION_MODE must be 'local' or 'distributed'")

    allowed_workspaces = tuple(
        workspace.strip()
        for workspace in allowed_workspaces_raw.split(",")
        if workspace.strip()
    )

    return Settings(
        redis_host=redis_host,
        otel_endpoint=otel_endpoint,
        execution_mode=execution_mode,
        allowed_workspaces=allowed_workspaces,
    )
