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


def test_incidents_compatibility_endpoint(client: TestClient):
    """Verify /api/incidents compatibility endpoint returns envelope with records list."""
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert isinstance(data["records"], list)
    assert "total" in data


def test_dashboard_static_mount(client: TestClient):
    """Verify /dashboard serves the frontend dashboard index.html."""
    response = client.get("/dashboard")
    assert response.status_code in [200, 307]
    if response.status_code == 307:
        response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "CYBER-TRAC" in response.text or "MATRIX" in response.text
