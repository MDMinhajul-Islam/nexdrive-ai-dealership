"""API request and response schemas."""

from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.schemas.vehicle import VehicleDetails, VehicleDetailsResponse

__all__ = [
    "DatabaseHealthResponse",
    "HealthResponse",
    "VehicleDetails",
    "VehicleDetailsResponse",
]
