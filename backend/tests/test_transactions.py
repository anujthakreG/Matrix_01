"""Tests for transaction financial networks and topology builder."""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.app.db.models import CaseModel


def test_transaction_network_with_flows(client: TestClient, sample_case: CaseModel):
    """Verify transaction network graph includes origin, mule nodes, ATM endpoints, and directed edges."""
    response = client.get(f"/api/v1/transactions/{sample_case.id}/network")
    assert response.status_code == 200
    data = response.json()

    assert data["case_id"] == sample_case.id
    assert data["case_number"] == sample_case.case_number
    assert data["total_flow_amount"] == 125000.0  # 85k + 40k
    assert data["suspicious_flow_amount"] == 125000.0
    assert data["total_nodes"] >= 3  # Victim account + 2 Mule accounts + ATM
    assert data["total_edges"] == 2

    # Check node identities
    node_ids = [n["id"] for n in data["nodes"]]
    assert "ACC-VICTIM-1001" in node_ids
    assert "ACC-MULE-2002" in node_ids
    assert "ACC-MULE-3003" in node_ids

    # Check node classifications
    victim_node = next(n for n in data["nodes"] if n["id"] == "ACC-VICTIM-1001")
    assert victim_node["node_type"] == "victim_account"

    mule_node = next(n for n in data["nodes"] if n["id"] == "ACC-MULE-2002")
    assert mule_node["node_type"] == "suspect_mule"
    assert mule_node["risk_score"] >= 0.85


def test_transaction_network_case_without_transactions(client: TestClient):
    """Verify case with no transactions returns clean empty topology without error."""
    # Create empty case
    case_payload = {
        "title": "Case without transactions",
        "description": "Initial report pending transaction statement extraction.",
        "category": "identity_theft",
        "status": "open",
        "priority": "low",
        "reported_amount": 0.0,
        "currency": "INR",
        "victim_state": "Delhi",
        "victim_district": "Central Delhi",
        "incident_date": datetime.now(timezone.utc).isoformat(),
    }
    create_res = client.post("/api/v1/cases", json=case_payload)
    case_id = create_res.json()["id"]

    response = client.get(f"/api/v1/transactions/{case_id}/network")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["total_flow_amount"] == 0.0
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0


def test_transaction_network_not_found(client: TestClient):
    """Verify 404 returned for unknown case ID."""
    response = client.get("/api/v1/transactions/999999/network")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "RESOURCE_NOT_FOUND"
