from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.routes.customer_tools import get_customer_tools_repository
from app.schemas.customer_tools import TestDriveSlotQuery as SlotQuery
from app.services.customer_tools import get_customer_history, get_test_drive_slots


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
