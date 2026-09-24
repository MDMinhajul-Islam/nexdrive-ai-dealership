"""Tests for Retell request envelope handling and direct JSON on create_or_update_lead."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.routes.business_tools import get_business_client
from app.schemas.business_tools import LeadResponse, LeadUpsertRequest

TOOL_HEADERS = {"X-Retell-Tool-Key": "test-retell-tool-key"}


# ---------------------------------------------------------------------------
# Schema Tests — Direct JSON
# ---------------------------------------------------------------------------

def test_direct_json_minimal_lead_request():
    """Direct JSON with only mandatory customer_id succeeds with defaults."""
    req = LeadUpsertRequest.model_validate({"customer_id": "CUST-005001"})
    assert req.customer_id == "CUST-005001"
    assert req.source == "Inbound Call"
    assert req.budget is None
    assert req.vehicle_interest is None
    assert req.purchase_timeline is None
    assert req.financing_needed is None
    assert req.trade_in is None
    assert req.assigned_salesperson is None
    assert req.test_drive_requested is False
    assert req.notes == ""


def test_direct_json_with_optional_fields():
    """Direct JSON with optional qualification fields validates correctly."""
    req = LeadUpsertRequest.model_validate({
        "customer_id": "CUST-005001",
        "budget": 45000,
        "vehicle_interest": "VEH-000001",
        "purchase_timeline": "Within 7 Days",
        "financing_needed": True,
        "trade_in": False,
        "assigned_salesperson": "SP-001",
        "test_drive_requested": True,
        "notes": "Interested in AWD models",
    })
    assert req.customer_id == "CUST-005001"
    assert req.budget == 45000
    assert req.vehicle_interest == "VEH-000001"
    assert req.purchase_timeline == "Within 7 Days"
    assert req.financing_needed is True
    assert req.trade_in is False
    assert req.assigned_salesperson == "SP-001"
    assert req.test_drive_requested is True
    assert req.notes == "Interested in AWD models"


def test_direct_json_missing_customer_id_fails():
    """Direct JSON without customer_id fails validation."""
    with pytest.raises(ValidationError):
        LeadUpsertRequest.model_validate({"budget": 30000})


def test_direct_json_invalid_customer_id_pattern():
    """Direct JSON with invalid customer_id pattern fails validation."""
    with pytest.raises(ValidationError):
        LeadUpsertRequest.model_validate({"customer_id": "INVALID-123"})


def test_direct_json_extra_fields_forbidden():
    """Direct JSON with forbidden fields (e.g. caller-supplied score) fails."""
    with pytest.raises(ValidationError):
        LeadUpsertRequest.model_validate({
            "customer_id": "CUST-005001",
            "lead_score": 90,
        })


# ---------------------------------------------------------------------------
# Schema Tests — Retell Request Envelope
# ---------------------------------------------------------------------------

def test_retell_envelope_minimal_lead_request():
    """Retell wrapper with only mandatory customer_id succeeds."""
    payload = {
        "call": {"call_id": "schema-test-1"},
        "name": "create_or_update_lead",
        "args": {
            "customer_id": "CUST-005001",
        },
    }
    req = LeadUpsertRequest.model_validate(payload)
    assert req.customer_id == "CUST-005001"
    assert req.source == "Inbound Call"
    assert req.budget is None


def test_retell_envelope_with_optional_fields():
    """Retell wrapper with qualification fields validates correctly."""
    payload = {
        "call": {"call_id": "schema-test-2"},
        "name": "create_or_update_lead",
        "args": {
            "customer_id": "CUST-005001",
            "budget": 35000,
            "purchase_timeline": "Within 30 Days",
            "financing_needed": True,
            "trade_in": True,
        },
    }
    req = LeadUpsertRequest.model_validate(payload)
    assert req.customer_id == "CUST-005001"
    assert req.budget == 35000
    assert req.purchase_timeline == "Within 30 Days"
    assert req.financing_needed is True
    assert req.trade_in is True


def test_retell_envelope_missing_customer_id_fails():
    """Retell wrapper missing customer_id in args fails validation."""
    payload = {
        "call": {"call_id": "schema-test-3"},
        "name": "create_or_update_lead",
        "args": {
            "budget": 35000,
        },
    }
    with pytest.raises(ValidationError):
        LeadUpsertRequest.model_validate(payload)


def test_retell_envelope_incorrect_tool_name_rejected():
    """Retell wrapper with wrong function name is rejected."""
    payload = {
        "call": {"call_id": "schema-test-4"},
        "name": "resolve_or_create_customer",
        "args": {
            "customer_id": "CUST-005001",
        },
    }
    with pytest.raises(ValidationError, match="Invalid function name"):
        LeadUpsertRequest.model_validate(payload)


def test_retell_envelope_malformed_args_rejected():
    """Retell wrapper with non-dict args is rejected."""
    payload = {
        "call": {"call_id": "schema-test-5"},
        "name": "create_or_update_lead",
        "args": "not-a-dict",
    }
    with pytest.raises(ValidationError, match="Malformed Retell wrapper"):
        LeadUpsertRequest.model_validate(payload)


def test_retell_envelope_missing_args_rejected():
    """Retell wrapper with call and name but missing args is rejected."""
    payload = {
        "call": {"call_id": "schema-test-6"},
        "name": "create_or_update_lead",
    }
    with pytest.raises(ValidationError, match="missing 'args'"):
        LeadUpsertRequest.model_validate(payload)


def test_retell_envelope_extra_fields_inside_args_forbidden():
    """Forbidden extra fields inside wrapper args are rejected."""
    payload = {
        "call": {"call_id": "schema-test-7"},
        "name": "create_or_update_lead",
        "args": {
            "customer_id": "CUST-005001",
            "lead_temperature": "Hot",
        },
    }
    with pytest.raises(ValidationError):
        LeadUpsertRequest.model_validate(payload)


# ---------------------------------------------------------------------------
# Route Integration Tests — Fast API endpoint POST /api/tools/create-or-update-lead
# ---------------------------------------------------------------------------

def test_route_accepts_direct_json(monkeypatch):
    """FastAPI route successfully processes direct JSON."""
    fake_lead = {
        "lead_id": "LEAD-004002",
        "customer_id": "CUST-005001",
        "lead_status": "New",
        "lead_score": 15,
        "lead_temperature": "Cold",
    }

    mock_client = MagicMock()
    app.dependency_overrides[get_business_client] = lambda: mock_client

    monkeypatch.setattr(
        "app.routes.business_tools.create_or_update_lead",
        lambda req, client: LeadResponse(created=True, lead=fake_lead),
    )

    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/create-or-update-lead",
            json={"customer_id": "CUST-005001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] is True
        assert data["lead"]["lead_id"] == "LEAD-004002"
    finally:
        app.dependency_overrides.clear()


def test_route_accepts_retell_envelope(monkeypatch):
    """FastAPI route successfully processes Retell wrapper payload."""
    fake_lead = {
        "lead_id": "LEAD-004002",
        "customer_id": "CUST-005001",
        "lead_status": "New",
        "lead_score": 15,
        "lead_temperature": "Cold",
    }

    mock_client = MagicMock()
    app.dependency_overrides[get_business_client] = lambda: mock_client

    captured_req = []

    def mock_service(req, client):
        captured_req.append(req)
        return LeadResponse(created=True, lead=fake_lead)

    monkeypatch.setattr(
        "app.routes.business_tools.create_or_update_lead",
        mock_service,
    )

    try:
        payload = {
            "call": {"call_id": "schema-test"},
            "name": "create_or_update_lead",
            "args": {
                "customer_id": "CUST-005001",
                "budget": 35000,
                "purchase_timeline": "Within 30 Days",
            },
        }
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/create-or-update-lead",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] is True
        assert data["lead"]["lead_id"] == "LEAD-004002"
        assert len(captured_req) == 1
        assert captured_req[0].customer_id == "CUST-005001"
        assert captured_req[0].budget == 35000
        assert captured_req[0].purchase_timeline == "Within 30 Days"
    finally:
        app.dependency_overrides.clear()


def test_route_rejects_wrong_tool_name_in_envelope():
    """FastAPI route returns 422 when wrapper has an incorrect function name."""
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    try:
        payload = {
            "call": {"call_id": "schema-test"},
            "name": "resolve_or_create_customer",
            "args": {"customer_id": "CUST-005001"},
        }
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/create-or-update-lead",
            json=payload,
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Regression Tests — Malformed wrapper edge cases (bug fix)
# ---------------------------------------------------------------------------

def test_args_without_name_rejected():
    """Retell wrapper with 'args' but missing 'name' must be rejected."""
    payload = {
        "args": {
            "customer_id": "CUST-005001",
        },
    }
    with pytest.raises(ValidationError, match="'args' present without 'name'"):
        LeadUpsertRequest.model_validate(payload)


def test_args_without_name_with_call_rejected():
    """Retell wrapper with 'call' and 'args' but missing 'name' must be rejected."""
    payload = {
        "call": {"call_id": "test"},
        "args": {
            "customer_id": "CUST-005001",
        },
    }
    with pytest.raises(ValidationError, match="'args' present without 'name'"):
        LeadUpsertRequest.model_validate(payload)


def test_name_only_without_args_or_call_rejected():
    """Payload with only 'name' field (no 'args', no 'call') is rejected as ambiguous."""
    payload = {
        "name": "create_or_update_lead",
    }
    with pytest.raises(ValidationError, match="Ambiguous payload"):
        LeadUpsertRequest.model_validate(payload)


def test_call_only_without_name_or_args_rejected():
    """Payload with only 'call' field (no 'name', no 'args') is rejected as ambiguous."""
    payload = {
        "call": {"call_id": "test"},
    }
    with pytest.raises(ValidationError, match="Ambiguous payload"):
        LeadUpsertRequest.model_validate(payload)


def test_direct_fields_mixed_with_name_rejected():
    """Direct fields mixed with 'name' envelope field are rejected."""
    payload = {
        "customer_id": "CUST-005001",
        "name": "create_or_update_lead",
    }
    with pytest.raises(ValidationError, match="Ambiguous payload"):
        LeadUpsertRequest.model_validate(payload)


def test_direct_fields_mixed_with_call_rejected():
    """Direct fields mixed with 'call' envelope field are rejected."""
    payload = {
        "customer_id": "CUST-005001",
        "call": {"call_id": "test"},
    }
    with pytest.raises(ValidationError, match="Ambiguous payload"):
        LeadUpsertRequest.model_validate(payload)


def test_non_dict_args_with_name_rejected():
    """Retell wrapper with name but non-dict args is still rejected."""
    payload = {
        "call": {"call_id": "test"},
        "name": "create_or_update_lead",
        "args": [1, 2, 3],
    }
    with pytest.raises(ValidationError, match="Malformed Retell wrapper"):
        LeadUpsertRequest.model_validate(payload)


def test_incorrect_name_without_args_rejected():
    """Retell wrapper with incorrect function name and no args is rejected."""
    payload = {
        "call": {"call_id": "test"},
        "name": "wrong_function_name",
    }
    with pytest.raises(ValidationError, match="Invalid function name"):
        LeadUpsertRequest.model_validate(payload)


def test_valid_retell_wrapper_still_accepted():
    """Valid complete Retell wrapper continues to work after fix."""
    payload = {
        "call": {"call_id": "regression-test"},
        "name": "create_or_update_lead",
        "args": {
            "customer_id": "CUST-005001",
            "budget": 25000,
        },
    }
    req = LeadUpsertRequest.model_validate(payload)
    assert req.customer_id == "CUST-005001"
    assert req.budget == 25000


def test_direct_json_still_accepted():
    """Direct JSON continues to work after fix."""
    payload = {
        "customer_id": "CUST-005001",
        "budget": 50000,
        "financing_needed": True,
    }
    req = LeadUpsertRequest.model_validate(payload)
    assert req.customer_id == "CUST-005001"
    assert req.budget == 50000
    assert req.financing_needed is True
