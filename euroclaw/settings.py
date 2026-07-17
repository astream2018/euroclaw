"""Centralized, validated configuration for EuroClaw.

All runtime configuration is sourced from environment variables and exposed as
an immutable :class:`Settings` object. ``get_settings(strict=True)`` (aliased as
``validate_settings``) raises on misconfiguration so readiness probes and
startup can fail closed instead of silently running on defaults.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    # Core infra
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_use_tls: bool = False

    # Telemetry
    otel_endpoint: str = ""
    otel_disabled: bool = False

    # Execution
    execution_mode: str = "local"  # "local" | "distributed"
    sandbox_backend: str = "subprocess"  # "subprocess" | "firecracker"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # LLM
    llm_endpoint: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"

    # Files / workspaces
    allowed_workspaces: tuple[str, ...] = ()

    # API
    api_version: str = "v1"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    cors_allow_origins: tuple[str, ...] = ("http://localhost:3000",)

    # Identity
    oidc_issuer_url: str = "http://localhost:8080/realms/euroclaw"
    oidc_audience: str = "euroclaw-api"
    jwks_cache_ttl_seconds: int = 600

    # Orchestration limits (bound the agent loop)
    max_tool_iterations: int = 5
    max_agent_turns: int = 6
    hitl_timeout_seconds: int = 300

    # Audit
    audit_dir: str = "audit_logs"

    # RBAC policy override (tool -> comma-separated roles), parsed from env
    rbac_policy: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _coerce_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _parse_rbac_policy(raw: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    # Format: "tool_a:role1|role2;tool_b:role3"
    entries: list[tuple[str, tuple[str, ...]]] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        tool, roles = chunk.split(":", 1)
        entries.append(
            (tool.strip(), tuple(r.strip() for r in roles.split("|") if r.strip()))
        )
    return tuple(entries)


def get_settings(strict: bool = False) -> Settings:
    execution_mode = os.getenv("EXECUTION_MODE", "local").strip().lower()
    sandbox_backend = os.getenv("SANDBOX_BACKEND", "subprocess").strip().lower()
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    origins = _csv(os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000"))

    if strict:
        if execution_mode not in {"local", "distributed"}:
            raise ValueError("EXECUTION_MODE must be 'local' or 'distributed'")
        if sandbox_backend not in {"subprocess", "firecracker"}:
            raise ValueError("SANDBOX_BACKEND must be 'subprocess' or 'firecracker'")
        if execution_mode == "distributed" and not os.getenv("REDIS_HOST", "").strip():
            raise ValueError("REDIS_HOST must be configured for distributed mode")

    return Settings(
        redis_host=os.getenv("REDIS_HOST", "localhost").strip() or "localhost",
        redis_port=_coerce_int("REDIS_PORT", 6379),
        redis_password=os.getenv("REDIS_PASSWORD", ""),
        redis_use_tls=_bool("REDIS_USE_TLS", False),
        otel_endpoint=otel_endpoint,
        otel_disabled=_bool("OTEL_SDK_DISABLED", False),
        execution_mode=execution_mode,
        sandbox_backend=sandbox_backend,
        celery_broker_url=os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/0"
        ).strip(),
        celery_result_backend=os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
        ).strip(),
        llm_endpoint=os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:11434").strip(),
        llm_model=os.getenv("EUROCLAW_MODEL", "qwen2.5:7b").strip(),
        allowed_workspaces=_csv(os.getenv("ALLOWED_WORKSPACES", "")),
        api_version=os.getenv("API_VERSION", "v1").strip() or "v1",
        rate_limit_requests=_coerce_int("RATE_LIMIT_REQUESTS", 60),
        rate_limit_window_seconds=_coerce_int("RATE_LIMIT_WINDOW_SECONDS", 60),
        cors_allow_origins=origins or ("http://localhost:3000",),
        oidc_issuer_url=os.getenv(
            "OIDC_ISSUER_URL", "http://localhost:8080/realms/euroclaw"
        ).strip()
        or "http://localhost:8080/realms/euroclaw",
        oidc_audience=os.getenv("OIDC_AUDIENCE", "euroclaw-api").strip()
        or "euroclaw-api",
        jwks_cache_ttl_seconds=_coerce_int("JWKS_CACHE_TTL_SECONDS", 600),
        max_tool_iterations=_coerce_int("MAX_TOOL_ITERATIONS", 5),
        max_agent_turns=_coerce_int("MAX_AGENT_TURNS", 6),
        hitl_timeout_seconds=_coerce_int("HITL_TIMEOUT_SECONDS", 300),
        audit_dir=os.getenv("AUDIT_DIR", "audit_logs").strip() or "audit_logs",
        rbac_policy=_parse_rbac_policy(os.getenv("RBAC_POLICY", "")),
    )


@lru_cache(maxsize=1)
def _cached_settings() -> Settings:
    return get_settings(strict=False)


def current_settings() -> Settings:
    """Process-wide cached settings (non-strict)."""
    return _cached_settings()


def validate_settings() -> Settings:
    """Strict validation used by readiness probes and startup."""
    return get_settings(strict=True)
