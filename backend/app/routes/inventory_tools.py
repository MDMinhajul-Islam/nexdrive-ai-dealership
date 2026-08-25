"""Retell-ready read-only inventory tool endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.database import get_supabase
from app.repositories.inventory import InventoryRepository, SupabaseInventoryRepository
from app.schemas.inventory_tools import (
    InventorySearchFilters,
    InventorySearchResponse,
    ToolVehicleDetailsResponse,
    VehicleAvailabilityResponse,
)
from app.services.inventory_tools import (
    InventoryToolUnavailableError,
    InventoryVehicleNotFoundError,
    check_vehicle_availability,
    get_vehicle_details,
    search_inventory,
)

router = APIRouter(prefix="/api/tools", tags=["Inventory Tools"])
VehicleId = Annotated[str, Path(pattern=r"^VEH-[0-9]{6}$")]


def get_inventory_repository() -> InventoryRepository:
    return SupabaseInventoryRepository(client_factory=get_supabase)


Repository = Annotated[InventoryRepository, Depends(get_inventory_repository)]


def _safe_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InventoryVehicleNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Inventory service unavailable")


@router.post("/search-inventory", response_model=InventorySearchResponse, summary="Search authoritative available inventory")
def search_inventory_tool(filters: InventorySearchFilters, repository: Repository) -> InventorySearchResponse:
    try:
        return search_inventory(filters, repository)
    except InventoryToolUnavailableError as exc:
        raise _safe_error(exc) from None


@router.get("/get-vehicle-details/{vehicle_id}", response_model=ToolVehicleDetailsResponse, summary="Get authoritative vehicle details")
def get_vehicle_details_tool(vehicle_id: VehicleId, repository: Repository) -> ToolVehicleDetailsResponse:
    try:
        return ToolVehicleDetailsResponse(vehicle=get_vehicle_details(vehicle_id, repository))
    except (InventoryVehicleNotFoundError, InventoryToolUnavailableError) as exc:
        raise _safe_error(exc) from None


@router.get("/check-vehicle-availability/{vehicle_id}", response_model=VehicleAvailabilityResponse, summary="Check current vehicle availability")
def check_vehicle_availability_tool(vehicle_id: VehicleId, repository: Repository) -> VehicleAvailabilityResponse:
    try:
        return VehicleAvailabilityResponse(availability=check_vehicle_availability(vehicle_id, repository))
    except (InventoryVehicleNotFoundError, InventoryToolUnavailableError) as exc:
        raise _safe_error(exc) from None
