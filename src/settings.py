import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    redis_host: str = "localhost"
    otel_endpoint: str = ""
    execution_mode: str = "local"
    allowed_workspaces: tuple[str, ...] = ()
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    api_version: str = "v1"
    oidc_issuer_url: str = "http://localhost:8080/realms/euroclaw"
    oidc_audience: str = "euroclaw-api"


def _parse_allowed_workspaces(value: str) -> tuple[str, ...]:
    return tuple(
        workspace.strip() for workspace in value.split(",") if workspace.strip()
    )


def _coerce_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def get_settings(strict: bool = False) -> Settings:
    redis_host = os.getenv("REDIS_HOST", "").strip()
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    execution_mode = os.getenv("EXECUTION_MODE", "local").strip().lower()
    allowed_workspaces = _parse_allowed_workspaces(os.getenv("ALLOWED_WORKSPACES", ""))
    rate_limit_requests = _coerce_int("RATE_LIMIT_REQUESTS", 60)
    rate_limit_window_seconds = _coerce_int("RATE_LIMIT_WINDOW_SECONDS", 60)

    if strict:
        if not redis_host:
            raise ValueError("REDIS_HOST must be configured")
        if not otel_endpoint:
            raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT must be configured")
        if execution_mode not in {"local", "distributed"}:
            raise ValueError("EXECUTION_MODE must be 'local' or 'distributed'")

    return Settings(
        redis_host=redis_host or "localhost",
        otel_endpoint=otel_endpoint,
        execution_mode=execution_mode,
        allowed_workspaces=allowed_workspaces,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
        api_version=os.getenv("API_VERSION", "v1").strip() or "v1",
        oidc_issuer_url=os.getenv(
            "OIDC_ISSUER_URL", "http://localhost:8080/realms/euroclaw"
        ).strip()
        or "http://localhost:8080/realms/euroclaw",
        oidc_audience=os.getenv("OIDC_AUDIENCE", "euroclaw-api").strip()
        or "euroclaw-api",
    )


def validate_settings() -> Settings:
    return get_settings(strict=True)
