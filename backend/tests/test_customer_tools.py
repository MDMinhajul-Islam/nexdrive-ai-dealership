from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.customer_tools import CustomerToolsRepositoryError
from app.repositories.inventory import CsvInventoryRepository
from app.routes import customer_tools as customer_tool_routes
from app.routes.customer_tools import (
    get_customer_tools_repository,
    get_test_drive_inventory_repository,
)
from app.schemas import customer_tools as customer_tool_schemas
from app.schemas.customer_tools import TestDriveSlotQuery as SlotQuery
from app.services import customer_tools as customer_tools_service
from app.services.customer_tools import (
    CustomerToolsUnavailableError,
    get_customer_history,
    get_test_drive_slots,
)
from app.services.inventory_tools import InventoryToolUnavailableError

TOOL_HEADERS = {"X-Retell-Tool-Key": "test-retell-tool-key"}


def verified_customer(customer_id: str) -> dict[str, str]:
    return {"X-Retell-Verified-Customer-ID": customer_id}


class FakeRepository:
    def customer_history(self, customer_id):
        if customer_id != "CUST-000001":
            return None
        return {
            "customer": {"customer_id": customer_id, "first_name": "Avery"},
            "leads": [{"lead_id": "LEAD-000001", "customer_id": customer_id}],
            "appointments": [{"appointment_id": "APT-000001", "customer_id": customer_id}],
        }

    def salespeople(self, salesperson_id=None):
        people = [{
            "salesperson_id": "SP-001", "name": "Jordan Ellis", "active": True,
            "working_days": ["Tuesday"], "shift_start": "09:00:00", "shift_end": "10:30:00",
        }]
        return [p for p in people if salesperson_id is None or p["salesperson_id"] == salesperson_id]

    def appointments_between(self, start, end):
        return [{
            "salesperson_id": "SP-001", "appointment_date": "2099-09-01",
            "appointment_time": "09:30:00", "status": "Confirmed",
        }]


class EmptyHistoryRepository(FakeRepository):
    def customer_history(self, customer_id):
        if customer_id != "CUST-000002":
            return None
        return {
            "customer": {"customer_id": customer_id, "first_name": "Morgan"},
            "leads": [],
            "appointments": [],
        }


class FailingHistoryRepository(FakeRepository):
    def customer_history(self, customer_id):
        raise CustomerToolsRepositoryError("provider details must stay private")


class SameDaySchedulingRepository(FakeRepository):
    def salespeople(self, salesperson_id=None):
        people = [{
            "salesperson_id": "SP-001", "name": "Jordan Ellis", "active": True,
            "working_days": ["Saturday"], "shift_start": "13:00:00", "shift_end": "16:00:00",
        }]
        return [person for person in people if salesperson_id is None or person["salesperson_id"] == salesperson_id]

    def appointments_between(self, start, end):
        return []


class NoSameDaySlotsRepository(SameDaySchedulingRepository):
    def salespeople(self, salesperson_id=None):
        return [{
            "salesperson_id": "SP-001", "name": "Jordan Ellis", "active": True,
            "working_days": ["Saturday"], "shift_start": "14:30:00", "shift_end": "15:00:00",
        }]

    def appointments_between(self, start, end):
        return [{
            "salesperson_id": "SP-001", "appointment_date": "2026-09-12",
            "appointment_time": "14:30:00", "status": "Confirmed",
        }]


class FailingSchedulingRepository(FakeRepository):
    def salespeople(self, salesperson_id=None):
        raise CustomerToolsRepositoryError("Salesperson schedule lookup failed")


def test_customer_history_returns_related_records():
    result = get_customer_history("CUST-000001", FakeRepository())
    assert result.customer["customer_id"] == "CUST-000001"
    assert result.leads[0]["lead_id"] == "LEAD-000001"
    assert result.appointments[0]["appointment_id"] == "APT-000001"


def test_slots_follow_shift_and_exclude_booked_time():
    result = get_test_drive_slots(SlotQuery(
        requested_date=date(2099, 9, 1), days=1, salesperson_id="SP-001", limit=10,
    ), FakeRepository())
    assert [slot.appointment_time.strftime("%H:%M") for slot in result.slots] == ["09:00", "10:00"]


def test_same_day_slots_use_texas_time_exclude_past_and_keep_future(monkeypatch):
    texas_time = datetime(2026, 9, 12, 14, 5, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(customer_tool_schemas, "dealership_today", lambda: texas_time.date())
    monkeypatch.setattr(customer_tools_service, "dealership_now", lambda: texas_time)

    result = get_test_drive_slots(
        SlotQuery(requested_date=date(2026, 9, 12), days=1, limit=20),
        SameDaySchedulingRepository(),
    )

    times = [slot.appointment_time.strftime("%H:%M") for slot in result.slots]
    assert times == ["14:30", "15:00", "15:30"]
    assert all(slot.appointment_time.minute in {0, 30} for slot in result.slots)


def test_same_day_slots_exclude_230_when_it_has_already_passed(monkeypatch):
    texas_time = datetime(2026, 9, 12, 14, 31, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(customer_tool_schemas, "dealership_today", lambda: texas_time.date())
    monkeypatch.setattr(customer_tools_service, "dealership_now", lambda: texas_time)

    result = get_test_drive_slots(
        SlotQuery(requested_date=date(2026, 9, 12), days=1, limit=20),
        SameDaySchedulingRepository(),
    )

    assert [slot.appointment_time.strftime("%H:%M") for slot in result.slots] == ["15:00", "15:30"]


def test_no_same_day_slots_is_a_successful_empty_response(monkeypatch):
    texas_time = datetime(2026, 9, 12, 14, 5, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(customer_tool_schemas, "dealership_today", lambda: texas_time.date())
    monkeypatch.setattr(customer_tools_service, "dealership_now", lambda: texas_time)

    result = get_test_drive_slots(
        SlotQuery(requested_date=date(2026, 9, 12), days=1, limit=20),
        NoSameDaySlotsRepository(),
    )

    assert result.success is True
    assert result.count == 0
    assert result.slots == []
    assert result.message == "No test-drive slots are available for that date."


def test_scheduling_repository_failure_keeps_internal_cause_for_logging():
    with pytest.raises(CustomerToolsUnavailableError) as error:
        get_test_drive_slots(
            SlotQuery(requested_date=date(2099, 9, 1), days=1, limit=20),
            FailingSchedulingRepository(),
        )

    assert isinstance(error.value.__cause__, CustomerToolsRepositoryError)


@pytest.mark.parametrize("date_field", ["requested_date", "start_date"])
def test_production_vehicle_slot_route_accepts_both_date_fields(monkeypatch, date_field):
    texas_time = datetime(2026, 9, 12, 14, 5, tzinfo=ZoneInfo("America/Chicago"))
    monkeypatch.setattr(customer_tool_schemas, "dealership_today", lambda: texas_time.date())
    monkeypatch.setattr(customer_tools_service, "dealership_now", lambda: texas_time)
    inventory = CsvInventoryRepository(
        Path(__file__).resolve().parents[2] / "database" / "seed"
    )
    app.dependency_overrides[get_customer_tools_repository] = SameDaySchedulingRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-test-drive-slots",
            json={
                "vehicle_id": "VEH-004163",
                date_field: "2026-09-12",
                "days": 1,
                "limit": 20,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["count"] == 3
        assert [slot["appointment_time"] for slot in payload["slots"]] == [
            "14:30:00", "15:00:00", "15:30:00",
        ]
    finally:
        app.dependency_overrides.clear()


def test_post_rejects_dates_past_in_texas(monkeypatch):
    monkeypatch.setattr(customer_tool_schemas, "dealership_today", lambda: date(2026, 9, 12))

    response = TestClient(app, headers=TOOL_HEADERS).post(
        "/api/tools/get-test-drive-slots",
        json={"vehicle_id": "VEH-000001", "requested_date": "2026-09-11"},
    )

    assert response.status_code == 422


def test_slot_route_returns_sanitized_503_and_logs_repository_failure(caplog):
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FailingSchedulingRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    caplog.set_level("ERROR", logger="app.services.customer_tools")
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-test-drive-slots",
            json={"vehicle_id": "VEH-000001", "requested_date": "2099-09-01"},
        )
        assert response.status_code == 503
        assert response.json() == {
            "success": False,
            "error_code": "SCHEDULING_UNAVAILABLE",
            "retryable": True,
            "message": "Test-drive scheduling is temporarily unavailable",
        }
        assert "Salesperson schedule lookup failed" in caplog.text
        assert "Salesperson schedule lookup failed" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_customer_tool_routes():
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        history = client.get(
            "/api/tools/get-customer-history/CUST-000001",
            headers=verified_customer("CUST-000001"),
        )
        assert history.status_code == 200
        assert history.json()["source"] == "database"

        post_history = client.post(
            "/api/tools/get-customer-history", json={"customer_id": "CUST-000001"},
            headers=verified_customer("CUST-000001"),
        )
        assert post_history.status_code == 200
        assert post_history.json() == history.json()
        
        assert set(post_history.json()["history"]) == {
            "customer", "leads", "appointments",
        }

        missing = client.get(
            "/api/tools/get-customer-history/CUST-999999",
            headers=verified_customer("CUST-999999"),
        )
        assert missing.status_code == 404

        slots = client.get("/api/tools/get-test-drive-slots", params={
            "vehicle_id": "VEH-000001", "requested_date": "2099-09-01",
            "days": 1, "salesperson_id": "SP-001",
        })
        assert slots.status_code == 200
        assert slots.json()["count"] == 2
    finally:
        app.dependency_overrides.clear()


def test_customer_history_post_route_supports_empty_history():
    app.dependency_overrides[get_customer_tools_repository] = EmptyHistoryRepository
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-customer-history", json={"customer_id": "CUST-000002"},
            headers=verified_customer("CUST-000002"),
        )
        assert response.status_code == 200
        assert response.json()["history"]["customer"]["customer_id"] == "CUST-000002"
        assert response.json()["history"]["leads"] == []
        assert response.json()["history"]["appointments"] == []
    finally:
        app.dependency_overrides.clear()


def test_customer_history_post_route_rejects_invalid_missing_and_unknown_ids():
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        assert client.post(
            "/api/tools/get-customer-history", json={"customer_id": "bad-id"},
            headers=verified_customer("CUST-000001"),
        ).status_code == 422
        assert client.post(
            "/api/tools/get-customer-history", json={},
            headers=verified_customer("CUST-000001"),
        ).status_code == 422

        unknown = client.post(
            "/api/tools/get-customer-history", json={"customer_id": "CUST-999999"},
            headers=verified_customer("CUST-999999"),
        )
        assert unknown.status_code == 404
        assert unknown.json()["error_code"] == "CUSTOMER_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_customer_history_post_route_returns_sanitized_database_error():
    app.dependency_overrides[get_customer_tools_repository] = FailingHistoryRepository
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-customer-history", json={"customer_id": "CUST-000001"},
            headers=verified_customer("CUST-000001"),
        )
        assert response.status_code == 503
        assert response.json() == {
            "success": False, "error_code": "CUSTOMER_HISTORY_UNAVAILABLE",
            "retryable": True, "message": "Customer history is temporarily unavailable",
        }
        assert "provider details" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_post_route_uses_authoritative_vehicle_and_slots():
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        get_response = client.get("/api/tools/get-test-drive-slots", params={
            "vehicle_id": "VEH-000001", "requested_date": "2099-09-01",
            "days": 1, "salesperson_id": "SP-001",
        })
        response = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000001", "requested_date": "2099-09-01",
            "days": 1, "salesperson_id": "SP-001",
        })
        assert response.status_code == 200
        assert response.json() == get_response.json()
        assert response.json()["count"] == 2

        ineligible = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000002", "requested_date": "2099-09-01",
        })
        assert ineligible.status_code == 409
        assert ineligible.json() == {
            "success": False,
            "error_code": "VEHICLE_NOT_AVAILABLE_FOR_TEST_DRIVE",
            "retryable": False,
            "message": "This vehicle is not currently available for a test drive",
        }
        ineligible_get = client.get("/api/tools/get-test-drive-slots", params={
            "vehicle_id": "VEH-000002", "requested_date": "2099-09-01",
        })
        assert ineligible_get.status_code == 409
        assert ineligible_get.json() == ineligible.json()
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_post_route_rejects_invalid_or_missing_input():
    client = TestClient(app, headers=TOOL_HEADERS)
    invalid_vehicle = client.post("/api/tools/get-test-drive-slots", json={
        "vehicle_id": "bad-id", "requested_date": "2099-09-01",
    })
    assert invalid_vehicle.status_code == 422

    missing_vehicle = client.post("/api/tools/get-test-drive-slots", json={
        "requested_date": "2099-09-01",
    })
    assert missing_vehicle.status_code == 422

    invalid_date = client.post("/api/tools/get-test-drive-slots", json={
        "vehicle_id": "VEH-000001", "requested_date": "not-a-date",
    })
    assert invalid_date.status_code == 422

    missing_get_vehicle = client.get(
        "/api/tools/get-test-drive-slots",
        params={"requested_date": "2099-09-01"},
    )
    assert missing_get_vehicle.status_code == 422


def test_test_drive_slots_post_keeps_start_date_alias_compatible():
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        response = TestClient(app, headers=TOOL_HEADERS).post(
            "/api/tools/get-test-drive-slots",
            json={
                "vehicle_id": "VEH-000001",
                "start_date": "2099-09-01",
                "days": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_get_rejects_past_date_before_returning_slots():
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        response = TestClient(app, headers=TOOL_HEADERS).get(
            "/api/tools/get-test-drive-slots",
            params={"vehicle_id": "VEH-000001", "requested_date": "2026-08-01"},
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "PAST_REQUESTED_DATE"
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_post_route_returns_not_found_and_safe_service_errors(monkeypatch):
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        client = TestClient(app, headers=TOOL_HEADERS)
        not_found = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-999999", "requested_date": "2099-09-01",
        })
        assert not_found.status_code == 404
        assert not_found.json()["error_code"] == "VEHICLE_NOT_FOUND"

        def unavailable(*_args):
            raise InventoryToolUnavailableError("provider details must stay private")

        monkeypatch.setattr(customer_tool_routes, "check_vehicle_availability", unavailable)
        failed = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000001", "requested_date": "2099-09-01",
        })
        assert failed.status_code == 503
        assert failed.json()["error_code"] == "INVENTORY_UNAVAILABLE"
        assert "provider details" not in failed.text
    finally:
        app.dependency_overrides.clear()
