"""Tests for resolve_or_create_customer — customer resolution and creation."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.routes.business_tools import get_business_client
from app.schemas.business_tools import ResolveCustomerRequest, ResolveCustomerResponse
from app.services.business_tools import (
    BusinessConflictError,
    BusinessToolError,
    resolve_or_create_customer,
)

TOOL_HEADERS = {"X-Retell-Tool-Key": "test-retell-tool-key"}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class CustomerQuery:
    """Chainable mock for Supabase query builder."""

    def __init__(self, result, client=None):
        self.result = result
        self.client = client

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, payload):
        if self.client:
            self.client.insert_payloads.append(payload)
        return self

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return SimpleNamespace(data=self.result)


class CustomerClient:
    """Mock Supabase client with configurable per-call results."""

    def __init__(self, results):
        self.results = list(results)
        self._idx = 0
        self.insert_payloads = []

    def table(self, _name):
        result = self.results[self._idx]
        self._idx += 1
        return CustomerQuery(result, self)


def make_request(**overrides):
    defaults = {
        "first_name": "Jordan",
        "last_name": "Lee",
        "phone": "214-555-0176",
    }
    defaults.update(overrides)
    return ResolveCustomerRequest(**defaults)


# ---------------------------------------------------------------------------
# TEST A — Minimal customer (no email)
# ---------------------------------------------------------------------------

def test_minimal_customer_creation():
    """Create a customer with only first_name, last_name, phone. Email=NULL."""
    client = CustomerClient([
        [],                                          # lookup: no match
        [{"customer_id": "CUST-005000"}],            # _next_id query
        [{"customer_id": "CUST-005001"}],            # insert result
    ])
    request = make_request()
    result = resolve_or_create_customer(request, client)
    assert result.created is True
    assert result.customer_id == "CUST-005001"
    assert len(client.insert_payloads) == 1
    payload = client.insert_payloads[0]
    assert payload["synthetic_email"] is None
    assert payload["synthetic_phone"] == "+1-214-555-0176"
    assert payload["first_name"] == "Jordan"
    assert payload["last_name"] == "Lee"
    assert "city" not in payload
    assert "budget_min" not in payload


# ---------------------------------------------------------------------------
# TEST B — Customer with email
# ---------------------------------------------------------------------------

def test_customer_with_email():
    """Create a customer with a valid email."""
    client = CustomerClient([
        [],                                          # lookup: no match
        [{"customer_id": "CUST-005000"}],            # _next_id
        [{"customer_id": "CUST-005001"}],            # insert result
    ])
    request = make_request(email="jordan.lee@example.com")
    result = resolve_or_create_customer(request, client)
    assert result.created is True
    payload = client.insert_payloads[0]
    assert payload["synthetic_email"] == "jordan.lee@example.com"


# ---------------------------------------------------------------------------
# TEST C — Spoken email normalization
# ---------------------------------------------------------------------------

def test_spoken_email_normalization():
    """Spoken email 'Jordan dot Lee at G mail dot com' normalizes correctly."""
    request = ResolveCustomerRequest(
        first_name="Jordan",
        last_name="Lee",
        phone="214-555-0176",
        email="Jordan dot Lee at G mail dot com",
    )
    assert request.email == "jordan.lee@gmail.com"


# ---------------------------------------------------------------------------
# TEST D — Existing customer
# ---------------------------------------------------------------------------

def test_existing_customer_returned():
    """If phone matches an existing customer, return it without INSERT."""
    client = CustomerClient([
        [{"customer_id": "CUST-000042"}],            # lookup: match found
    ])
    request = make_request()
    result = resolve_or_create_customer(request, client)
    assert result.created is False
    assert result.customer_id == "CUST-000042"
    assert len(client.insert_payloads) == 0


# ---------------------------------------------------------------------------
# TEST E — Invalid phone
# ---------------------------------------------------------------------------

def test_invalid_phone_rejected():
    """A phone number with fewer than 10 digits raises validation error."""
    with pytest.raises(ValidationError, match="10 digits"):
        make_request(phone="123")


# ---------------------------------------------------------------------------
# TEST F — Invalid email
# ---------------------------------------------------------------------------

def test_invalid_email_rejected():
    """An email without @ or . after normalization raises validation error."""
    with pytest.raises(ValidationError, match="email"):
        make_request(email="jordan lee gmail")


# ---------------------------------------------------------------------------
# TEST G — Synthetic data compatibility
# ---------------------------------------------------------------------------

def test_synthetic_phone_format_accepted():
    """Synthetic phone format +1-555-010-0001 is accepted by phone validator."""
    request = ResolveCustomerRequest(
        first_name="Avery",
        last_name="Campbell",
        phone="+1-555-010-0001",
    )
    assert request.phone == "+1-555-010-0001"


def test_synthetic_email_format_accepted():
    """Synthetic email format customer000001@nexdrive.example is accepted."""
    request = ResolveCustomerRequest(
        first_name="Avery",
        last_name="Campbell",
        phone="+1-555-010-0001",
        email="customer000001@nexdrive.example",
    )
    assert request.email == "customer000001@nexdrive.example"


# ---------------------------------------------------------------------------
# TEST H — Optional customer fields
# ---------------------------------------------------------------------------

def test_optional_fields_not_in_payload():
    """No qualification fields are included in the INSERT payload."""
    client = CustomerClient([
        [],
        [{"customer_id": "CUST-000000"}],
        [{"customer_id": "CUST-000001"}],
    ])
    request = make_request()
    resolve_or_create_customer(request, client)
    payload = client.insert_payloads[0]
    optional_fields = [
        "city", "preferred_vehicle_type", "preferred_brand",
        "budget_min", "budget_max", "financing_needed",
        "family_size", "trade_in", "purchase_timeline",
        "lead_source", "buyer_profile",
    ]
    for field in optional_fields:
        assert field not in payload, f"Unexpected optional field {field} in payload"


# ---------------------------------------------------------------------------
# TEST I — Retell envelope
# ---------------------------------------------------------------------------

def test_retell_envelope_extraction():
    """Retell envelope is correctly unwrapped to extract args."""
    data = {
        "call": {"call_id": "diagnostic-test"},
        "name": "resolve_or_create_customer",
        "args": {
            "first_name": "Jordan",
            "last_name": "Lee",
            "phone": "214-555-0176",
            "email": "Jordan dot Lee at G mail dot com",
        },
    }
    request = ResolveCustomerRequest(**data)
    assert request.first_name == "Jordan"
    assert request.last_name == "Lee"
    assert request.phone == "+1-214-555-0176"
    assert request.email == "jordan.lee@gmail.com"


def test_retell_envelope_route():
    """POST /api/tools/resolve-customer accepts Retell envelope."""
    client = CustomerClient([
        [{"customer_id": "CUST-000001"}],
    ])
    app.dependency_overrides[get_business_client] = lambda: client
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/resolve-customer",
            json={
                "call": {"call_id": "diagnostic-test"},
                "name": "resolve_or_create_customer",
                "args": {
                    "first_name": "Jordan",
                    "last_name": "Lee",
                    "phone": "214-555-0176",
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["created"] is False
        assert body["customer_id"] == "CUST-000001"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TEST J — Concurrent customer creation (phone uniqueness collision)
# ---------------------------------------------------------------------------

def test_phone_collision_returns_existing_customer():
    """When INSERT fails with phone uniqueness violation, re-query and return."""
    phone_collision = Exception(
        "duplicate key value violates unique constraint "
        '"customers_synthetic_phone_key" (synthetic_phone)'
    )
    client = CustomerClient([
        [],                                          # initial lookup: no match
        [{"customer_id": "CUST-005000"}],            # _next_id
        phone_collision,                             # insert: phone collision
        [{"customer_id": "CUST-005001"}],            # re-query: found
    ])
    request = make_request()
    result = resolve_or_create_customer(request, client)
    assert result.created is False
    assert result.customer_id == "CUST-005001"


def test_customer_id_collision_retries():
    """When INSERT fails with customer_id uniqueness, retry with next ID."""
    id_collision = Exception(
        "duplicate key value violates unique constraint "
        '"customers_pkey" 23505'
    )
    client = CustomerClient([
        [],                                          # initial lookup: no match
        [{"customer_id": "CUST-005000"}],            # _next_id (attempt 1)
        id_collision,                                # insert: ID collision
        [{"customer_id": "CUST-005001"}],            # _next_id (attempt 2)
        [{"customer_id": "CUST-005002"}],            # insert: success
    ])
    request = make_request()
    result = resolve_or_create_customer(request, client)
    assert result.created is True
    assert result.customer_id == "CUST-005002"


# ---------------------------------------------------------------------------
# TEST K — Database constraint tests (via schema validation)
# ---------------------------------------------------------------------------

def test_missing_first_name_rejected():
    with pytest.raises(ValidationError):
        ResolveCustomerRequest(last_name="Lee", phone="214-555-0176")


def test_missing_last_name_rejected():
    with pytest.raises(ValidationError):
        ResolveCustomerRequest(first_name="Jordan", phone="214-555-0176")


def test_missing_phone_rejected():
    with pytest.raises(ValidationError):
        ResolveCustomerRequest(first_name="Jordan", last_name="Lee")


def test_valid_phone_formats():
    for phone in ["214-555-0176", "(214) 555-0176", "2145550176", "1-214-555-0176"]:
        req = ResolveCustomerRequest(first_name="J", last_name="L", phone=phone)
        assert req.phone == "+1-214-555-0176"


def test_non_unique_insert_failure_raises():
    """A non-uniqueness database error raises BusinessToolError."""
    db_error = Exception("connection refused")
    client = CustomerClient([
        [],                                          # lookup: no match
        [{"customer_id": "CUST-005000"}],            # _next_id
        db_error,                                    # insert: non-unique error
    ])
    with pytest.raises(BusinessToolError, match="Insert failed"):
        resolve_or_create_customer(make_request(), client)


# ---------------------------------------------------------------------------
# TEST L — Regression: routes unchanged
# ---------------------------------------------------------------------------

def test_resolve_customer_route_invalid_phone():
    """The route returns structured INVALID_PHONE for bad phone input."""
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/resolve-customer",
            json={
                "call": {"call_id": "test"},
                "name": "resolve_or_create_customer",
                "args": {"first_name": "J", "last_name": "L", "phone": "123"},
            },
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_PHONE"
    finally:
        app.dependency_overrides.clear()


def test_resolve_customer_route_invalid_email():
    """The route returns structured INVALID_EMAIL for bad email input."""
    app.dependency_overrides[get_business_client] = lambda: MagicMock()
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/resolve-customer",
            json={
                "call": {"call_id": "test"},
                "name": "resolve_or_create_customer",
                "args": {
                    "first_name": "J",
                    "last_name": "L",
                    "phone": "214-555-0176",
                    "email": "jordan lee gmail",
                },
            },
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_EMAIL"
    finally:
        app.dependency_overrides.clear()


def test_email_none_stored_not_empty_string():
    """Missing email must be stored as None/NULL, never empty string."""
    client = CustomerClient([
        [],
        [{"customer_id": "CUST-000000"}],
        [{"customer_id": "CUST-000001"}],
    ])
    request = make_request()
    assert request.email is None
    resolve_or_create_customer(request, client)
    payload = client.insert_payloads[0]
    assert payload["synthetic_email"] is None
    assert payload["synthetic_email"] != ""
