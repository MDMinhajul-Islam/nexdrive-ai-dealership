"""Retell-ready customer history and scheduling endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.database import get_supabase
from app.repositories.customer_tools import CustomerToolsRepository, SupabaseCustomerToolsRepository
from app.schemas.customer_tools import CustomerHistoryResponse, TestDriveSlotQuery, TestDriveSlotsResponse
from app.services.customer_tools import CustomerNotFoundError, CustomerToolsUnavailableError, get_customer_history, get_test_drive_slots

router = APIRouter(prefix="/api/tools", tags=["Customer Tools"])
CustomerId = Annotated[str, Path(pattern=r"^CUST-[0-9]{6}$")]


def get_customer_tools_repository() -> CustomerToolsRepository:
    return SupabaseCustomerToolsRepository(get_supabase())


Repository = Annotated[CustomerToolsRepository, Depends(get_customer_tools_repository)]


@router.get("/get-customer-history/{customer_id}", response_model=CustomerHistoryResponse)
def customer_history_tool(customer_id: CustomerId, repository: Repository) -> CustomerHistoryResponse:
    try:
        return CustomerHistoryResponse(history=get_customer_history(customer_id, repository))
    except CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found") from None
    except CustomerToolsUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Customer service unavailable") from None


@router.get("/get-test-drive-slots", response_model=TestDriveSlotsResponse)
def test_drive_slots_tool(
    repository: Repository,
    start_date: date = Query(...), days: int = Query(7, ge=1, le=14),
    salesperson_id: str | None = Query(None, pattern=r"^SP-[0-9]{3}$"),
    limit: int = Query(20, ge=1, le=50),
) -> TestDriveSlotsResponse:
    try:
        return get_test_drive_slots(TestDriveSlotQuery(
            start_date=start_date, days=days, salesperson_id=salesperson_id, limit=limit,
        ), repository)
    except CustomerToolsUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduling service unavailable") from None
