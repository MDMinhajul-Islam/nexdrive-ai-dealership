"""Business logic for database-grounded read-only inventory tools."""

from __future__ import annotations

from app.repositories.inventory import InventoryRepository, InventoryRepositoryError
from app.schemas.inventory_tools import (
    InventorySearchFilters,
    InventorySearchResponse,
    InventorySearchVehicle,
    VehicleAvailability,
)
from app.schemas.vehicle import VehicleDetails


class InventoryToolUnavailableError(RuntimeError):
    """Raised when an authoritative tool result cannot be obtained."""


class InventoryVehicleNotFoundError(LookupError):
    """Raised when a requested vehicle ID does not exist."""


def search_inventory(filters: InventorySearchFilters, repository: InventoryRepository) -> InventorySearchResponse:
    try:
        rows = repository.search(filters)
        vehicles = [InventorySearchVehicle.model_validate(row) for row in rows]
    except (InventoryRepositoryError, ValueError):
        raise InventoryToolUnavailableError("Authoritative inventory search failed") from None
    return InventorySearchResponse(count=len(vehicles), vehicles=vehicles)


def get_vehicle_details(vehicle_id: str, repository: InventoryRepository) -> VehicleDetails:
    try:
        row = repository.get(vehicle_id)
    except InventoryRepositoryError:
        raise InventoryToolUnavailableError("Authoritative inventory lookup failed") from None
    if row is None:
        raise InventoryVehicleNotFoundError(vehicle_id)
    try:
        return VehicleDetails.model_validate(row)
    except ValueError:
        raise InventoryToolUnavailableError("Authoritative inventory record is invalid") from None


def check_vehicle_availability(vehicle_id: str, repository: InventoryRepository) -> VehicleAvailability:
    vehicle = get_vehicle_details(vehicle_id, repository)
    can_book = vehicle.vehicle_status in {"Available", "Demo Vehicle"} and vehicle.test_drive_available
    if can_book:
        reason = "Vehicle is currently eligible for test-drive booking."
    elif vehicle.vehicle_status == "Reserved":
        reason = "Vehicle is reserved; offer similar available alternatives."
    elif vehicle.vehicle_status == "Sold":
        reason = "Vehicle is sold; it cannot be recommended as available inventory."
    elif vehicle.vehicle_status == "Arriving Soon":
        reason = "Vehicle is arriving soon and is not yet eligible for a test drive."
    else:
        reason = f"Vehicle status is {vehicle.vehicle_status}; test-drive booking is unavailable."
    return VehicleAvailability(
        vehicle_id=vehicle.vehicle_id,
        vehicle_status=vehicle.vehicle_status,
        test_drive_available=vehicle.test_drive_available,
        can_book_test_drive=can_book,
        reason=reason,
    )
