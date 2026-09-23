import json
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

TOOL_HEADERS = {"X-Retell-Tool-Key": "test-retell-tool-key"}


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


def test_search_inventory_supports_suv_budget_and_seating_alias(repository) -> None:
    filters = InventorySearchFilters.model_validate({
        "body_type": "SUV",
        "budget_max": 40_000,
        "seating_capacity": 5,
    })

    result = search_inventory(filters, repository)

    assert filters.seating_capacity_min == 5
    assert result.count == 1
    assert result.vehicles[0].vehicle_id == "VEH-000001"


def test_awd_aliases_are_one_canonical_drivetrain_filter(repository) -> None:
    filters = InventorySearchFilters(
        body_type="SUV",
        drivetrain="AWD",
        features=["AWD", "All-Wheel Drive", "Apple CarPlay"],
    )

    result = search_inventory(filters, repository)

    assert filters.drivetrain == "AWD"
    assert filters.features == ["Apple CarPlay"]
    assert result.count == 1
    assert result.vehicles[0].vehicle_id == "VEH-000001"


def test_awd_feature_alias_populates_canonical_drivetrain(repository) -> None:
    filters = InventorySearchFilters(features=["All-Wheel Drive"])

    result = search_inventory(filters, repository)

    assert filters.drivetrain == "AWD"
    assert filters.features == []
    assert result.count == 1


def test_null_features_and_drivetrain_mean_no_filter(repository) -> None:
    filters = InventorySearchFilters.model_validate({
        "body_type": "SUV",
        "features": None,
        "drivetrain": None,
    })

    result = search_inventory(filters, repository)

    assert filters.features == []
    assert filters.drivetrain is None
    assert result.count == 1


def test_search_route_accepts_real_retell_null_relaxation_payload(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/search-inventory",
            json={
                "budget_max": 40_000,
                "features": None,
                "body_type": "SUV",
                "drivetrain": None,
                "seating_capacity": 5,
            },
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "field",
    [
        "make", "model", "body_type", "condition", "budget_min", "budget_max",
        "year_min", "year_max", "mileage_max", "drivetrain", "fuel_type",
        "seating_capacity_min", "seating_capacity", "features", "limit",
    ],
)
def test_each_optional_search_field_safely_accepts_null(field) -> None:
    filters = InventorySearchFilters.model_validate({field: None})

    assert filters.features == []
    assert filters.limit == 5


def test_no_match_response_supports_safe_preference_relaxation(repository) -> None:
    no_match = search_inventory(
        InventorySearchFilters(body_type="SUV", features=["Unknown Feature"]),
        repository,
    )
    relaxed = search_inventory(
        InventorySearchFilters(body_type="SUV", features=None, drivetrain=None),
        repository,
    )

    assert no_match.count == 0
    assert "matched all hard filters" in no_match.message
    assert "explicit must-have" in no_match.message
    assert relaxed.count == 1


def test_cpo_condition_alias_maps_to_production_value() -> None:
    repository = CsvInventoryRepository(
        Path(__file__).resolve().parents[2] / "database" / "seed"
    )

    filters = InventorySearchFilters(
        body_type="SUV", condition="CPO", budget_max=40_000, seating_capacity_min=5,
    )
    result = search_inventory(filters, repository)

    assert filters.condition == "Certified Pre-Owned"
    assert result.count > 0
    assert all(vehicle.condition == "Certified Pre-Owned" for vehicle in result.vehicles)


def test_retell_search_contract_documents_hard_filters_and_nullable_fields() -> None:
    tools_path = Path(__file__).resolve().parents[2] / "retell" / "tools.json"
    tools = json.loads(tools_path.read_text(encoding="utf-8"))["tools"]
    contract = next(tool for tool in tools if tool["name"] == "search_inventory")
    properties = contract["body"]["properties"]

    assert "AND hard filter" in contract["description"]
    assert "never in features" in contract["description"]
    assert properties["features"]["type"] == ["array", "null"]
    assert properties["drivetrain"]["type"] == ["string", "null"]
    assert properties["seating_capacity"]["description"] == "Minimum required seating capacity."


def test_check_availability_is_authoritative(repository) -> None:
    available = check_vehicle_availability("VEH-000001", repository)
    sold = check_vehicle_availability("VEH-000002", repository)
    assert available.can_book_test_drive is True
    assert sold.can_book_test_drive is False
    assert "cannot be recommended" in sold.reason


def test_tool_routes_use_repository_dependency(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        response = client.post("/api/tools/search-inventory", json={
            "body_type": "SUV", "condition": "Used", "budget_max": 30000,
            "drivetrain": "AWD", "features": ["Apple CarPlay"], "limit": 5,
        })
        assert response.status_code == 200
        assert response.json()["source"] == "database"
        assert response.json()["count"] == 1
        assert response.json()["message"] == ""
        assert "data" not in response.json()
        assert set(response.json()["vehicles"][0]) == {
            "vehicle_id", "make", "model", "year", "trim", "body_type",
            "condition", "mileage", "fuel_type", "drivetrain",
            "seating_capacity", "sale_price", "dealership_location", "features",
            "test_drive_available",
        }

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
    client = TestClient(app, headers=TOOL_HEADERS)
    response = client.post("/api/tools/search-inventory", json={"budget_min": 40000, "budget_max": 30000})
    assert response.status_code == 422


def test_search_route_requires_meaningful_customer_preferences(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/search-inventory", json={}
        )
        assert response.status_code == 422
        assert response.json() == {
            "success": False,
            "error_code": "MISSING_SEARCH_CRITERIA",
            "retryable": False,
            "message": "Vehicle search requires customer preferences",
        }
        all_null = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/search-inventory",
            json={"features": None, "drivetrain": None, "body_type": None, "limit": None},
        )
        assert all_null.status_code == 422
        assert all_null.json()["error_code"] == "MISSING_SEARCH_CRITERIA"
    finally:
        app.dependency_overrides.clear()


def test_search_normalizes_voice_input_case_and_spacing(repository) -> None:
    result = search_inventory(
        InventorySearchFilters(
            make="  toyota ", model=" rav4 ", body_type="suv",
            condition="used", drivetrain="awd", features=[" apple carplay "],
        ),
        repository,
    )
    assert result.count == 1
    assert result.vehicles[0].vehicle_id == "VEH-000001"


def test_search_route_returns_ai_friendly_inventory_failure(monkeypatch, repository) -> None:
    def unavailable(*_args):
        raise InventoryToolUnavailableError("private database diagnostics")

    app.dependency_overrides[get_inventory_repository] = lambda: repository
    monkeypatch.setattr(inventory_tool_routes, "search_inventory", unavailable)
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/search-inventory", json={"make": "Toyota"}
        )
        assert response.status_code == 503
        assert response.json() == {
            "success": False,
            "error_code": "INVENTORY_UNAVAILABLE",
            "retryable": True,
            "message": "Live inventory is temporarily unavailable",
        }
        assert "private database diagnostics" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_vehicle_details_query_route_handles_not_found_and_invalid_input(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        not_found = client.get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json() == {
            "success": False, "error_code": "VEHICLE_NOT_FOUND",
            "retryable": False, "message": "Vehicle not found",
        }

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
        client = TestClient(app, headers=TOOL_HEADERS)
        not_found = client.post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json()["error_code"] == "VEHICLE_NOT_FOUND"

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
        response = TestClient(app, headers=TOOL_HEADERS).get(
            "/api/tools/get-vehicle-details", params={"vehicle_id": "VEH-000001"}
        )
        assert response.status_code == 503
        assert response.json() == {
            "success": False, "error_code": "INVENTORY_UNAVAILABLE",
            "retryable": True, "message": "Live inventory is temporarily unavailable",
        }
        assert "provider details" not in response.text

        post_response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-vehicle-details", json={"vehicle_id": "VEH-000001"}
        )
        assert post_response.status_code == 503
        assert post_response.json() == response.json()
        assert "provider details" not in post_response.text
    finally:
        app.dependency_overrides.clear()


def test_vehicle_availability_post_route_handles_not_found_and_invalid_input(repository) -> None:
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        not_found = client.post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "VEH-999999"}
        )
        assert not_found.status_code == 404
        assert not_found.json()["error_code"] == "VEHICLE_NOT_FOUND"

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
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/check-vehicle-availability", json={"vehicle_id": "VEH-000001"}
        )
        assert response.status_code == 503
        assert response.json()["error_code"] == "INVENTORY_UNAVAILABLE"
        assert "provider details" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_search_inventory_timing_logging(repository, caplog):
    import logging
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routes.inventory_tools import get_inventory_repository
    
    caplog.set_level(logging.INFO, logger="nexdrive.inventory.timing")
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    try:
        response = TestClient(app, headers={"X-Retell-Tool-Key": "test-retell-tool-key"}).post(
            "/api/tools/search-inventory",
            json={"body_type": "SUV", "features": ["Backup Camera"]},
        )
        assert response.status_code == 200
        
        log_messages = [record.message for record in caplog.records if "search_inventory timing" in record.message]
        assert len(log_messages) == 1
        log_str = log_messages[0]
        
        assert "total_ms=" in log_str
        assert "validation_ms=" in log_str
        assert "normalization_ms=" in log_str
        assert "db_ms=" in log_str
        assert "response_build_ms=" in log_str
        assert "count=" in log_str
    finally:
        app.dependency_overrides.clear()

def test_search_inventory_timing_logging_error(repository, monkeypatch, caplog):
    import logging
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routes.inventory_tools import get_inventory_repository
    from app.services.inventory_tools import InventoryToolUnavailableError
    from app.routes import inventory_tools as inventory_tool_routes
    
    def unavailable(*_args):
        raise InventoryToolUnavailableError("private database diagnostics")
        
    caplog.set_level(logging.INFO, logger="nexdrive.inventory.timing")
    app.dependency_overrides[get_inventory_repository] = lambda: repository
    monkeypatch.setattr(inventory_tool_routes, "search_inventory", unavailable)
    
    try:
        response = TestClient(app, headers={"X-Retell-Tool-Key": "test-retell-tool-key"}).post(
            "/api/tools/search-inventory",
            json={"make": "Toyota"}
        )
        assert response.status_code == 503
        
        log_messages = [record.message for record in caplog.records if "search_inventory timing" in record.message]
        assert len(log_messages) == 1
        log_str = log_messages[0]
        
        assert "total_ms=" in log_str
        assert "failed_stage=database" in log_str
    finally:
        app.dependency_overrides.clear()
