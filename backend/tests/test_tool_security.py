import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routes.customer_tools import get_customer_tools_repository
from app.routes.inventory_tools import get_inventory_repository
from app import tool_auth


class MinimalInventoryRepository:
    def search(self, _filters):
        return []


class MinimalCustomerRepository:
    def customer_history(self, customer_id):
        return {
            "customer": {"customer_id": customer_id},
            "leads": [],
            "appointments": [],
        }


def test_tool_routes_reject_missing_and_invalid_authentication(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key="expected-tool-key"),
    )
    client = TestClient(app)

    missing = client.post("/api/tools/search-inventory", json={"make": "Toyota"})
    invalid = client.post(
        "/api/tools/search-inventory",
        json={"make": "Toyota"},
        headers={"X-Retell-Tool-Key": "wrong-tool-key"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json() == {
        "success": False,
        "error_code": "UNAUTHORIZED",
        "retryable": False,
        "message": "Retell tool authentication required",
    }
    assert "wrong-tool-key" not in caplog.text


def test_tool_route_rejects_missing_server_auth_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key=""),
    )
    response = TestClient(app).post(
        "/api/tools/search-inventory", json={"make": "Toyota"}
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "TOOL_AUTH_UNAVAILABLE"


def test_authenticated_tool_request_is_accepted(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key="expected-tool-key"),
    )
    app.dependency_overrides[get_inventory_repository] = MinimalInventoryRepository
    try:
        response = TestClient(app).post(
            "/api/tools/search-inventory",
            json={"make": "Toyota"},
            headers={"X-Retell-Tool-Key": "expected-tool-key"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_tool_execution_log_contains_safe_trace_fields(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key="expected-tool-key"),
    )
    app.dependency_overrides[get_inventory_repository] = MinimalInventoryRepository
    caplog.set_level("INFO", logger="nexdrive.audit")
    try:
        response = TestClient(app).post(
            "/api/tools/search-inventory",
            json={"make": "Toyota"},
            headers={
                "X-Retell-Tool-Key": "expected-tool-key",
                "X-Retell-Call-ID": "call-123",
                "X-Request-ID": "tool-request-123",
            },
        )
        assert response.status_code == 200
        events = [
            json.loads(record.message)
            for record in caplog.records
            if record.message.startswith("{")
        ]
        event = next(item for item in events if item["event"] == "retell_tool_request")
        assert event["retell_call_id"] == "call-123"
        assert event["request_id"] == "tool-request-123"
        assert event["tool_name"] == "search_inventory"
        assert event["success"] is True
        assert event["error_code"] is None
        assert event["duration_ms"] >= 0
        assert "received_at" in event
        assert "completed_at" in event
        assert "expected-tool-key" not in caplog.text
        assert "Toyota" not in caplog.text
    finally:
        app.dependency_overrides.clear()


def test_failed_tool_execution_log_has_safe_failure_reason(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key="expected-tool-key"),
    )
    caplog.set_level("INFO", logger="nexdrive.audit")

    response = TestClient(app).post(
        "/api/tools/search-inventory",
        json={"make": "Toyota"},
        headers={"X-Retell-Call-ID": "call-456"},
    )

    assert response.status_code == 401
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.message.startswith("{")
    ]
    event = next(item for item in events if item["event"] == "retell_tool_request")
    assert event["retell_call_id"] == "call-456"
    assert event["success"] is False
    assert event["error_code"] == "UNAUTHORIZED"
    assert "expected-tool-key" not in caplog.text
    assert "Toyota" not in caplog.text


def test_customer_history_requires_matching_verified_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_auth,
        "get_settings",
        lambda: SimpleNamespace(retell_tool_api_key="expected-tool-key"),
    )
    app.dependency_overrides[get_customer_tools_repository] = MinimalCustomerRepository
    client = TestClient(
        app, headers={"X-Retell-Tool-Key": "expected-tool-key"}
    )
    try:
        missing = client.post(
            "/api/tools/get-customer-history", json={"customer_id": "CUST-000001"}
        )
        mismatch = client.post(
            "/api/tools/get-customer-history",
            json={"customer_id": "CUST-000001"},
            headers={"X-Retell-Verified-Customer-ID": "CUST-000002"},
        )
        accepted = client.post(
            "/api/tools/get-customer-history",
            json={"customer_id": "CUST-000001"},
            headers={"X-Retell-Verified-Customer-ID": "CUST-000001"},
        )

        assert missing.status_code == 403
        assert mismatch.status_code == 403
        assert missing.json()["error_code"] == "CUSTOMER_IDENTITY_NOT_VERIFIED"
        assert accepted.status_code == 200
        assert accepted.json()["history"]["customer"]["customer_id"] == "CUST-000001"
    finally:
        app.dependency_overrides.clear()
