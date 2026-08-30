from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def lead_payload(**changes):
    value = {"customer_id": "CUST-000001", "vehicle_id": "VEH-000001", "source": "Voice Agent"}
    value.update(changes)
    return value


def appointment_payload(**changes):
    value = {"customer_id": "CUST-000001", "vehicle_id": "VEH-000001",
             "starts_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()}
    value.update(changes)
    return value


def finance_payload(**changes):
    value = {"vehicle_price": "40000", "down_payment": "5000", "trade_in_value": "2000",
             "credit_score": 720, "term_months": 60}
    value.update(changes)
    return value


def test_create_lead_scores_deterministically():
    response = client.post("/api/v1/leads", json=lead_payload())
    assert response.status_code == 201
    assert response.json()["score"] == 70


def test_create_lead_without_vehicle():
    response = client.post("/api/v1/leads", json=lead_payload(vehicle_id=None))
    assert response.status_code == 201
    assert response.json()["score"] == 63


def test_create_lead_rejects_unknown_customer():
    assert client.post("/api/v1/leads", json=lead_payload(customer_id="CUST-999999")).status_code == 404


def test_create_lead_rejects_unknown_vehicle():
    assert client.post("/api/v1/leads", json=lead_payload(vehicle_id="VEH-999999")).status_code == 404


def test_lead_idempotency_replays_same_response():
    headers = {"Idempotency-Key": "lead-test-replay"}
    first = client.post("/api/v1/leads", json=lead_payload(), headers=headers)
    replay = client.post("/api/v1/leads", json=lead_payload(), headers=headers)
    assert first.json() == replay.json()
    assert replay.status_code == 200 and replay.headers["Idempotent-Replayed"] == "true"


def test_lead_idempotency_rejects_payload_change():
    headers = {"Idempotency-Key": "lead-test-conflict"}
    client.post("/api/v1/leads", json=lead_payload(), headers=headers)
    assert client.post("/api/v1/leads", json=lead_payload(vehicle_id=None), headers=headers).status_code == 409


def test_update_lead():
    lead = client.post("/api/v1/leads", json=lead_payload()).json()
    response = client.patch(f"/api/v1/leads/{lead['lead_id']}", json={"status": "Qualified", "notes": "Ready"})
    assert response.status_code == 200 and response.json()["status"] == "Qualified"


def test_update_unknown_lead():
    assert client.patch("/api/v1/leads/LEAD-999999", json={"status": "Lost"}).status_code == 404


def test_book_test_drive():
    response = client.post("/api/v1/appointments", json=appointment_payload())
    assert response.status_code == 201 and response.json()["status"] == "Scheduled"


def test_booking_rejects_past_time():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.post("/api/v1/appointments", json=appointment_payload(starts_at=past)).status_code == 422


def test_booking_rejects_unavailable_test_drive_vehicle():
    assert client.post("/api/v1/appointments", json=appointment_payload(vehicle_id="VEH-000002")).status_code == 409


def test_booking_idempotency():
    headers = {"Idempotency-Key": "booking-test-replay"}
    payload = appointment_payload()
    first = client.post("/api/v1/appointments", json=payload, headers=headers)
    second = client.post("/api/v1/appointments", json=payload, headers=headers)
    assert first.json() == second.json() and second.status_code == 200


def test_customer_history_aggregates_records():
    response = client.get("/api/v1/customers/CUST-000001/history")
    assert response.status_code == 200
    assert response.json()["customer"]["customer_id"] == "CUST-000001"
    assert set(response.json()) == {"customer", "leads", "appointments", "trade_ins"}


def test_customer_history_unknown_customer():
    assert client.get("/api/v1/customers/CUST-999999/history").status_code == 404


def test_financing_estimate_is_deterministic():
    first = client.post("/api/v1/financing/estimate", json=finance_payload())
    second = client.post("/api/v1/financing/estimate", json=finance_payload())
    assert first.status_code == 200 and first.json() == second.json()
    assert first.json()["credit_tier"] == "Good"


def test_financing_better_credit_has_lower_payment():
    excellent = client.post("/api/v1/financing/estimate", json=finance_payload(credit_score=780)).json()
    fair = client.post("/api/v1/financing/estimate", json=finance_payload(credit_score=620)).json()
    assert float(excellent["estimated_monthly_payment"]) < float(fair["estimated_monthly_payment"])


def test_financing_rejects_invalid_credit_score():
    assert client.post("/api/v1/financing/estimate", json=finance_payload(credit_score=200)).status_code == 422


def test_every_response_has_request_id():
    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})
    assert response.headers["X-Request-ID"] == "test-request-123"
