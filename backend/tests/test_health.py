from fastapi.testclient import TestClient

from app.main import app
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
