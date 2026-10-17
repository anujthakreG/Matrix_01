"""Tests for ML prediction interface, honest availability handling, and persistence."""

from fastapi.testclient import TestClient
from backend.app.db.models import CaseModel
from backend.app.services.ml_service import MLPredictionService


def test_prediction_model_unavailable_returns_503(client: TestClient, sample_case: CaseModel):
    """
    Verify honest 503 response when Worker 2's ML model pipeline is not ready.
    Ensures the API never fabricates dummy predictions.
    """
    payload = {
        "case_id": sample_case.id,
        "complaint_narrative": "Victim reports suspicious withdrawal following phishing link.",
        "source_channel": "UPI",
    }
    response = client.post("/api/v1/predictions", json=payload)
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "ML_MODEL_UNAVAILABLE"
    assert "Worker 2 model pipeline is pending integration" in data["detail"]


def test_prediction_case_not_found(client: TestClient):
    """Verify 404 is returned when predicting for a non-existent case."""
    payload = {
        "case_id": 999999,
        "source_channel": "UPI",
    }
    response = client.post("/api/v1/predictions", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "RESOURCE_NOT_FOUND"


def test_prediction_success_with_predictor_hook(client: TestClient, sample_case: CaseModel):
    """
    Verify full prediction flow when Worker 2's interface is connected.
    Tests candidate location schema, mandatory investigative disclaimer, and database persistence.
    """

    def mock_worker2_predictor(features: dict) -> dict:
        return {
            "model_version": "v1.2-lightgbm-geo",
            "risk_score": 0.89,
            "risk_level": "high",
            "candidate_locations": [
                {
                    "name": "ATM Cluster #12 - Dadar Station",
                    "latitude": 19.0178,
                    "longitude": 72.8478,
                    "district": "Mumbai",
                    "state": "Maharashtra",
                    "confidence_score": 0.86,
                    "withdrawal_window_hours": 2.5,
                }
            ],
            "key_risk_factors": ["Rapid multi-hop UPI velocity", "Known mule hub coordinates"],
            "explanation": "High probability of immediate cash-out within 2.5 hours.",
        }

    # Register predictor hook conforming to ML interface contract
    MLPredictionService.register_predictor(mock_worker2_predictor)

    payload = {
        "case_id": sample_case.id,
        "reported_amount": 85000.0,
        "complaint_narrative": "Victim deceived via fake SMS link.",
        "source_channel": "UPI",
        "mule_accounts": ["ACC-MULE-2002", "ACC-MULE-3003"],
    }
    response = client.post("/api/v1/predictions", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["case_id"] == sample_case.id
    assert data["prediction_id"].startswith("PRED-")
    assert data["model_version"] == "v1.2-lightgbm-geo"
    assert data["risk_score"] == 0.89
    assert data["risk_level"] == "high"
    assert len(data["candidate_locations"]) == 1

    candidate = data["candidate_locations"][0]
    assert candidate["name"] == "ATM Cluster #12 - Dadar Station"
    assert candidate["confidence_score"] == 0.86
    # Verify mandatory disclaimer
    assert "Predicted candidate location only" in candidate["disclaimer"]
    assert "Predicted candidate location only" in data["disclaimer"]

    # Verify prediction retrieval by UUID
    pred_uuid = data["prediction_id"]
    get_res = client.get(f"/api/v1/predictions/{pred_uuid}")
    assert get_res.status_code == 200
    stored_data = get_res.json()
    assert stored_data["prediction_uuid"] == pred_uuid
    assert stored_data["risk_score"] == 0.89
    assert stored_data["model_version"] == "v1.2-lightgbm-geo"


def test_get_stored_prediction_not_found(client: TestClient):
    """Verify 404 for unknown prediction ID."""
    response = client.get("/api/v1/predictions/PRED-UNKNOWN123")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "RESOURCE_NOT_FOUND"
