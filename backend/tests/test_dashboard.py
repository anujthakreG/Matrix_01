"""Tests for dashboard summary aggregation."""

from fastapi.testclient import TestClient
from backend.app.db.models import CaseModel


def test_dashboard_summary_empty_database(client: TestClient):
    """Verify empty database produces zeroed metrics without fabricating data."""
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cases"] == 0
    assert data["total_cases_open"] == 0
    assert data["total_defrauded_amount"] == 0.0
    assert data["total_suspect_accounts"] == 0
    assert data["total_transactions_flagged"] == 0
    assert data["total_candidate_withdrawal_locations"] == 0
    assert data["cases_by_category"] == {}
    assert data["cases_by_priority"] == {}
    assert "last_updated" in data


def test_dashboard_summary_with_data(client: TestClient, sample_case: CaseModel):
    """Verify aggregated metrics accurately reflect database records."""
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cases"] >= 1
    assert data["total_cases_open"] >= 1
    assert data["high_risk_cases_count"] >= 1
    assert data["total_defrauded_amount"] >= 85000.0
    assert data["total_suspect_accounts"] == 2  # ACC-MULE-2002 and ACC-MULE-3003
    assert data["total_transactions_flagged"] == 2
    assert data["total_candidate_withdrawal_locations"] >= 1
    assert "phishing" in data["cases_by_category"]
    assert "high" in data["cases_by_priority"]
