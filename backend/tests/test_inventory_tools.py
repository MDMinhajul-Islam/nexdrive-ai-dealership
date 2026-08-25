from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.inventory import CsvInventoryRepository
from app.routes.inventory_tools import get_inventory_repository
from app.schemas.inventory_tools import InventorySearchFilters
from app.services.inventory_tools import check_vehicle_availability, search_inventory


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

        availability = client.get("/api/tools/check-vehicle-availability/VEH-000002")
        assert availability.status_code == 200
        assert availability.json()["availability"]["can_book_test_drive"] is False
    finally:
        app.dependency_overrides.clear()


def test_search_contract_rejects_inverted_ranges() -> None:
    client = TestClient(app)
    response = client.post("/api/tools/search-inventory", json={"budget_min": 40000, "budget_max": 30000})
    assert response.status_code == 422
