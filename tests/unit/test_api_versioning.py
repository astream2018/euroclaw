from fastapi.testclient import TestClient

from src.app import app


def test_openapi_includes_security_scheme():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    assert "securitySchemes" in schema["components"]
    assert schema["components"]["securitySchemes"]["BearerAuth"]["type"] == "http"
    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"

    assert schema["info"]["version"].startswith("v")
