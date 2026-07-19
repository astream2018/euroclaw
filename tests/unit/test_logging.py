from fastapi.testclient import TestClient

from euroclaw.app import app


def test_request_id_header_is_echoed_back():
    client = TestClient(app)

    response = client.get(
        "/healthz/liveness",
        headers={"X-Request-ID": "req-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
