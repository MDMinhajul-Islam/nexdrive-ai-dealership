from pydantic import ValidationError
import pytest

from app.schemas.admin import VehicleCreateRequest
from app.schemas.operations import ConversationOutcomeRequest, EscalationRequest, TradeInCaptureRequest


def valid_vehicle(**changes):
    payload = {
        "make": "Toyota", "model": "RAV4", "year": 2026, "trim": "XLE",
        "body_type": "SUV", "condition": "New", "mileage": 12,
        "exterior_color": "Pearl White", "interior_color": "Black",
        "fuel_type": "Hybrid", "transmission": "CVT", "drivetrain": "AWD",
        "seating_capacity": 5, "msrp": 38000, "sale_price": 36900,
        "vehicle_status": "Available", "test_drive_available": True,
        "warranty": "Manufacturer Warranty", "certification": "None",
        "dealership_location": "NexDrive Motors Plano", "feature_ids": ["FEAT-001"],
    }
    payload.update(changes)
    return payload


def test_vehicle_create_contract_enforces_pricing_and_operational_truth():
    assert VehicleCreateRequest(**valid_vehicle()).sale_price == 36900
    with pytest.raises(ValidationError): VehicleCreateRequest(**valid_vehicle(sale_price=39000))
    with pytest.raises(ValidationError): VehicleCreateRequest(**valid_vehicle(vehicle_status="Sold", test_drive_available=True))
    with pytest.raises(ValidationError): VehicleCreateRequest(**valid_vehicle(mileage=700))


def test_cpo_requires_certification():
    with pytest.raises(ValidationError): VehicleCreateRequest(**valid_vehicle(condition="Certified Pre-Owned", mileage=24000))


def test_agent_operation_contracts_are_typed():
    trade = TradeInCaptureRequest(lead_id="LEAD-000001", customer_id="CUST-000001", make="Honda", model="Civic", year=2021, mileage=42000, condition="Good")
    assert trade.loan_balance == 0
    escalation = EscalationRequest(session_id="CALL-DEMO-001", reason="Customer Request", summary="Caller requested a salesperson")
    assert escalation.reason == "Customer Request"
    outcome = ConversationOutcomeRequest(session_id="CALL-DEMO-001", channel="Web Voice", status="Completed", outcome="Discovery", started_at="2026-08-30T10:00:00Z")
    assert outcome.outcome == "Discovery"
