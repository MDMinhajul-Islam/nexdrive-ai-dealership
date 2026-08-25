"""Business rules for customer history and available test-drive slots."""

from datetime import date, datetime, time, timedelta

from app.repositories.customer_tools import CustomerToolsRepository, CustomerToolsRepositoryError
from app.schemas.customer_tools import CustomerHistory, TestDriveSlot, TestDriveSlotQuery, TestDriveSlotsResponse


class CustomerToolsUnavailableError(RuntimeError):
    pass


class CustomerNotFoundError(RuntimeError):
    pass


def get_customer_history(customer_id: str, repository: CustomerToolsRepository) -> CustomerHistory:
    try:
        history = repository.customer_history(customer_id)
    except CustomerToolsRepositoryError:
        raise CustomerToolsUnavailableError from None
    if history is None:
        raise CustomerNotFoundError
    return CustomerHistory(**history)


def _parse_time(value: str | time) -> time:
    return value if isinstance(value, time) else time.fromisoformat(value)


def get_test_drive_slots(query: TestDriveSlotQuery, repository: CustomerToolsRepository) -> TestDriveSlotsResponse:
    end_date = query.start_date + timedelta(days=query.days - 1)
    try:
        salespeople = repository.salespeople(query.salesperson_id)
        appointments = repository.appointments_between(query.start_date, end_date)
    except CustomerToolsRepositoryError:
        raise CustomerToolsUnavailableError from None

    occupied = {
        (row["salesperson_id"], str(row["appointment_date"]), str(row["appointment_time"])[:5])
        for row in appointments
    }
    slots: list[TestDriveSlot] = []
    for offset in range(query.days):
        slot_date = query.start_date + timedelta(days=offset)
        for person in salespeople:
            if slot_date.strftime("%A") not in person["working_days"]:
                continue
            cursor = datetime.combine(slot_date, _parse_time(person["shift_start"]))
            end = datetime.combine(slot_date, _parse_time(person["shift_end"]))
            while cursor + timedelta(minutes=30) <= end:
                key = (person["salesperson_id"], slot_date.isoformat(), cursor.strftime("%H:%M"))
                if key not in occupied:
                    slots.append(TestDriveSlot(
                        salesperson_id=person["salesperson_id"], salesperson_name=person["name"],
                        appointment_date=slot_date, appointment_time=cursor.time(),
                    ))
                cursor += timedelta(minutes=30)
    slots.sort(key=lambda slot: (slot.appointment_date, slot.appointment_time, slot.salesperson_id))
    slots = slots[:query.limit]
    return TestDriveSlotsResponse(count=len(slots), slots=slots)
