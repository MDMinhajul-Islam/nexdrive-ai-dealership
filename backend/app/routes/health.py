"""System health routes."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.health import (
    DatabaseUnavailableError,
    database_health_status,
    health_status,
)


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return health_status()


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Supabase is unavailable or is not configured",
        }
    },
)
def database_health() -> DatabaseHealthResponse:
    try:
        return database_health_status()
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "disconnected"},
        ) from None
