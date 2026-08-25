from fastapi.testclient import TestClient

from app.main import app
from app.routes import health as health_routes
from app.schemas.health import DatabaseHealthResponse
from app.services.health import DatabaseUnavailableError
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
