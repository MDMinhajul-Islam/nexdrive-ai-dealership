"""Health-check service."""

from app.database import get_supabase
from app.schemas.health import DatabaseHealthResponse, HealthResponse, ReadinessResponse
from app.utils.config import Settings, get_settings


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database connectivity check cannot complete."""


class ReadinessConfigurationError(RuntimeError):
    """Raised when a required production configuration group is incomplete."""

    def __init__(self, checks: dict[str, str]):
        super().__init__("Required production configuration is incomplete")
        self.checks = checks


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


def readiness_status(settings: Settings | None = None) -> ReadinessResponse:
    """Validate production-critical configuration without exposing its values."""
    settings = settings or get_settings()
    checks = {
        "database_configuration": bool(
            settings.supabase_url
            and settings.supabase_publishable_key
            and settings.supabase_secret_key
        ),
        "retell_configuration": bool(
            settings.retell_api_key and settings.retell_agent_id
        ),
        "tool_authentication": bool(settings.retell_tool_api_key),
    }
    if settings.app_env.strip().casefold() == "production":
        configured_origins = {
            origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
        }
        checks["production_security"] = bool(
            settings.admin_auth_required and "*" not in configured_origins
        )

    safe_checks = {
        name: "ok" if configured else "error"
        for name, configured in checks.items()
    }
    if not all(checks.values()):
        raise ReadinessConfigurationError(safe_checks)
    return ReadinessResponse(checks={name: "ok" for name in checks})
