import pytest
from fastapi.testclient import TestClient

from euroclaw.app import app
from euroclaw.settings import validate_settings


def test_health_endpoints_are_available():
    client = TestClient(app)

    readiness = client.get("/healthz/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ok"

    liveness = client.get("/healthz/liveness")
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "ok"


def test_validation_rejects_invalid_execution_mode(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "banana")
    with pytest.raises(ValueError, match="EXECUTION_MODE"):
        validate_settings()


def test_validation_requires_redis_in_distributed_mode(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "distributed")
    monkeypatch.setenv("REDIS_HOST", "")
    with pytest.raises(ValueError, match="REDIS_HOST"):
        validate_settings()


def test_defaults_are_valid_in_local_mode(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("SANDBOX_BACKEND", raising=False)
    settings = validate_settings()
    assert settings.execution_mode == "local"
