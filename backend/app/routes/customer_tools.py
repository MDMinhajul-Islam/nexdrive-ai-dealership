"""Retell-ready customer history and scheduling endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, status

from app.database import get_supabase
from app.repositories.customer_tools import CustomerToolsRepository, SupabaseCustomerToolsRepository
from app.repositories.inventory import InventoryRepository, SupabaseInventoryRepository
from app.schemas.customer_tools import (
    CustomerHistoryRequest,
    CustomerHistoryResponse,
    TestDriveSlotDiscoveryRequest,
    TestDriveSlotQuery,
    TestDriveSlotsResponse,
)
from app.services.customer_tools import CustomerNotFoundError, CustomerToolsUnavailableError, get_customer_history, get_test_drive_slots
from app.services.inventory_tools import (
    InventoryToolUnavailableError,
    InventoryVehicleNotFoundError,
    check_vehicle_availability,
)
from app.tool_auth import require_retell_tool_auth, require_verified_customer_identity
from app.utils.tool_errors import ToolAPIError

router = APIRouter(
    prefix="/api/tools",
    tags=["Customer Tools"],
    dependencies=[Depends(require_retell_tool_auth)],
)
CustomerId = Annotated[str, Path(pattern=r"^CUST-[0-9]{6}$")]
VerifiedCustomerId = Annotated[
    str | None,
    Header(alias="X-Retell-Verified-Customer-ID", pattern=r"^CUST-[0-9]{6}$"),
]


def get_customer_tools_repository() -> CustomerToolsRepository:
    return SupabaseCustomerToolsRepository(get_supabase())


Repository = Annotated[CustomerToolsRepository, Depends(get_customer_tools_repository)]


def get_test_drive_inventory_repository() -> InventoryRepository:
    return SupabaseInventoryRepository(client_factory=get_supabase)


InventoryRepositoryDependency = Annotated[
    InventoryRepository, Depends(get_test_drive_inventory_repository)
]


@router.get("/get-customer-history/{customer_id}", response_model=CustomerHistoryResponse)
def customer_history_tool(
    customer_id: CustomerId,
    repository: Repository,
    verified_customer_id: VerifiedCustomerId = None,
) -> CustomerHistoryResponse:
    require_verified_customer_identity(customer_id, verified_customer_id)
    return _customer_history_response(customer_id, repository)


def _customer_history_response(
    customer_id: str, repository: CustomerToolsRepository
) -> CustomerHistoryResponse:
    try:
        return CustomerHistoryResponse(history=get_customer_history(customer_id, repository))
    except CustomerNotFoundError:
        raise ToolAPIError(status.HTTP_404_NOT_FOUND, "CUSTOMER_NOT_FOUND", False, "Customer not found") from None
    except CustomerToolsUnavailableError:
        raise ToolAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CUSTOMER_HISTORY_UNAVAILABLE",
            True,
            "Customer history is temporarily unavailable",
        ) from None


@router.post("/get-customer-history", response_model=CustomerHistoryResponse)
def customer_history_post_tool(
    request: CustomerHistoryRequest,
    repository: Repository,
    verified_customer_id: VerifiedCustomerId = None,
) -> CustomerHistoryResponse:
    """Retell-friendly, read-only customer history lookup."""
    require_verified_customer_identity(request.customer_id, verified_customer_id)
    return _customer_history_response(request.customer_id, repository)


@router.get("/get-test-drive-slots", response_model=TestDriveSlotsResponse)
def test_drive_slots_tool(
    repository: Repository,
    inventory_repository: InventoryRepositoryDependency,
    vehicle_id: str = Query(..., pattern=r"^VEH-[0-9]{6}$"),
    requested_date: date = Query(...),
    days: int = Query(7, ge=1, le=14),
    salesperson_id: str | None = Query(None, pattern=r"^SP-[0-9]{3}$"),
    limit: int = Query(20, ge=1, le=50),
) -> TestDriveSlotsResponse:
    if requested_date < date.today():
        raise ToolAPIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PAST_REQUESTED_DATE",
            False,
            "Requested test-drive date cannot be in the past",
        )
    request = TestDriveSlotDiscoveryRequest(
        vehicle_id=vehicle_id,
        requested_date=requested_date,
        days=days,
        salesperson_id=salesperson_id,
        limit=limit,
    )
    return _vehicle_test_drive_slots_response(
        request,
        repository,
        inventory_repository,
    )


def _test_drive_slots_response(
    query: TestDriveSlotQuery, repository: CustomerToolsRepository
) -> TestDriveSlotsResponse:
    try:
        return get_test_drive_slots(query, repository)
    except CustomerToolsUnavailableError:
        raise ToolAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SCHEDULING_UNAVAILABLE",
            True,
            "Test-drive scheduling is temporarily unavailable",
        ) from None


def _vehicle_test_drive_slots_response(
    request: TestDriveSlotDiscoveryRequest,
    repository: CustomerToolsRepository,
    inventory_repository: InventoryRepository,
) -> TestDriveSlotsResponse:
    try:
        availability = check_vehicle_availability(request.vehicle_id, inventory_repository)
    except InventoryVehicleNotFoundError:
        raise ToolAPIError(
            status.HTTP_404_NOT_FOUND, "VEHICLE_NOT_FOUND", False, "Vehicle not found"
        ) from None
    except InventoryToolUnavailableError:
        raise ToolAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "INVENTORY_UNAVAILABLE",
            True,
            "Live inventory is temporarily unavailable",
        ) from None

    if not availability.can_book_test_drive:
        raise ToolAPIError(
            status.HTTP_409_CONFLICT,
            "VEHICLE_NOT_AVAILABLE_FOR_TEST_DRIVE",
            False,
            "This vehicle is not currently available for a test drive",
        )
    return _test_drive_slots_response(request, repository)


@router.post("/get-test-drive-slots", response_model=TestDriveSlotsResponse)
def test_drive_slots_post_tool(
    request: TestDriveSlotDiscoveryRequest,
    repository: Repository,
    inventory_repository: InventoryRepositoryDependency,
) -> TestDriveSlotsResponse:
    """Retell-friendly, read-only vehicle-specific test-drive slot discovery."""
    return _vehicle_test_drive_slots_response(
        request, repository, inventory_repository
    )
