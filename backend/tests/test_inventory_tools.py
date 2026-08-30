from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.inventory import CsvInventoryRepository
from app.routes import inventory_tools as inventory_tool_routes
from app.routes.inventory_tools import get_inventory_repository
from app.schemas.inventory_tools import InventorySearchFilters
from app.services.inventory_tools import (
    InventoryToolUnavailableError,
    check_vehicle_availability,
    search_inventory,
)


@pytest.fixture
def repository() -> CsvInventoryRepository:
    return CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")


def test_search_inventory_applies_all_filters_and_excludes_sold(repository) -> None:
    result = search_inventory(InventorySearchFilters(
        body_type="SUV", condition="Used", budget_max=30_000,
        drivetrain="AWD", features=["Apple CarPlay"], limit=5,
    ), repository)
    assert result.count == 1
    assert result.vehicles[0].vehicle_id == "VEH-000001"
    assert result.vehicles[0].vehicle_status == "Available"
    assert "Apple CarPlay" in result.vehicles[0].features


def test_check_availability_is_authoritative(repository) -> None:
    available = check_vehicle_availability("VEH-000001", repository)
    sold = check_vehicle_availability("VEH-000002", repository)
    assert available.can_book_test_drive is True
    assert sold.can_book_test_drive is False
    assert "cannot be recommended" in sold.reason


def test_tool_routes_use_repository_dependency(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app)
        response = client.post("/api/tools/search-inventory", json={
            "body_type": "SUV", "condition": "Used", "budget_max": 30000,
            "drivetrain": "AWD", "features": ["Apple CarPlay"], "limit": 5,
        })
        assert response.status_code == 200
        assert response.json()["source"] == "database"
        assert response.json()["count"] == 1

        details = client.get("/api/tools/get-vehicle-details/VEH-000001")
        assert details.status_code == 200
        assert details.json()["vehicle"]["vehicle_id"] == "VEH-000001"

        query_details = client.get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "VEH-000001"}
        )
        assert query_details.status_code == 200
        assert query_details.json() == details.json()

        post_details = client.post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "VEH-000001"}
        )
        assert post_details.status_code == 200
        assert post_details.json() == details.json()

        availability = client.get("/api/tools/check-vehicle-availability/VEH-000002")
        assert availability.status_code == 200
        assert availability.json()["availability"]["can_book_test_drive"] is False

        post_availability = client.post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "VEH-000002"}
        )
        assert post_availability.status_code == 200
        assert post_availability.json() == availability.json()
    finally:
        app.dependency_overrides.clear()


def test_search_contract_rejects_inverted_ranges() -> None:
    client = TestClient(app)
    response = client.post("/api/tools/search-inventory", json={"budget_min": 40000, "budget_max": 30000})
    assert response.status_code == 422


def test_vehicle_details_query_route_handles_not_found_and_invalid_input(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app)
        not_found = client.get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json() == {"detail": "Vehicle not found"}

        invalid = client.get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "bad-id"}
        )
        assert invalid.status_code == 422

        missing = client.get("/api/tools/get-vehicle-details")
        assert missing.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_vehicle_details_post_route_handles_not_found_and_invalid_input(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app)
        not_found = client.post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json() == {"detail": "Vehicle not found"}

        invalid = client.post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "bad-id"}
        )
        assert invalid.status_code == 422

        missing = client.post("/api/tools/get-vehicle-details", json={})
        assert missing.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_vehicle_details_query_route_returns_sanitized_database_error(monkeypatch, repository) -> None:
    def unavailable(*_args):
        raise InventoryToolUnavailableError("provider details must stay private")

    app.dependency_overrides[get_inventory_repository] = lambda: repository
    monkeypatch.setattr(inventory_tool_routes, "get_vehicle_details", unavailable)
    try:
        response = TestClient(app).get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "VEH-000001"}
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Inventory service unavailable"}
        assert "provider details" not in response.text

        post_response = TestClient(app).post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "VEH-000001"}
        )
        assert post_response.status_code == 503
        assert post_response.json() == {"detail": "Inventory service unavailable"}
        assert "provider details" not in post_response.text
    finally:
        app.dependency_overrides.clear()


def test_vehicle_availability_post_route_handles_not_found_and_invalid_input(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app)
        not_found = client.post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json() == {"detail": "Vehicle not found"}

        invalid = client.post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "bad-id"}
        )
        assert invalid.status_code == 422

        missing = client.post("/api/tools/check-vehicle-availability", json={})
        assert missing.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_vehicle_availability_post_route_returns_sanitized_database_error(monkeypatch, repository) -> None:
    def unavailable(*_args):
        raise InventoryToolUnavailableError("provider details must stay private")

    app.dependency_overrides[get_inventory_repository] = lambda: repository
    monkeypatch.setattr(inventory_tool_routes, "check_vehicle_availability", unavailable)
    try:
        response = TestClient(app).post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "VEH-000001"}
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Inventory service unavailable"}
        assert "provider details" not in response.text
    finally:
        app.dependency_overrides.clear()
