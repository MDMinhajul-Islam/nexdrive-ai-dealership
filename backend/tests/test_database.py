from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import database
from app.services import health as health_service


@pytest.fixture(autouse=True)
def clear_database_client_cache():
    database.get_supabase.cache_clear()
    yield
    database.get_supabase.cache_clear()


def test_supabase_client_uses_backend_secret_key(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_secret_key="test-secret-key",
    )
    create_client = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "create_client", create_client)

    first_client = database.get_supabase()
    second_client = database.get_supabase()

    assert first_client is second_client
    create_client.assert_called_once_with(
        "https://example.supabase.co", "test-secret-key"
    )


@pytest.mark.parametrize(
    ("missing_field", "expected_name"),
    [
        ("supabase_url", "SUPABASE_URL"),
        ("supabase_publishable_key", "SUPABASE_PUBLISHABLE_KEY"),
        ("supabase_secret_key", "SUPABASE_SECRET_KEY"),
    ],
)
def test_supabase_client_reports_missing_configuration(
    monkeypatch, missing_field: str, expected_name: str
) -> None:
    values = {
        "supabase_url": "https://example.supabase.co",
        "supabase_publishable_key": "test-publishable-key",
        "supabase_secret_key": "test-secret-key",
    }
    values[missing_field] = ""
    monkeypatch.setattr(database, "get_settings", lambda: SimpleNamespace(**values))

    with pytest.raises(database.SupabaseConfigurationError, match=expected_name):
        database.get_supabase()


def test_database_health_queries_only_one_vehicle(monkeypatch) -> None:
    client = MagicMock()
    query = client.table.return_value.select.return_value.limit.return_value
    query.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr(health_service, "get_supabase", lambda: client)

    response = health_service.database_health_status()

    assert response.database == "connected"
    client.table.assert_called_once_with("vehicles")
    client.table.return_value.select.assert_called_once_with("vehicle_id")
    client.table.return_value.select.return_value.limit.assert_called_once_with(1)
    query.execute.assert_called_once_with()
