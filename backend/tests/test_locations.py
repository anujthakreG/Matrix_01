"""Tests for geospatial locations endpoints and candidate withdrawal hotspots."""

from fastapi.testclient import TestClient
from backend.app.db.models import CaseModel


def test_list_locations_empty(client: TestClient):
    """Verify empty database returns empty list without error."""
    response = client.get("/api/v1/locations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_locations_filtering(client: TestClient, sample_case: CaseModel):
    """Verify location query filters for case_id, type, and risk threshold."""
    # Filter by case_id
    res_case = client.get(f"/api/v1/locations?case_id={sample_case.id}")
    assert res_case.status_code == 200
    data = res_case.json()
    assert len(data) == 2

    # Filter by candidate_withdrawal type
    res_type = client.get(f"/api/v1/locations?location_type=candidate_withdrawal")
    assert res_type.status_code == 200
    candidate_data = res_type.json()
    assert len(candidate_data) == 1
    assert candidate_data[0]["location_type"] == "candidate_withdrawal"
    assert candidate_data[0]["is_predicted"] is True
    assert "Predicted candidate location only" in candidate_data[0]["disclaimer"]

    # Filter by min_risk threshold
    res_risk = client.get(f"/api/v1/locations?min_risk=0.5")
    assert res_risk.status_code == 200
    assert len(res_risk.json()) == 1
    assert res_risk.json()[0]["risk_score"] >= 0.5
