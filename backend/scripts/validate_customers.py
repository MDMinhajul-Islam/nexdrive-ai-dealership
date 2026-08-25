"""Validate the NexDrive synthetic customer dataset."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "database" / "seed" / "customers.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "customer_validation_report.json"
ID_RE = re.compile(r"^CUST-\d{6}$")
PHONE_RE = re.compile(r"^\+1-555-010-\d{4}$")
EMAIL_RE = re.compile(r"^customer\d{6}@nexdrive\.example$")
VEHICLE_TYPES = {"SUV", "Sedan", "Truck", "Hatchback"}
TIMELINES = {"Within 7 Days", "Within 30 Days", "1-3 Months", "3-6 Months", "Researching"}
PROFILES = {"Hot", "Warm", "Research", "Edge Case"}


def validate(path: Path, expected_count: int) -> dict:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    warnings: list[str] = []
    if len(rows) != expected_count:
        errors.append(f"Expected {expected_count:,} customers, found {len(rows):,}")
    for field in ("customer_id", "synthetic_phone", "synthetic_email"):
        values = [row[field] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {field} values found")

    profiles: Counter[str] = Counter()
    timelines: Counter[str] = Counter()
    cities: Counter[str] = Counter()
    vehicle_types: Counter[str] = Counter()
    lead_sources: Counter[str] = Counter()
    financing_count = 0
    trade_in_count = 0
    for row_number, row in enumerate(rows, start=2):
        prefix = f"row {row_number} ({row.get('customer_id', 'unknown')})"
        if not ID_RE.fullmatch(row["customer_id"]):
            errors.append(f"{prefix}: malformed customer_id")
        if not PHONE_RE.fullmatch(row["synthetic_phone"]):
            errors.append(f"{prefix}: phone is not in the reserved synthetic namespace")
        if not EMAIL_RE.fullmatch(row["synthetic_email"]):
            errors.append(f"{prefix}: email is not in the reserved .example domain")
        if not row["first_name"].strip() or not row["last_name"].strip():
            errors.append(f"{prefix}: missing customer name")
        if row["state"] != "TX":
            errors.append(f"{prefix}: customer is outside the configured Texas market")
        if row["preferred_vehicle_type"] not in VEHICLE_TYPES:
            errors.append(f"{prefix}: invalid preferred vehicle type")
        if row["purchase_timeline"] not in TIMELINES:
            errors.append(f"{prefix}: invalid purchase timeline")
        if row["buyer_profile"] not in PROFILES:
            errors.append(f"{prefix}: invalid buyer profile")
        try:
            budget_min = int(row["budget_min"])
            budget_max = int(row["budget_max"])
            down_payment = int(row["estimated_down_payment"])
            family_size = int(row["family_size"])
            datetime.fromisoformat(row["created_at"])
        except ValueError:
            errors.append(f"{prefix}: invalid numeric or datetime value")
            continue
        if not 3_000 <= budget_min <= budget_max <= 100_000:
            errors.append(f"{prefix}: invalid budget range")
        if not 1 <= family_size <= 8:
            errors.append(f"{prefix}: invalid family size")
        financing = row["financing_needed"].lower() == "true"
        trade_in = row["trade_in"].lower() == "true"
        if row["financing_needed"].lower() not in {"true", "false"} or row["trade_in"].lower() not in {"true", "false"}:
            errors.append(f"{prefix}: invalid boolean value")
        if not 0 <= down_payment <= budget_max or (not financing and down_payment != 0):
            errors.append(f"{prefix}: down payment conflicts with financing")
        profiles[row["buyer_profile"]] += 1
        timelines[row["purchase_timeline"]] += 1
        cities[row["city"]] += 1
        vehicle_types[row["preferred_vehicle_type"]] += 1
        lead_sources[row["lead_source"]] += 1
        financing_count += int(financing)
        trade_in_count += int(trade_in)

    if rows:
        for profile, minimum, maximum in (
            ("Hot", 12, 24), ("Warm", 34, 50), ("Research", 24, 40), ("Edge Case", 4, 12)
        ):
            percentage = profiles[profile] / len(rows) * 100
            if not minimum <= percentage <= maximum:
                errors.append(f"{profile} profile mix is {percentage:.2f}%, expected {minimum}-{maximum}%")
        if len(cities) < 5:
            warnings.append("Customer geography has fewer than five cities")

    return {
        "result": "PASS" if not errors else "FAIL",
        "dataset_as_of": "2026-08-25",
        "summary": {
            "customers": len(rows),
            "unique_customer_ids": len({r["customer_id"] for r in rows}),
            "unique_synthetic_phones": len({r["synthetic_phone"] for r in rows}),
            "unique_synthetic_emails": len({r["synthetic_email"] for r in rows}),
            "financing_needed": financing_count,
            "trade_ins": trade_in_count,
        },
        "buyer_profile_distribution": dict(sorted(profiles.items())),
        "purchase_timeline_distribution": dict(sorted(timelines.items())),
        "vehicle_type_distribution": dict(sorted(vehicle_types.items())),
        "city_distribution": dict(sorted(cities.items())),
        "lead_source_distribution": dict(sorted(lead_sources.items())),
        "errors": errors[:100], "error_count": len(errors), "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-count", type=int, default=5_000)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = validate(args.input.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        print(f"FAIL: {exc}")
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['customers']:,} customers, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
