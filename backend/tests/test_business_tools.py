from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.routes import business_tools as business_tool_routes
from app.routes.business_tools import get_business_client
from app.schemas.business_tools import (
    BookingRequest,
    BookingResponse,
    FinancingEstimateRequest,
    LeadResponse,
    LeadUpsertRequest,
)
from app.services.business_tools import (
    BusinessConflictError,
    BusinessNotFoundError,
    BusinessToolError,
    create_or_update_lead,
    create_test_drive,
    estimate_financing,
    score_lead,
)


class BookingQuery:
    def __init__(self, result, client):
        self.result = result
        self.client = client

    def select(self, *_args, **_kwargs): return self
    def eq(self, *_args, **_kwargs): return self
    @property
    def not_(self): return self
    def in_(self, *_args, **_kwargs): return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args, **_kwargs): return self
    def update(self, payload):
        self.client.update_payloads.append(payload)
        return self
    def insert(self, payload):
        self.client.insert_payloads.append(payload)
        return self
    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return SimpleNamespace(data=self.result)


class BookingClient:
    def __init__(self, results):
        self.results = iter(results)
        self.tables = []
        self.insert_payloads = []
        self.update_payloads = []

    def table(self, name):
        self.tables.append(name)
        return BookingQuery(next(self.results), self)


def booking_request(**changes):
    values = {
        "lead_id": "LEAD-000001",
        "customer_id": "CUST-000001",
        "vehicle_id": "VEH-000001",
        "salesperson_id": "SP-001",
        "appointment_date": "2026-08-26",
        "appointment_time": "09:00",
    }
    values.update(changes)
    return BookingRequest(**values)


def booking_success_results():
    return [
        [],
        [{"lead_id": "LEAD-000001", "customer_id": "CUST-000001"}],
        [{"customer_id": "CUST-000001"}],
        [{"vehicle_status": "Available", "test_drive_available": True}],
        [{"working_days": ["Wednesday"], "shift_start": "09:00:00", "shift_end": "17:00:00", "active": True}],
        [],
        [],
        [{"appointment_id": "APT-000001", "lead_id": "LEAD-000001", "status": "Confirmed"}],
    ]


def lead_request(**changes):
    values = dict(customer_id="CUST-000001", budget=30000, vehicle_interest="VEH-000001",
                  purchase_timeline="Within 7 Days", financing_needed=True, trade_in=True,
                  assigned_salesperson="SP-001")
    values.update(changes)
    return LeadUpsertRequest(**values)


def lead_create_results():
    return [
        [{"customer_id": "CUST-000001"}],
        [{"vehicle_id": "VEH-000001"}],
        [{"salesperson_id": "SP-001", "active": True}],
        [],
        [],
        [{
            "lead_id": "LEAD-000001", "lead_status": "New",
            "lead_score": 88, "lead_temperature": "Hot",
        }],
    ]


def test_lead_scoring_is_deterministic_and_bucketed():
    hot_score, hot = score_lead(lead_request())
    cold_score, cold = score_lead(lead_request(
        vehicle_interest=None, purchase_timeline="Researching", financing_needed=False,
        trade_in=False, budget=3000,
    ))
    assert hot_score >= 70 and hot == "Hot"
    assert cold_score <= 39 and cold == "Cold"


def test_lead_scoring_classifies_exact_cold_warm_and_hot_boundaries():
    cold_score, cold = score_lead(lead_request(
        vehicle_interest=None, purchase_timeline="1-3 Months",
        financing_needed=False, trade_in=False, budget=90_000,
    ))
    warm_score, warm = score_lead(lead_request(
        vehicle_interest=None, purchase_timeline="Within 30 Days",
        financing_needed=False, trade_in=False, budget=3_000,
    ))
    hot_score, hot = score_lead(lead_request(
        vehicle_interest="VEH-000001", purchase_timeline="Within 7 Days",
        financing_needed=False, trade_in=False, budget=3_000,
    ))

    assert (cold_score, cold) == (39, "Cold")
    assert (warm_score, warm) == (40, "Warm")
    assert (hot_score, hot) == (70, "Hot")


def test_lead_create_persists_backend_calculated_score_and_temperature():
    client = BookingClient(lead_create_results())

    result = create_or_update_lead(lead_request(), client)

    assert result.created is True
    assert result.lead["lead_id"] == "LEAD-000001"
    assert client.tables == [
        "customers", "vehicles", "salespeople", "leads", "leads", "leads",
    ]
    payload = client.insert_payloads[0]
    assert payload["lead_score"] == 88
    assert payload["lead_temperature"] == "Hot"
    assert payload["lead_status"] == "New"
    assert payload["next_followup_date"]
    assert "created_at" in payload and "updated_at" in payload


def test_lead_update_uses_existing_active_customer_lead_without_duplicate_insert():
    existing = {"lead_id": "LEAD-000123", "lead_status": "Qualified"}
    updated = {"lead_id": "LEAD-000123", "lead_score": 88, "lead_temperature": "Hot"}
    client = BookingClient([
        [{"customer_id": "CUST-000001"}],
        [{"vehicle_id": "VEH-000001"}],
        [{"salesperson_id": "SP-001", "active": True}],
        [existing],
        [updated],
    ])

    result = create_or_update_lead(lead_request(), client)

    assert result.created is False
    assert result.lead == updated
    assert client.insert_payloads == []
    assert client.update_payloads[0]["lead_score"] == 88
    assert client.update_payloads[0]["lead_temperature"] == "Hot"


@pytest.mark.parametrize(
    ("results", "message"),
    [
        ([[]], "Customer not found"),
        ([[{"customer_id": "CUST-000001"}], []], "Vehicle not found"),
        ([[{"customer_id": "CUST-000001"}], [{"vehicle_id": "VEH-000001"}], []], "Salesperson not found"),
    ],
)
def test_lead_rejects_unknown_referenced_entities(results, message):
    with pytest.raises(BusinessNotFoundError, match=message):
        create_or_update_lead(lead_request(), BookingClient(results))


def test_lead_rejects_inactive_salesperson():
    client = BookingClient([
        [{"customer_id": "CUST-000001"}],
        [{"vehicle_id": "VEH-000001"}],
        [{"salesperson_id": "SP-001", "active": False}],
    ])
    with pytest.raises(BusinessConflictError, match="Salesperson is unavailable"):
        create_or_update_lead(lead_request(), client)


def test_lead_rejects_caller_supplied_score_and_temperature():
    with pytest.raises(ValidationError):
        lead_request(lead_score=100)
    with pytest.raises(ValidationError):
        lead_request(lead_temperature="Hot")


def test_lead_database_failure_is_sanitized_by_route(monkeypatch):
    def unavailable(*_args):
        raise BusinessToolError("provider details must stay private")

    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    monkeypatch.setattr(business_tool_routes, "create_or_update_lead", unavailable)
    try:
        response = TestClient(app).post(
            "/api/tools/create-or-update-lead", json=lead_request().model_dump(mode="json")
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Business tool unavailable"}
        assert "provider details" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_lead_route_returns_authoritative_persisted_response(monkeypatch):
    lead = {"lead_id": "LEAD-000001", "lead_status": "New", "lead_score": 88, "lead_temperature": "Hot"}
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    monkeypatch.setattr(
        business_tool_routes,
        "create_or_update_lead",
        lambda *_args: LeadResponse(created=True, lead=lead),
    )
    try:
        response = TestClient(app).post(
            "/api/tools/create-or-update-lead", json=lead_request().model_dump(mode="json")
        )
        assert response.status_code == 200
        assert response.json() == {
            "success": True, "source": "database", "created": True, "lead": lead,
        }
    finally:
        app.dependency_overrides.clear()


def test_lead_route_rejects_invalid_and_missing_input_before_writes():
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    try:
        client = TestClient(app)
        assert client.post("/api/tools/create-or-update-lead", json={}).status_code == 422
        invalid = client.post(
            "/api/tools/create-or-update-lead",
            json={**lead_request().model_dump(mode="json"), "customer_id": "bad-id"},
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_booking_retry_returns_existing_appointment():
    client = MagicMock()
    existing = {"appointment_id": "APT-000001", "lead_id": "LEAD-000001", "status": "Confirmed"}
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=[existing])
    result = create_test_drive(BookingRequest(
        lead_id="LEAD-000001", customer_id="CUST-000001", vehicle_id="VEH-000001",
        salesperson_id="SP-001", appointment_date="2026-08-26", appointment_time="09:00",
    ), client)
    assert result.created is False
    assert result.appointment["appointment_id"] == "APT-000001"


def test_booking_persists_only_after_authoritative_checks_pass():
    client = BookingClient(booking_success_results())

    result = create_test_drive(booking_request(notes="Retell booking"), client)

    assert result.created is True
    assert result.appointment["appointment_id"] == "APT-000001"
    assert client.tables == [
        "appointments", "leads", "customers", "vehicles", "salespeople",
        "appointments", "appointments", "appointments",
    ]
    assert len(client.insert_payloads) == 1
    payload = client.insert_payloads[0]
    assert payload == {
        "lead_id": "LEAD-000001", "customer_id": "CUST-000001",
        "vehicle_id": "VEH-000001", "salesperson_id": "SP-001",
        "appointment_date": "2026-08-26", "appointment_time": "09:00:00",
        "notes": "Retell booking", "appointment_id": "APT-000001",
        "appointment_type": "Test Drive", "status": "Confirmed",
        "created_by": "Voice Agent", "created_at": payload["created_at"],
    }
    assert isinstance(payload["created_at"], str)


@pytest.mark.parametrize(
    ("results", "message"),
    [
        ([[], [],], "Lead not found"),
        ([[], [{"customer_id": "CUST-000001"}], []], "Customer not found"),
        ([[], [{"customer_id": "CUST-000001"}], [{"customer_id": "CUST-000001"}], []], "Vehicle not found"),
        ([[], [{"customer_id": "CUST-000001"}], [{"customer_id": "CUST-000001"}], [{"vehicle_status": "Available", "test_drive_available": True}], []], "Salesperson not found"),
    ],
)
def test_booking_reports_unknown_referenced_entities(results, message):
    with pytest.raises(BusinessNotFoundError, match=message):
        create_test_drive(booking_request(), BookingClient(results))


def test_booking_rejects_unavailable_vehicle_and_occupied_slot():
    unavailable_vehicle = [
        [], [{"customer_id": "CUST-000001"}], [{"customer_id": "CUST-000001"}],
        [{"vehicle_status": "Sold", "test_drive_available": False}],
    ]
    with pytest.raises(BusinessConflictError, match="Vehicle is unavailable"):
        create_test_drive(booking_request(), BookingClient(unavailable_vehicle))

    occupied_slot = booking_success_results()[:5] + [[{"appointment_id": "APT-999999"}]]
    with pytest.raises(BusinessConflictError, match="slot is no longer available"):
        create_test_drive(booking_request(), BookingClient(occupied_slot))


def test_booking_database_failure_is_sanitized_by_route(monkeypatch):
    def unavailable(*_args):
        raise BusinessToolError("provider details must stay private")

    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    monkeypatch.setattr(business_tool_routes, "create_test_drive", unavailable)
    try:
        response = TestClient(app).post("/api/tools/create-test-drive", json=booking_request().model_dump(mode="json"))
        assert response.status_code == 503
        assert response.json() == {"detail": "Business tool unavailable"}
        assert "provider details" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_booking_route_returns_authoritative_created_appointment(monkeypatch):
    appointment = {"appointment_id": "APT-000001", "status": "Confirmed"}
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    monkeypatch.setattr(
        business_tool_routes,
        "create_test_drive",
        lambda *_args: BookingResponse(created=True, appointment=appointment),
    )
    try:
        response = TestClient(app).post("/api/tools/create-test-drive", json=booking_request().model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json() == {
            "success": True, "source": "database", "created": True,
            "appointment": appointment,
        }
    finally:
        app.dependency_overrides.clear()


def test_financing_uses_rule_and_amortization():
    client = MagicMock()
    vehicle_query = MagicMock(); rule_query = MagicMock()
    vehicle_query.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[{"vehicle_id": "VEH-000001", "condition": "Used", "sale_price": 30000, "year": 2023}])
    rule_query.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[{"apr_min": 6.0, "apr_max": 8.0, "minimum_down_payment_percent": 10,
               "disclaimer": "Estimate only; final terms depend on lender approval."}])
    client.table.side_effect = [vehicle_query, rule_query]
    result = estimate_financing(FinancingEstimateRequest(
        vehicle_id="VEH-000001", term_months=60, down_payment=5000), client)
    assert result.amount_financed == 25000
    assert result.estimated_apr == 7.0
    assert result.estimated_monthly_payment > 0
    assert "lender approval" in result.disclaimer


def test_financing_rejects_insufficient_down_payment():
    client = MagicMock(); vehicle_query = MagicMock(); rule_query = MagicMock()
    vehicle_query.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[{"vehicle_id": "VEH-000001", "condition": "Used", "sale_price": 30000, "year": 2023}])
    rule_query.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[{"apr_min": 6, "apr_max": 8, "minimum_down_payment_percent": 10, "disclaimer": "lender approval"}])
    client.table.side_effect = [vehicle_query, rule_query]
    with pytest.raises(BusinessConflictError, match="Minimum down payment"):
        estimate_financing(FinancingEstimateRequest(vehicle_id="VEH-000001", term_months=60, down_payment=1000), client)


def test_business_routes_validate_before_writes():
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    try:
        response = TestClient(app).post("/api/tools/create-test-drive", json={"lead_id": "bad"})
        assert response.status_code == 422
        assert response.headers["X-Request-ID"]
        assert TestClient(app).post("/api/tools/create-test-drive", json={}).status_code == 422
    finally:
        app.dependency_overrides.clear()
