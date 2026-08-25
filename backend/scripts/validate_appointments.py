"""Validate NexDrive appointment relationships and booking-state rules."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_INPUT = SEED_DIR / "appointments.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "appointments_validation_report.json"
AS_OF = date(2026, 8, 25)
ID_RE = re.compile(r"^APT-\d{6}$")
PAST_STATUSES = {"Completed", "Cancelled", "No Show"}
FUTURE_STATUSES = {"Confirmed", "Requested", "Rescheduled"}
TYPES = {"Test Drive", "Virtual Consultation", "Financing Consultation", "Trade-In Appraisal"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_array(value: str) -> set[str]:
    return set(value.removeprefix("{").removesuffix("}").split(","))


def validate(path: Path, expected_count: int) -> dict:
    rows = read_csv(path)
    leads = {row["lead_id"]: row for row in read_csv(SEED_DIR / "leads.csv")}
    customers = {row["customer_id"] for row in read_csv(SEED_DIR / "customers.csv")}
    vehicles = {row["vehicle_id"]: row for row in read_csv(SEED_DIR / "vehicles.csv")}
    salespeople = {row["salesperson_id"]: row for row in read_csv(SEED_DIR / "salespeople.csv")}
    errors: list[str] = []
    warnings: list[str] = []
    if len(rows) != expected_count:
        errors.append(f"Expected {expected_count:,} appointments, found {len(rows):,}")
    for field in ("appointment_id", "lead_id"):
        values = [row[field] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {field} values found")
    slots: set[tuple[str, str, str]] = set()
    statuses: Counter[str] = Counter()
    types: Counter[str] = Counter()
    creators: Counter[str] = Counter()
    future_count = 0
    for row_number, row in enumerate(rows, start=2):
        prefix = f"row {row_number} ({row.get('appointment_id', 'unknown')})"
        if not ID_RE.fullmatch(row["appointment_id"]):
            errors.append(f"{prefix}: malformed appointment_id")
        lead = leads.get(row["lead_id"])
        if not lead:
            errors.append(f"{prefix}: lead_id does not resolve")
        else:
            if row["customer_id"] != lead["customer_id"]:
                errors.append(f"{prefix}: customer_id conflicts with lead")
            if row["vehicle_id"] != lead["vehicle_interest"]:
                errors.append(f"{prefix}: vehicle_id conflicts with lead")
            if row["salesperson_id"] != lead["assigned_salesperson"]:
                errors.append(f"{prefix}: salesperson_id conflicts with lead")
        if row["customer_id"] not in customers:
            errors.append(f"{prefix}: customer_id does not resolve")
        vehicle = vehicles.get(row["vehicle_id"])
        if not vehicle:
            errors.append(f"{prefix}: vehicle_id does not resolve")
        salesperson = salespeople.get(row["salesperson_id"])
        if not salesperson:
            errors.append(f"{prefix}: salesperson_id does not resolve")
            continue
        try:
            appointment_date = date.fromisoformat(row["appointment_date"])
            appointment_time = time.fromisoformat(row["appointment_time"])
            created_at = datetime.fromisoformat(row["created_at"])
            shift_start = time.fromisoformat(salesperson["shift_start"])
            shift_end = time.fromisoformat(salesperson["shift_end"])
        except ValueError:
            errors.append(f"{prefix}: invalid date or time")
            continue
        slot = (row["salesperson_id"], row["appointment_date"], row["appointment_time"])
        if slot in slots:
            errors.append(f"{prefix}: duplicate salesperson time slot")
        slots.add(slot)
        if appointment_date.strftime("%A") not in parse_array(salesperson["working_days"]):
            errors.append(f"{prefix}: appointment falls outside salesperson working days")
        if not shift_start <= appointment_time < shift_end:
            errors.append(f"{prefix}: appointment falls outside salesperson shift")
        if created_at.date() > AS_OF or created_at.date() >= appointment_date:
            errors.append(f"{prefix}: invalid appointment creation timestamp")
        if appointment_date > AS_OF:
            future_count += 1
            if row["status"] not in FUTURE_STATUSES:
                errors.append(f"{prefix}: future appointment has historical status")
            if salesperson["active"] != "true":
                errors.append(f"{prefix}: future appointment assigned to inactive salesperson")
            if vehicle and vehicle["test_drive_available"] != "true":
                errors.append(f"{prefix}: future appointment uses unavailable vehicle")
        elif row["status"] not in PAST_STATUSES:
            errors.append(f"{prefix}: past appointment has future status")
        if row["appointment_type"] not in TYPES:
            errors.append(f"{prefix}: invalid appointment type")
        statuses[row["status"]] += 1
        types[row["appointment_type"]] += 1
        creators[row["created_by"]] += 1
    if len(statuses) < 6:
        warnings.append("Not all appointment status edge cases are represented")
    return {
        "result": "PASS" if not errors else "FAIL", "dataset_as_of": "2026-08-25",
        "summary": {"appointments": len(rows), "future_appointments": future_count, "unique_slots": len(slots)},
        "status_distribution": dict(sorted(statuses.items())),
        "type_distribution": dict(sorted(types.items())),
        "created_by_distribution": dict(sorted(creators.items())),
        "errors": errors[:100], "error_count": len(errors), "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-count", type=int, default=1_500)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = validate(args.input.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        print(f"FAIL: {exc}")
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['appointments']:,} appointments, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
