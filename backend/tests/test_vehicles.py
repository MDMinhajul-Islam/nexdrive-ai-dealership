from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.routes import vehicles as vehicle_routes
from app.schemas.vehicle import VehicleDetails
from app.services import vehicles as vehicle_service
from app.services.vehicles import VehicleDatabaseError, VehicleNotFoundError


client = TestClient(app)

VEHICLE_ROW = {
    "vehicle_id": "VEH-000001",
    "vin": "NXD2LW9SL100W5WKZ",
    "stock_number": "NX-000001",
    "make": "Toyota",
    "model": "Camry",
    "year": 2024,
    "trim": "XLE",
    "body_type": "Sedan",
    "condition": "Used",
    "mileage": 26560,
    "exterior_color": "Silver Metallic",
    "interior_color": "Parchment Leather",
    "fuel_type": "Hybrid",
    "transmission": "Automatic",
    "drivetrain": "FWD",
    "seating_capacity": 5,
    "msrp": 37050,
    "sale_price": 28100,
    "vehicle_status": "Available",
    "test_drive_available": True,
    "warranty": "90-Day Dealer Limited Warranty",
    "certification": "None",
    "dealership_location": "Dallas Central",
}


def vehicle_details() -> VehicleDetails:
    return VehicleDetails.model_validate(
        {**VEHICLE_ROW, "features": ["Adaptive Cruise Control", "Hybrid Powertrain"]}
    )


def test_existing_vehicle_returns_details_and_features(monkeypatch) -> None:
    monkeypatch.setattr(vehicle_routes, "get_vehicle_details", lambda _: vehicle_details())

    response = client.get("/api/vehicles/VEH-000001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert set(VEHICLE_ROW) <= set(payload["vehicle"])
    assert payload["vehicle"]["vehicle_id"] == "VEH-000001"
    assert payload["vehicle"]["stock_number"] == "NX-000001"
    assert payload["vehicle"]["make"] == "Toyota"
    assert payload["vehicle"]["sale_price"] == 28100
    assert payload["vehicle"]["features"] == [
        "Adaptive Cruise Control",
        "Hybrid Powertrain",
    ]
    assert isinstance(payload["vehicle"]["features"], list)


def test_unknown_vehicle_returns_404(monkeypatch) -> None:
    def missing(_: str) -> VehicleDetails:
        raise VehicleNotFoundError

    monkeypatch.setattr(vehicle_routes, "get_vehicle_details", missing)

    response = client.get("/api/vehicles/VEH-999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Vehicle not found"}


def test_vehicle_database_failure_is_safe(monkeypatch) -> None:
    def failed(_: str) -> VehicleDetails:
        raise VehicleDatabaseError("provider details must stay private")

    monkeypatch.setattr(vehicle_routes, "get_vehicle_details", failed)

    response = client.get("/api/vehicles/VEH-000001")

    assert response.status_code == 503
    assert response.json() == {"detail": "Vehicle service unavailable"}
    assert "provider details" not in response.text


def test_invalid_vehicle_id_returns_422() -> None:
    response = client.get("/api/vehicles/not-a-vehicle-id")

    assert response.status_code == 422


def test_service_queries_exact_vehicle_and_feature_names(monkeypatch) -> None:
    client_mock = MagicMock()
    vehicle_query = (
        client_mock.table.return_value.select.return_value.eq.return_value.limit.return_value
    )
    vehicle_query.execute.return_value = SimpleNamespace(data=[VEHICLE_ROW])

    feature_table = MagicMock()
    feature_query = feature_table.select.return_value.eq.return_value
    feature_query.execute.return_value = SimpleNamespace(
        data=[
            {"features": {"name": "Hybrid Powertrain"}},
            {"features": {"name": "Adaptive Cruise Control"}},
        ]
    )
    client_mock.table.side_effect = [client_mock.table.return_value, feature_table]
    monkeypatch.setattr(vehicle_service, "get_supabase", lambda: client_mock)

    result = vehicle_service.get_vehicle_details("VEH-000001")

    assert result.vehicle_id == "VEH-000001"
    assert result.features == ["Adaptive Cruise Control", "Hybrid Powertrain"]
    first_table = client_mock.table.return_value
    first_table.select.return_value.eq.assert_called_once_with(
        "vehicle_id", "VEH-000001"
    )
    first_table.select.return_value.eq.return_value.limit.assert_called_once_with(1)
    feature_table.select.assert_called_once_with("features(name)")
    feature_table.select.return_value.eq.assert_called_once_with(
        "vehicle_id", "VEH-000001"
    )


def test_service_raises_not_found_without_feature_query(monkeypatch) -> None:
    client_mock = MagicMock()
    query = client_mock.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr(vehicle_service, "get_supabase", lambda: client_mock)

    try:
        vehicle_service.get_vehicle_details("VEH-999999")
    except VehicleNotFoundError:
        pass
    else:
        raise AssertionError("VehicleNotFoundError was not raised")

    client_mock.table.assert_called_once_with("vehicles")
