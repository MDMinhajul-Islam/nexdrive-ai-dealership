"""Vehicle detail routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas.vehicle import VehicleDetailsResponse
from app.services.vehicles import (
    VehicleDatabaseError,
    VehicleNotFoundError,
    get_vehicle_details,
)


router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])
VehicleId = Annotated[
    str,
    Path(
        pattern=r"^VEH-[0-9]{6}$",
        description="NexDrive vehicle identifier, for example VEH-000001",
    ),
]


@router.get(
    "/{vehicle_id}",
    response_model=VehicleDetailsResponse,
    summary="Get authoritative vehicle details",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Vehicle not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Vehicle database is unavailable",
        },
    },
)
def vehicle_details(vehicle_id: VehicleId) -> VehicleDetailsResponse:
    try:
        vehicle = get_vehicle_details(vehicle_id)
    except VehicleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found",
        ) from None
    except VehicleDatabaseError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vehicle service unavailable",
        ) from None

    return VehicleDetailsResponse(vehicle=vehicle)
