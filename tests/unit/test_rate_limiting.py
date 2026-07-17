import os

from fastapi.testclient import TestClient

os.environ["RATE_LIMIT_REQUESTS"] = "2"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"

from euroclaw import state  # noqa: E402
from euroclaw.app import app  # noqa: E402


def test_rate_limit_enforces_threshold():
    state.reset_for_tests()
    client = TestClient(app)

    payload = {"task_id": "1", "approved": True}
    first = client.post("/api/v1/hitl/callback", json=payload)
    second = client.post("/api/v1/hitl/callback", json=payload)
    third = client.post("/api/v1/hitl/callback", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
