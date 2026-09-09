import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import health as health_routes
from app.schemas.health import DatabaseHealthResponse, ReadinessResponse
from app.services.health import (
    DatabaseUnavailableError,
    ReadinessConfigurationError,
    readiness_status,
)
from app.utils.config import Settings


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "NexDrive API",
        "environment": "development",
    }


def test_supabase_uses_new_setting_names() -> None:
    fields = Settings.model_fields
    assert "supabase_publishable_key" in fields
    assert "supabase_secret_key" in fields
    assert "supabase_anon_key" not in fields
    assert "supabase_service_role_key" not in fields


def test_database_health_success(monkeypatch) -> None:
    monkeypatch.setattr(
        health_routes,
        "database_health_status",
        lambda: DatabaseHealthResponse(),
    )

    response = client.get("/health/database")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "source": "supabase",
    }


def test_database_health_failure_is_safe(monkeypatch) -> None:
    def unavailable() -> DatabaseHealthResponse:
        raise DatabaseUnavailableError("provider details must stay private")

    monkeypatch.setattr(health_routes, "database_health_status", unavailable)

    response = client.get("/health/database")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"status": "error", "database": "disconnected"}
    }
    assert "provider details" not in response.text


def test_production_readiness_accepts_complete_configuration() -> None:
    response = readiness_status(Settings(
        app_env="production",
        supabase_url="https://database.example",
        supabase_publishable_key="public-key",
        supabase_secret_key="database-secret",
        retell_api_key="retell-secret",
        retell_agent_id="agent-123",
        retell_tool_api_key="tool-secret",
        admin_auth_required=True,
        cors_origins="https://nexdrive.example",
    ))

    assert response == ReadinessResponse(checks={
        "database_configuration": "ok",
        "retell_configuration": "ok",
        "tool_authentication": "ok",
        "production_security": "ok",
    })


def test_readiness_detects_missing_production_configuration() -> None:
    with pytest.raises(ReadinessConfigurationError) as caught:
        readiness_status(Settings(
            app_env="production",
            supabase_url="",
            supabase_publishable_key="",
            supabase_secret_key="",
            retell_api_key="",
            retell_agent_id="",
            retell_tool_api_key="",
            admin_auth_required=False,
            cors_origins="*",
        ))

    assert caught.value.checks == {
        "database_configuration": "error",
        "retell_configuration": "error",
        "tool_authentication": "error",
        "production_security": "error",
    }


def test_missing_production_configuration_fails_safely(monkeypatch) -> None:
    def not_ready() -> ReadinessResponse:
        raise ReadinessConfigurationError({
            "database_configuration": "error",
            "retell_configuration": "error",
            "tool_authentication": "error",
            "production_security": "error",
        })

    monkeypatch.setattr(health_routes, "readiness_status", not_ready)
    response = client.get("/health/readiness")

    assert response.status_code == 503
    assert response.json() == {"detail": {
        "status": "not_ready",
        "checks": {
            "database_configuration": "error",
            "retell_configuration": "error",
            "tool_authentication": "error",
            "production_security": "error",
        },
    }}
    assert "secret" not in response.text.casefold()
