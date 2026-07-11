import os
import importlib
import src.app as app_module
from fastapi.testclient import TestClient


os.environ.setdefault("RATE_LIMIT_REQUESTS", "2")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")


def test_rate_limit_enforces_threshold():
    reloaded_module = importlib.reload(app_module)
    client = TestClient(reloaded_module.app)

    first = client.post(
        "/api/v1/hitl/callback",
        json={"task_id": "1", "approved": True},
    )
    second = client.post(
        "/api/v1/hitl/callback",
        json={"task_id": "1", "approved": True},
    )
    third = client.post(
        "/api/v1/hitl/callback",
        json={"task_id": "1", "approved": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
