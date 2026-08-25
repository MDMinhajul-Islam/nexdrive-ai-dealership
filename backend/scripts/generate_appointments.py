"""Generate deterministic NexDrive appointments with schedule-safe relationships."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_OUTPUT = SEED_DIR / "appointments.csv"
AS_OF = date(2026, 8, 25)
FIELDS = [
    "appointment_id", "lead_id", "customer_id", "vehicle_id", "salesperson_id",
    "appointment_date", "appointment_time", "appointment_type", "status",
    "created_by", "notes", "created_at",
]
PAST_STATUSES = ["Completed", "Cancelled", "No Show"]
FUTURE_STATUSES = ["Confirmed", "Requested", "Rescheduled"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_array(value: str) -> set[str]:
    return set(value.removeprefix("{").removesuffix("}").split(","))


def choose_workday(rng: random.Random, start: date, end: date, working_days: set[str]) -> date:
    candidates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    candidates = [candidate for candidate in candidates if candidate.strftime("%A") in working_days]
    return rng.choice(candidates)


def time_slots(start_value: str, end_value: str) -> list[str]:
    start = datetime.combine(AS_OF, time.fromisoformat(start_value))
    end = datetime.combine(AS_OF, time.fromisoformat(end_value))
    slots = []
    current = start
    while current + timedelta(minutes=30) <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


def generate(count: int, seed: int, output: Path) -> None:
    rng = random.Random(seed)
    leads = [row for row in read_csv(SEED_DIR / "leads.csv") if row["vehicle_interest"]]
    vehicles = {row["vehicle_id"]: row for row in read_csv(SEED_DIR / "vehicles.csv")}
    salespeople = {row["salesperson_id"]: row for row in read_csv(SEED_DIR / "salespeople.csv")}
    if count > len(leads):
        raise ValueError(f"Requested {count} appointments but only {len(leads)} vehicle-linked leads exist")
    chosen = rng.sample(leads, count)
    bookings: set[tuple[str, str, str]] = set()
    rows: list[dict[str, str]] = []
    for index, lead in enumerate(chosen, start=1):
        salesperson = salespeople[lead["assigned_salesperson"]]
        vehicle = vehicles[lead["vehicle_interest"]]
        future_eligible = vehicle["test_drive_available"] == "true" and salesperson["active"] == "true"
        future = future_eligible and rng.random() < 0.45
        if future:
            status = rng.choices(FUTURE_STATUSES, weights=[55, 28, 17], k=1)[0]
            appointment_date = choose_workday(rng, AS_OF + timedelta(days=1), AS_OF + timedelta(days=45), parse_array(salesperson["working_days"]))
        else:
            status = rng.choices(PAST_STATUSES, weights=[66, 21, 13], k=1)[0]
            appointment_date = choose_workday(rng, AS_OF - timedelta(days=150), AS_OF - timedelta(days=1), parse_array(salesperson["working_days"]))
        slots = time_slots(salesperson["shift_start"], salesperson["shift_end"])
        rng.shuffle(slots)
        appointment_time = next(
            slot for slot in slots
            if (salesperson["salesperson_id"], appointment_date.isoformat(), slot) not in bookings
        )
        bookings.add((salesperson["salesperson_id"], appointment_date.isoformat(), appointment_time))
        appointment_type = rng.choices(
            ["Test Drive", "Virtual Consultation", "Financing Consultation", "Trade-In Appraisal"],
            weights=[68, 12, 12, 8], k=1,
        )[0]
        created_date = (
            AS_OF - timedelta(days=rng.randint(0, 21))
            if future
            else appointment_date - timedelta(days=rng.randint(1, 21))
        )
        created_at = datetime.combine(created_date, time(15, 0), tzinfo=timezone.utc)
        rows.append({
            "appointment_id": f"APT-{index:06d}", "lead_id": lead["lead_id"],
            "customer_id": lead["customer_id"], "vehicle_id": lead["vehicle_interest"],
            "salesperson_id": salesperson["salesperson_id"],
            "appointment_date": appointment_date.isoformat(), "appointment_time": appointment_time,
            "appointment_type": appointment_type, "status": status,
            "created_by": rng.choices(["Voice Agent", "Website", "Salesperson", "Customer Service"], weights=[32, 28, 25, 15], k=1)[0],
            "notes": "Synthetic dealership appointment; authoritative status is stored in this record.",
            "created_at": created_at.isoformat(),
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows):,} synthetic appointments in {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1_500)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.count, args.seed, args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
