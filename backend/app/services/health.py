"""Health-check service."""

from app.schemas.health import HealthResponse
from app.utils.config import get_settings


def health_status() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(service=settings.app_name, environment=settings.app_env)
