"""Retell-ready read-only inventory tool endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.database import get_supabase
from app.repositories.inventory import InventoryRepository, SupabaseInventoryRepository
from app.schemas.inventory_tools import (
    InventorySearchFilters,
    RetellInventorySearchResponse,
    VehicleDetailsRequest,
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
from app.tool_auth import require_retell_tool_auth
from app.utils.tool_errors import ToolAPIError

router = APIRouter(
    prefix="/api/tools",
    tags=["Inventory Tools"],
    dependencies=[Depends(require_retell_tool_auth)],
)
VehicleId = Annotated[str, Path(pattern=r"^VEH-[0-9]{6}$")]
VehicleIdQuery = Annotated[str, Query(pattern=r"^VEH-[0-9]{6}$")]


def get_inventory_repository() -> InventoryRepository:
    return SupabaseInventoryRepository(client_factory=get_supabase)


Repository = Annotated[InventoryRepository, Depends(get_inventory_repository)]


def _safe_error(exc: Exception) -> ToolAPIError:
    if isinstance(exc, InventoryVehicleNotFoundError):
        return ToolAPIError(status.HTTP_404_NOT_FOUND, "VEHICLE_NOT_FOUND", False, "Vehicle not found")
    return ToolAPIError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "INVENTORY_UNAVAILABLE",
        True,
        "Live inventory is temporarily unavailable",
    )


def _vehicle_details_response(vehicle_id: str, repository: InventoryRepository) -> ToolVehicleDetailsResponse:
    try:
        return ToolVehicleDetailsResponse(vehicle=get_vehicle_details(vehicle_id, repository))
    except (InventoryVehicleNotFoundError, InventoryToolUnavailableError) as exc:
        raise _safe_error(exc) from None


def _vehicle_availability_response(vehicle_id: str, repository: InventoryRepository) -> VehicleAvailabilityResponse:
    try:
        return VehicleAvailabilityResponse(
            availability=check_vehicle_availability(vehicle_id, repository)
        )
    except (InventoryVehicleNotFoundError, InventoryToolUnavailableError) as exc:
        raise _safe_error(exc) from None


@router.post("/search-inventory", response_model=RetellInventorySearchResponse, summary="Search authoritative available inventory")
def search_inventory_tool(filters: InventorySearchFilters, repository: Repository) -> RetellInventorySearchResponse:
    if not filters.has_meaningful_criteria():
        raise ToolAPIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "MISSING_SEARCH_CRITERIA",
            False,
            "Vehicle search requires customer preferences",
        )
    try:
        result = search_inventory(filters, repository)
        return RetellInventorySearchResponse.from_inventory_response(result)
    except InventoryToolUnavailableError as exc:
        raise _safe_error(exc) from None


@router.get("/get-vehicle-details/{vehicle_id}", response_model=ToolVehicleDetailsResponse, summary="Get authoritative vehicle details")
def get_vehicle_details_tool(vehicle_id: VehicleId, repository: Repository) -> ToolVehicleDetailsResponse:
    return _vehicle_details_response(vehicle_id, repository)


@router.get("/get-vehicle-details", response_model=ToolVehicleDetailsResponse, summary="Get authoritative vehicle details by query parameter")
def get_vehicle_details_query_tool(vehicle_id: VehicleIdQuery, repository: Repository) -> ToolVehicleDetailsResponse:
    """Retell-friendly alias for clients that supply vehicle_id as a query parameter."""
    return _vehicle_details_response(vehicle_id, repository)


@router.post("/get-vehicle-details", response_model=ToolVehicleDetailsResponse, summary="Get authoritative vehicle details by JSON body")
def get_vehicle_details_post_tool(request: VehicleDetailsRequest, repository: Repository) -> ToolVehicleDetailsResponse:
    """Retell-friendly alias for clients that send vehicle_id in a JSON body."""
    return _vehicle_details_response(request.vehicle_id, repository)


@router.get("/check-vehicle-availability/{vehicle_id}", response_model=VehicleAvailabilityResponse, summary="Check current vehicle availability")
def check_vehicle_availability_tool(vehicle_id: VehicleId, repository: Repository) -> VehicleAvailabilityResponse:
    return _vehicle_availability_response(vehicle_id, repository)


@router.post("/check-vehicle-availability", response_model=VehicleAvailabilityResponse, summary="Check vehicle availability by JSON body")
def check_vehicle_availability_post_tool(request: VehicleDetailsRequest, repository: Repository) -> VehicleAvailabilityResponse:
    """Retell-friendly alias for clients that send vehicle_id in a JSON body."""
    return _vehicle_availability_response(request.vehicle_id, repository)
