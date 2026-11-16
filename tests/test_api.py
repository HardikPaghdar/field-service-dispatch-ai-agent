from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_seed_data():
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/technicians").json()) >= 3
    assert len(client.get("/requests").json()) >= 2


def test_safety_request_is_critical():
    result = client.post("/requests/assess", json={"request_id": "SR-1003"})
    assert result.status_code == 200
    assert result.json()["priority"] == "critical"
    assert result.json()["human_review_required"] is True


def test_proposal_requires_approval_and_has_eligible_match():
    result = client.post("/dispatch/proposals", json={
        "request_id": "SR-1001", "preferred_date": "2026-11-17", "duration_minutes": 60
    })
    assert result.status_code == 200
    proposal = result.json()
    assert proposal["status"] == "needs_manager_approval"
    assert proposal["selected_technician"]["technician_id"] == "T-102"
    approved = client.post(f"/dispatch/proposals/{proposal['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_unknown_request_returns_404():
    assert client.post("/requests/assess", json={"request_id": "missing"}).status_code == 404


def test_cannot_approve_without_match():
    result = client.post("/dispatch/proposals", json={
        "request_id": "SR-1003", "preferred_date": "2026-11-17", "duration_minutes": 60
    })
    proposal = result.json()
    assert proposal["selected_technician"] is None
    assert client.post(f"/dispatch/proposals/{proposal['id']}/approve").status_code == 409
