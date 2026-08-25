"""Validate the NexDrive synthetic sales-team roster."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "database" / "seed" / "salespeople.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "salespeople_validation_report.json"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LANGUAGES = {"English", "Spanish", "Hindi", "Urdu"}
SPECIALIZATIONS = {
    "General Sales", "SUV Specialist", "Truck Specialist", "EV/Hybrid Specialist",
    "Used/CPO Specialist", "Financing-Focused",
}
ID_RE = re.compile(r"^SP-\d{3}$")
EMAIL_RE = re.compile(r"^salesperson\d{3}@nexdrive\.example$")
PHONE_RE = re.compile(r"^\+1-555-020-\d{4}$")


def parse_pg_array(value: str) -> list[str]:
    if not value.startswith("{") or not value.endswith("}"):
        raise ValueError("invalid PostgreSQL array literal")
    content = value[1:-1]
    return [] if not content else content.split(",")


def parse_time(value: str) -> time:
    return time.fromisoformat(value)


def validate(path: Path, expected_count: int) -> dict:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    warnings: list[str] = []
    if len(rows) != expected_count:
        errors.append(f"Expected {expected_count} salespeople, found {len(rows)}")
    for field in ("salesperson_id", "synthetic_email", "synthetic_phone"):
        values = [row[field] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {field} values found")

    active_coverage: Counter[str] = Counter()
    specializations: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    active_count = 0
    for row_number, row in enumerate(rows, start=2):
        prefix = f"row {row_number} ({row.get('salesperson_id', 'unknown')})"
        if not ID_RE.fullmatch(row["salesperson_id"]):
            errors.append(f"{prefix}: malformed salesperson_id")
        if not EMAIL_RE.fullmatch(row["synthetic_email"]):
            errors.append(f"{prefix}: email is not in the reserved .example domain")
        if not PHONE_RE.fullmatch(row["synthetic_phone"]):
            errors.append(f"{prefix}: phone is not in the synthetic namespace")
        if not row["name"].strip():
            errors.append(f"{prefix}: missing name")
        if row["specialization"] not in SPECIALIZATIONS:
            errors.append(f"{prefix}: invalid specialization")
        try:
            languages = parse_pg_array(row["languages"])
            working_days = parse_pg_array(row["working_days"])
            shift_start = parse_time(row["shift_start"])
            shift_end = parse_time(row["shift_end"])
        except ValueError as exc:
            errors.append(f"{prefix}: {exc}")
            continue
        if not languages or not set(languages) <= LANGUAGES or len(languages) != len(set(languages)):
            errors.append(f"{prefix}: invalid languages")
        if not working_days or not set(working_days) <= set(DAYS) or len(working_days) != len(set(working_days)):
            errors.append(f"{prefix}: invalid working days")
        if shift_start >= shift_end:
            errors.append(f"{prefix}: shift_start must precede shift_end")
        if row["active"].lower() not in {"true", "false"}:
            errors.append(f"{prefix}: invalid active flag")
            continue
        active = row["active"].lower() == "true"
        if active:
            active_count += 1
            active_coverage.update(working_days)
        specializations[row["specialization"]] += 1
        language_counts.update(languages)

    for day in DAYS:
        if active_coverage[day] < 1:
            errors.append(f"No active salesperson covers {day}")
    if active_count == len(rows):
        warnings.append("Roster has no inactive salesperson edge case")
    if language_counts["Spanish"] < 1:
        errors.append("Roster has no Spanish-speaking salesperson")
    if len(specializations) < 6:
        errors.append("Not all required specialization types are represented")

    return {
        "result": "PASS" if not errors else "FAIL",
        "dataset_as_of": "2026-08-25",
        "summary": {
            "salespeople": len(rows), "active": active_count,
            "inactive": len(rows) - active_count,
            "unique_salesperson_ids": len({r["salesperson_id"] for r in rows}),
            "unique_synthetic_emails": len({r["synthetic_email"] for r in rows}),
            "unique_synthetic_phones": len({r["synthetic_phone"] for r in rows}),
        },
        "active_day_coverage": {day: active_coverage[day] for day in DAYS},
        "specialization_distribution": dict(sorted(specializations.items())),
        "language_distribution": dict(sorted(language_counts.items())),
        "errors": errors, "error_count": len(errors), "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-count", type=int, default=10)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = validate(args.input.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        print(f"FAIL: {exc}")
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['salespeople']} salespeople, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
