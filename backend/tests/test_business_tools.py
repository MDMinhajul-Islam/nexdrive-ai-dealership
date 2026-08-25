from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.business_tools import get_business_client
from app.schemas.business_tools import BookingRequest, FinancingEstimateRequest, LeadUpsertRequest
from app.services.business_tools import BusinessConflictError, create_test_drive, estimate_financing, score_lead


def lead_request(**changes):
    values = dict(customer_id="CUST-000001", budget=30000, vehicle_interest="VEH-000001",
                  purchase_timeline="Within 7 Days", financing_needed=True, trade_in=True,
                  assigned_salesperson="SP-001")
    values.update(changes)
    return LeadUpsertRequest(**values)


def test_lead_scoring_is_deterministic_and_bucketed():
    hot_score, hot = score_lead(lead_request())
    cold_score, cold = score_lead(lead_request(
        vehicle_interest=None, purchase_timeline="Researching", financing_needed=False,
        trade_in=False, budget=3000,
    ))
    assert hot_score >= 70 and hot == "Hot"
    assert cold_score <= 39 and cold == "Cold"


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
    app.dependency_overrides[get_business_client] = MagicMock
    try:
        response = TestClient(app).post("/api/tools/create-test-drive", json={"lead_id": "bad"})
        assert response.status_code == 422
        assert response.headers["X-Request-ID"]
    finally:
        app.dependency_overrides.clear()
