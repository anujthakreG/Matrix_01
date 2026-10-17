"""Tests for CORS middleware behavior and standard validation error handling."""

from fastapi.testclient import TestClient


def test_cors_preflight_allowed_origin(client: TestClient):
    """Verify CORS headers for configured frontend origins."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_disallowed_origin(client: TestClient):
    """Verify unapproved origin is rejected in CORS headers."""
    headers = {
        "Origin": "http://malicious-external-site.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") != "http://malicious-external-site.com"


def test_request_validation_error_format(client: TestClient):
    """Verify 422 validation errors conform to standardized error envelope."""
    invalid_payload = {
        # Missing required fields like title, category, victim_state, etc.
        "reported_amount": "not_a_number",
    }
    response = client.post("/api/v1/cases", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "errors" in data["meta"]
    assert "timestamp" in data
