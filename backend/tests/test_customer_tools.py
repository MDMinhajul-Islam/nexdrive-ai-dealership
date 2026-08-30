from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.inventory import CsvInventoryRepository
from app.routes import customer_tools as customer_tool_routes
from app.routes.customer_tools import (
    get_customer_tools_repository,
    get_test_drive_inventory_repository,
)
from app.schemas.customer_tools import TestDriveSlotQuery as SlotQuery
from app.services.customer_tools import get_customer_history, get_test_drive_slots
from app.services.inventory_tools import InventoryToolUnavailableError


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
            "salesperson_id": "SP-001", "appointment_date": "2026-08-25",
            "appointment_time": "09:30:00", "status": "Confirmed",
        }]


def test_customer_history_returns_related_records():
    result = get_customer_history("CUST-000001", FakeRepository())
    assert result.customer["customer_id"] == "CUST-000001"
    assert result.leads[0]["lead_id"] == "LEAD-000001"
    assert result.appointments[0]["appointment_id"] == "APT-000001"


def test_slots_follow_shift_and_exclude_booked_time():
    result = get_test_drive_slots(SlotQuery(
        start_date=date(2026, 8, 25), days=1, salesperson_id="SP-001", limit=10,
    ), FakeRepository())
    assert [slot.appointment_time.strftime("%H:%M") for slot in result.slots] == ["09:00", "10:00"]


def test_customer_tool_routes():
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    try:
        client = TestClient(app)
        history = client.get("/api/tools/get-customer-history/CUST-000001")
        assert history.status_code == 200
        assert history.json()["source"] == "database"

        missing = client.get("/api/tools/get-customer-history/CUST-999999")
        assert missing.status_code == 404

        slots = client.get("/api/tools/get-test-drive-slots", params={
            "start_date": "2026-08-25", "days": 1, "salesperson_id": "SP-001",
        })
        assert slots.status_code == 200
        assert slots.json()["count"] == 2
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_post_route_uses_authoritative_vehicle_and_slots():
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        client = TestClient(app)
        get_response = client.get("/api/tools/get-test-drive-slots", params={
            "start_date": "2026-08-25", "days": 1, "salesperson_id": "SP-001",
        })
        response = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000001", "start_date": "2026-08-25",
            "days": 1, "salesperson_id": "SP-001",
        })
        assert response.status_code == 200
        assert response.json() == get_response.json()
        assert response.json()["count"] == 2

        ineligible = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000002", "start_date": "2026-08-25",
        })
        assert ineligible.status_code == 409
        assert ineligible.json()["detail"]["vehicle_status"] == "Sold"
        assert "cannot be recommended" in ineligible.json()["detail"]["reason"]
    finally:
        app.dependency_overrides.clear()


def test_test_drive_slots_post_route_rejects_invalid_or_missing_input():
    client = TestClient(app)
    invalid_vehicle = client.post("/api/tools/get-test-drive-slots", json={
        "vehicle_id": "bad-id", "start_date": "2026-08-25",
    })
    assert invalid_vehicle.status_code == 422

    missing_vehicle = client.post("/api/tools/get-test-drive-slots", json={
        "start_date": "2026-08-25",
    })
    assert missing_vehicle.status_code == 422

    invalid_date = client.post("/api/tools/get-test-drive-slots", json={
        "vehicle_id": "VEH-000001", "start_date": "not-a-date",
    })
    assert invalid_date.status_code == 422


def test_test_drive_slots_post_route_returns_not_found_and_safe_service_errors(monkeypatch):
    inventory = CsvInventoryRepository(Path(__file__).parent / "fixtures" / "inventory")
    app.dependency_overrides[get_customer_tools_repository] = FakeRepository
    app.dependency_overrides[get_test_drive_inventory_repository] = lambda: inventory
    try:
        client = TestClient(app)
        not_found = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-999999", "start_date": "2026-08-25",
        })
        assert not_found.status_code == 404
        assert not_found.json() == {"detail": "Vehicle not found"}

        def unavailable(*_args):
            raise InventoryToolUnavailableError("provider details must stay private")

        monkeypatch.setattr(customer_tool_routes, "check_vehicle_availability", unavailable)
        failed = client.post("/api/tools/get-test-drive-slots", json={
            "vehicle_id": "VEH-000001", "start_date": "2026-08-25",
        })
        assert failed.status_code == 503
        assert failed.json() == {"detail": "Inventory service unavailable"}
        assert "provider details" not in failed.text
    finally:
        app.dependency_overrides.clear()
