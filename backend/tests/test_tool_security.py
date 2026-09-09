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
