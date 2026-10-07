"""Test service health check endpoint."""

from fastapi.testclient import TestClient


def test_health_check_returns_ok(client: TestClient) -> None:
    """Verify that /health returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
