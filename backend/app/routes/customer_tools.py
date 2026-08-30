"""Retell-ready customer history and scheduling endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

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

router = APIRouter(prefix="/api/tools", tags=["Customer Tools"])
CustomerId = Annotated[str, Path(pattern=r"^CUST-[0-9]{6}$")]


def get_customer_tools_repository() -> CustomerToolsRepository:
    return SupabaseCustomerToolsRepository(get_supabase())


Repository = Annotated[CustomerToolsRepository, Depends(get_customer_tools_repository)]


def get_test_drive_inventory_repository() -> InventoryRepository:
    return SupabaseInventoryRepository(client_factory=get_supabase)


InventoryRepositoryDependency = Annotated[
    InventoryRepository, Depends(get_test_drive_inventory_repository)
]


@router.get("/get-customer-history/{customer_id}", response_model=CustomerHistoryResponse)
def customer_history_tool(customer_id: CustomerId, repository: Repository) -> CustomerHistoryResponse:
    return _customer_history_response(customer_id, repository)


def _customer_history_response(
    customer_id: str, repository: CustomerToolsRepository
) -> CustomerHistoryResponse:
    try:
        return CustomerHistoryResponse(history=get_customer_history(customer_id, repository))
    except CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found") from None
    except CustomerToolsUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Customer service unavailable") from None


@router.post("/get-customer-history", response_model=CustomerHistoryResponse)
def customer_history_post_tool(
    request: CustomerHistoryRequest, repository: Repository
) -> CustomerHistoryResponse:
    """Retell-friendly, read-only customer history lookup."""
    return _customer_history_response(request.customer_id, repository)


@router.get("/get-test-drive-slots", response_model=TestDriveSlotsResponse)
def test_drive_slots_tool(
    repository: Repository,
    start_date: date = Query(...), days: int = Query(7, ge=1, le=14),
    salesperson_id: str | None = Query(None, pattern=r"^SP-[0-9]{3}$"),
    limit: int = Query(20, ge=1, le=50),
) -> TestDriveSlotsResponse:
    return _test_drive_slots_response(
        TestDriveSlotQuery(
            start_date=start_date,
            days=days,
            salesperson_id=salesperson_id,
            limit=limit,
        ),
        repository,
    )


def _test_drive_slots_response(
    query: TestDriveSlotQuery, repository: CustomerToolsRepository
) -> TestDriveSlotsResponse:
    try:
        return get_test_drive_slots(query, repository)
    except CustomerToolsUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduling service unavailable") from None


@router.post("/get-test-drive-slots", response_model=TestDriveSlotsResponse)
def test_drive_slots_post_tool(
    request: TestDriveSlotDiscoveryRequest,
    repository: Repository,
    inventory_repository: InventoryRepositoryDependency,
) -> TestDriveSlotsResponse:
    """Retell-friendly, read-only vehicle-specific test-drive slot discovery."""
    try:
        availability = check_vehicle_availability(
            request.vehicle_id, inventory_repository
        )
    except InventoryVehicleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found") from None
    except InventoryToolUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Inventory service unavailable") from None

    if not availability.can_book_test_drive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "vehicle_id": availability.vehicle_id,
                "vehicle_status": availability.vehicle_status,
                "reason": availability.reason,
            },
        )

    return _test_drive_slots_response(request, repository)
