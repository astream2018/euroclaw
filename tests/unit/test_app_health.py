import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.config import validate_settings


def test_health_endpoints_are_available():
    client = TestClient(app)

    readiness = client.get("/healthz/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ok"

    liveness = client.get("/healthz/liveness")
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "ok"


def test_config_validation_rejects_blank_required_values(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    with pytest.raises(ValueError, match="REDIS_HOST"):
        validate_settings()
