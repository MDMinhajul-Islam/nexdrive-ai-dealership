"""Retell-ready lead, booking, and financing endpoints."""

import logging
import time as clock

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.database import get_supabase
from app.schemas.business_tools import *
from app.services.business_tools import *
from app.tool_auth import require_retell_tool_auth
from app.utils.tool_errors import ToolAPIError

logger = logging.getLogger("nexdrive.audit")

router = APIRouter(
    prefix="/api/tools",
    tags=["Business Tools"],
    dependencies=[Depends(require_retell_tool_auth)],
)


def get_business_client() -> Client:
    return get_supabase()


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, BusinessNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ExistingAppointmentConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.details)
    if isinstance(exc, BusinessConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Business tool unavailable")


def _booking_error(exc: Exception) -> ToolAPIError:
    if isinstance(exc, AppointmentSlotUnavailableError):
        return ToolAPIError(
            status.HTTP_409_CONFLICT,
            "APPOINTMENT_SLOT_UNAVAILABLE",
            True,
            "The requested appointment time is no longer available",
        )
    if isinstance(exc, BusinessNotFoundError):
        return ToolAPIError(
            status.HTTP_404_NOT_FOUND,
            exc.error_code,
            False,
            str(exc),
        )
    if isinstance(exc, ExistingAppointmentConflictError):
        return ToolAPIError(
            status.HTTP_409_CONFLICT,
            "EXISTING_APPOINTMENT_CONFLICT",
            False,
            str(exc),
        )
    if isinstance(exc, BusinessConflictError):
        return ToolAPIError(
            status.HTTP_409_CONFLICT,
            exc.error_code,
            exc.retryable,
            str(exc),
        )
    return ToolAPIError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "BOOKING_UNAVAILABLE",
        True,
        "Test-drive booking is temporarily unavailable",
    )


@router.post("/create-or-update-lead", response_model=LeadResponse)
def lead_tool(request: LeadUpsertRequest, client: Client = Depends(get_business_client)) -> LeadResponse:
    try: return create_or_update_lead(request, client)
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc: raise _error(exc) from None


@router.post("/create-test-drive", response_model=BookingResponse, summary="Create an authoritative test-drive appointment")
def booking_tool(request: BookingRequest, client: Client = Depends(get_business_client)) -> BookingResponse:
    started = clock.perf_counter()
    try:
        response = create_test_drive(request, client)
        logger.info(
            "booking_tool vehicle_id=%s appointment_date=%s appointment_time=%s success=True created=%s error_code=none duration_ms=%.2f",
            request.vehicle_id,
            request.appointment_date.isoformat(),
            request.appointment_time.strftime("%H:%M:%S"),
            response.created,
            (clock.perf_counter() - started) * 1000,
        )
        return response
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc:
        error = _booking_error(exc)
        logger.warning(
            "booking_tool vehicle_id=%s appointment_date=%s appointment_time=%s success=False error_code=%s duration_ms=%.2f",
            request.vehicle_id,
            request.appointment_date.isoformat(),
            request.appointment_time.strftime("%H:%M:%S"),
            error.error_code,
            (clock.perf_counter() - started) * 1000,
        )
        raise error from None


@router.post("/estimate-financing", response_model=FinancingEstimateResponse)
def financing_tool(request: FinancingEstimateRequest, client: Client = Depends(get_business_client)) -> FinancingEstimateResponse:
    try: return estimate_financing(request, client)
    except (BusinessToolError, BusinessNotFoundError, BusinessConflictError) as exc: raise _error(exc) from None
