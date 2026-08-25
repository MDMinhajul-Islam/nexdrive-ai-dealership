"""Health-check service."""

from app.database import get_supabase
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.utils.config import get_settings


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database connectivity check cannot complete."""


def health_status() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(service=settings.app_name, environment=settings.app_env)


def database_health_status() -> DatabaseHealthResponse:
    """Prove Supabase connectivity with a single-row query."""
    try:
        (
            get_supabase()
            .table("vehicles")
            .select("vehicle_id")
            .limit(1)
            .execute()
        )
    except Exception:
        # Provider errors may contain request or connection details, so keep
        # them out of the public API response.
        raise DatabaseUnavailableError("Supabase database is unavailable") from None

    return DatabaseHealthResponse()
