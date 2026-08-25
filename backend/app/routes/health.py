"""System health routes."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.health import health_status


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return health_status()
