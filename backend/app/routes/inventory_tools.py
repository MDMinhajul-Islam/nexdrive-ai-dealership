from app.schemas.inventory_tools import RetellInventorySearchVehicle
"""Retell-ready read-only inventory tool endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.database import get_supabase
from app.repositories.inventory import InventoryRepository, SupabaseInventoryRepository
from app.schemas.inventory_tools import (
    InventorySearchFilters,
    RetellInventorySearchResponse,
    VehicleDetailsRequest,
    RetellToolVehicleDetailsResponse,
    VehicleAvailabilityResponse,
)
from app.services.inventory_tools import (
    InventoryToolUnavailableError,
    InventoryVehicleNotFoundError,
    check_vehicle_availability,
    get_vehicle_details,
    search_inventory,
)

import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.routing import APIRoute
from app.utils.timing import timing_data_ctx

logger = logging.getLogger("nexdrive.inventory.timing")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

class TimingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original = super().get_route_handler()
        async def custom(request: Request) -> Response:
            if not request.url.path.endswith("/search-inventory"):
                return await original(request)
                
            t_start = time.perf_counter()
            timing_data_ctx.set({"normalization": 0.0, "db": 0.0, "response_build": 0.0})
            request.state.failed_stage = "validation"
            
            try:
                response = await original(request)
                
                total_ms = (time.perf_counter() - t_start) * 1000.0
                timing_data = timing_data_ctx.get()
                db_ms = timing_data["db"] * 1000.0
                norm_ms = timing_data["normalization"] * 1000.0
                resp_ms = timing_data["response_build"] * 1000.0
                # validation is whatever remains since the start, excluding norm, db, and resp.
                val_ms = total_ms - db_ms - norm_ms - resp_ms
                if val_ms < 0: val_ms = 0.0
                
                count = getattr(request.state, "inventory_count", 0)
                
                logger.info(f"search_inventory timing total_ms={total_ms:.1f} validation_ms={val_ms:.1f} normalization_ms={norm_ms:.1f} db_ms={db_ms:.1f} response_build_ms={resp_ms:.1f} count={count}")
                return response
            except Exception as e:
                total_ms = (time.perf_counter() - t_start) * 1000.0
                stage = getattr(request.state, "failed_stage", "validation")
                logger.info(f"search_inventory timing total_ms={total_ms:.1f} failed_stage={stage}")
                raise
        return custom

from app.tool_auth import require_retell_tool_auth
from app.utils.tool_errors import ToolAPIError

router = APIRouter(
    route_class=TimingRoute,
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


def _vehicle_details_response(vehicle_id: str, repository: InventoryRepository) -> RetellToolVehicleDetailsResponse:
    try:
        return RetellToolVehicleDetailsResponse(vehicle=RetellInventorySearchVehicle.model_validate(get_vehicle_details(vehicle_id, repository).model_dump(), from_attributes=True))
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
def search_inventory_tool(request: Request, filters: InventorySearchFilters, repository: Repository) -> RetellInventorySearchResponse:
    request.state.failed_stage = 'database'
    if not filters.has_meaningful_criteria():
        raise ToolAPIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "MISSING_SEARCH_CRITERIA",
            False,
            "Vehicle search requires customer preferences",
        )
    try:
        result = search_inventory(filters, repository)
        request.state.inventory_count = result.count
        request.state.failed_stage = 'response_build'
        return RetellInventorySearchResponse.from_inventory_response(result)
    except InventoryToolUnavailableError as exc:
        raise _safe_error(exc) from None


@router.get("/get-vehicle-details/{vehicle_id}", response_model=RetellToolVehicleDetailsResponse, summary="Get authoritative vehicle details")
def get_vehicle_details_tool(vehicle_id: VehicleId, repository: Repository) -> RetellToolVehicleDetailsResponse:
    return _vehicle_details_response(vehicle_id, repository)


@router.get("/get-vehicle-details", response_model=RetellToolVehicleDetailsResponse, summary="Get authoritative vehicle details by query parameter")
def get_vehicle_details_query_tool(vehicle_id: VehicleIdQuery, repository: Repository) -> RetellToolVehicleDetailsResponse:
    """Retell-friendly alias for clients that supply vehicle_id as a query parameter."""
    return _vehicle_details_response(vehicle_id, repository)


@router.post("/get-vehicle-details", response_model=RetellToolVehicleDetailsResponse, summary="Get authoritative vehicle details by JSON body")
def get_vehicle_details_post_tool(request: VehicleDetailsRequest, repository: Repository) -> RetellToolVehicleDetailsResponse:
    """Retell-friendly alias for clients that send vehicle_id in a JSON body."""
    return _vehicle_details_response(request.vehicle_id, repository)


@router.get("/check-vehicle-availability/{vehicle_id}", response_model=VehicleAvailabilityResponse, summary="Check current vehicle availability")
def check_vehicle_availability_tool(vehicle_id: VehicleId, repository: Repository) -> VehicleAvailabilityResponse:
    return _vehicle_availability_response(vehicle_id, repository)


@router.post("/check-vehicle-availability", response_model=VehicleAvailabilityResponse, summary="Check vehicle availability by JSON body")
def check_vehicle_availability_post_tool(request: VehicleDetailsRequest, repository: Repository) -> VehicleAvailabilityResponse:
    """Retell-friendly alias for clients that send vehicle_id in a JSON body."""
    return _vehicle_availability_response(request.vehicle_id, repository)
