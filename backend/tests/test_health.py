"""Tests for health and root discovery endpoints."""

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Verify root endpoint returns API metadata and documentation links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["api_v1"] == "/api/v1"
    assert data["docs"] == "/docs"


def test_health_check_endpoint(client: TestClient):
    """Verify health endpoint reports DB connectivity and ML status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database"] == "connected"
    assert "ml_service" in data
    assert "timestamp" in data
