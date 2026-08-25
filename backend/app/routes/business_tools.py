"""Retell-ready lead, booking, and financing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.database import get_supabase
from app.schemas.business_tools import *
from app.services.business_tools import *

router = APIRouter(prefix="/api/tools", tags=["Business Tools"])


def get_business_client() -> Client:
    return get_supabase()


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, BusinessNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, BusinessConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Business tool unavailable")


@router.post("/create-or-update-lead", response_model=LeadResponse)
def lead_tool(request: LeadUpsertRequest, client: Client = Depends(get_business_client)) -> LeadResponse:
    try: return create_or_update_lead(request, client)
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc: raise _error(exc) from None


@router.post("/create-test-drive", response_model=BookingResponse)
def booking_tool(request: BookingRequest, client: Client = Depends(get_business_client)) -> BookingResponse:
    try: return create_test_drive(request, client)
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc: raise _error(exc) from None


@router.post("/estimate-financing", response_model=FinancingEstimateResponse)
def financing_tool(request: FinancingEstimateRequest, client: Client = Depends(get_business_client)) -> FinancingEstimateResponse:
    try: return estimate_financing(request, client)
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc: raise _error(exc) from None
