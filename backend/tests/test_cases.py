"""Tests for cybercrime cases endpoints, pagination, and filtering."""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from backend.app.db.models import CaseModel


def test_list_cases_empty(client: TestClient):
    """Verify empty case list produces valid pagination envelope."""
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 0


def test_create_and_retrieve_case(client: TestClient):
    """Verify creating a case and reading it back."""
    payload = {
        "title": "Unauthorized SIM Swap Transfer",
        "description": "Suspect conducted unauthorized SIM swap and drained account via netbanking.",
        "category": "sim_swap",
        "status": "open",
        "priority": "critical",
        "reported_amount": 250000.0,
        "currency": "INR",
        "victim_state": "Karnataka",
        "victim_district": "Bengaluru Urban",
        "incident_date": datetime.now(timezone.utc).isoformat(),
    }
    create_res = client.post("/api/v1/cases", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["title"] == payload["title"]
    assert created_data["case_number"].startswith("CASE-")
    case_id = created_data["id"]

    # Retrieve single case
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    detail_data = get_res.json()
    assert detail_data["id"] == case_id
    assert detail_data["priority"] == "critical"
    assert detail_data["victim_state"] == "Karnataka"


def test_get_case_details_with_relations(client: TestClient, sample_case: CaseModel):
    """Verify detailed case endpoint returns nested transactions and locations."""
    response = client.get(f"/api/v1/cases/{sample_case.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_case.id
    assert len(data["transactions"]) == 2
    assert len(data["locations"]) == 2
    assert data["transactions"][0]["sender_account"] == "ACC-VICTIM-1001"


def test_get_case_not_found(client: TestClient):
    """Verify 404 response on non-existent case ID."""
    response = client.get("/api/v1/cases/999999")
    assert response.status_code == 404
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "RESOURCE_NOT_FOUND"
    assert "999999" in data["detail"]


def test_cases_filtering_and_pagination(client: TestClient, sample_case: CaseModel):
    """Verify filtering by status, priority, category, and search keyword."""
    # Filter by category
    res_cat = client.get("/api/v1/cases?category=phishing")
    assert res_cat.status_code == 200
    assert res_cat.json()["total"] >= 1

    # Filter by mismatched category
    res_none = client.get("/api/v1/cases?category=non_existent_category")
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0

    # Search keyword
    res_search = client.get("/api/v1/cases?search=Mumbai")
    assert res_search.status_code == 200
    assert res_search.json()["total"] >= 1

    # Pagination bounds
    res_page = client.get("/api/v1/cases?page=1&page_size=1")
    assert res_page.status_code == 200
    assert len(res_page.json()["items"]) == 1


def test_cases_date_range_filtering(client: TestClient, sample_case: CaseModel):
    """Verify filtering by incident date range."""
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(hours=10)).isoformat()
    to_date = (now + timedelta(hours=1)).isoformat()

    res = client.get("/api/v1/cases", params={"date_from": from_date, "date_to": to_date})
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # Future date filter where no cases exist
    future_date = (now + timedelta(days=30)).isoformat()
    res_future = client.get("/api/v1/cases", params={"date_from": future_date})
    assert res_future.status_code == 200
    assert res_future.json()["total"] == 0


