"""Validate NexDrive leads, deterministic scoring, and foreign-key relationships."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_INPUT = SEED_DIR / "leads.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "leads_validation_report.json"
ID_RE = re.compile(r"^LEAD-\d{6}$")
STATUSES = {"New", "Contacted", "Discovery", "Qualified", "Vehicle Recommended", "Test Drive", "Negotiation", "Financing", "Won", "Lost"}
ACTION_STATUSES = {"Test Drive", "Negotiation", "Financing", "Won"}
SELECTED_VEHICLE_STATUSES = {"Vehicle Recommended", *ACTION_STATUSES}
TERMINAL_STATUSES = {"Won", "Lost"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def expected_score(customer: dict[str, str], vehicle_interest: str, status: str) -> int:
    score = {"Within 7 Days": 30, "Within 30 Days": 20}.get(customer["purchase_timeline"], 0) + 15
    score += 15 if vehicle_interest else 0
    score += 20 if status in ACTION_STATUSES else 0
    score += 10 if customer["financing_needed"] == "true" else 0
    score += 5 if customer["trade_in"] == "true" else 0
    return min(100, score)


def validate(path: Path, expected_count: int) -> dict:
    leads = read_csv(path)
    customers = {row["customer_id"]: row for row in read_csv(SEED_DIR / "customers.csv")}
    vehicles = {row["vehicle_id"]: row for row in read_csv(SEED_DIR / "vehicles.csv")}
    salespeople = {row["salesperson_id"]: row for row in read_csv(SEED_DIR / "salespeople.csv")}
    errors: list[str] = []
    warnings: list[str] = []
    if len(leads) != expected_count:
        errors.append(f"Expected {expected_count:,} leads, found {len(leads):,}")
    ids = [row["lead_id"] for row in leads]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate lead_id values found")
    customer_ids = [row["customer_id"] for row in leads]
    if len(customer_ids) != len(set(customer_ids)):
        warnings.append("Some customers have multiple generated leads")

    statuses: Counter[str] = Counter()
    temperatures: Counter[str] = Counter()
    salesperson_load: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    vehicle_interest_count = 0
    unavailable_interest_count = 0
    for row_number, row in enumerate(leads, start=2):
        prefix = f"row {row_number} ({row.get('lead_id', 'unknown')})"
        if not ID_RE.fullmatch(row["lead_id"]):
            errors.append(f"{prefix}: malformed lead_id")
        customer = customers.get(row["customer_id"])
        if not customer:
            errors.append(f"{prefix}: customer_id does not resolve")
            continue
        salesperson = salespeople.get(row["assigned_salesperson"])
        if not salesperson:
            errors.append(f"{prefix}: assigned_salesperson does not resolve")
        elif salesperson["active"] != "true":
            errors.append(f"{prefix}: lead assigned to inactive salesperson")
        if row["lead_status"] not in STATUSES:
            errors.append(f"{prefix}: invalid lead status")
        vehicle = None
        if row["vehicle_interest"]:
            vehicle_interest_count += 1
            vehicle = vehicles.get(row["vehicle_interest"])
            if not vehicle:
                errors.append(f"{prefix}: vehicle_interest does not resolve")
            elif vehicle["vehicle_status"] != "Available":
                unavailable_interest_count += 1
        if row["lead_status"] in SELECTED_VEHICLE_STATUSES and not row["vehicle_interest"]:
            errors.append(f"{prefix}: downstream lead stage is missing vehicle_interest")
        if row["lead_status"] in SELECTED_VEHICLE_STATUSES and vehicle and vehicle["vehicle_status"] != "Available":
            errors.append(f"{prefix}: downstream lead stage references unavailable inventory")
        try:
            score = int(row["lead_score"])
            budget = int(row["budget"])
            created_at = datetime.fromisoformat(row["created_at"])
        except ValueError:
            errors.append(f"{prefix}: invalid numeric or datetime value")
            continue
        if budget != int(customer["budget_max"]):
            errors.append(f"{prefix}: budget snapshot conflicts with customer")
        for field in ("source", "purchase_timeline", "financing_needed", "trade_in"):
            customer_field = "lead_source" if field == "source" else field
            if row[field] != customer[customer_field]:
                errors.append(f"{prefix}: {field} conflicts with customer snapshot")
        expected = expected_score(customer, row["vehicle_interest"], row["lead_status"])
        if score != expected:
            errors.append(f"{prefix}: lead_score {score} does not match deterministic score {expected}")
        temperature = "Hot" if score >= 70 else "Warm" if score >= 40 else "Cold"
        if row["lead_temperature"] != temperature:
            errors.append(f"{prefix}: lead_temperature conflicts with score")
        if created_at < datetime.fromisoformat(customer["created_at"]):
            errors.append(f"{prefix}: lead predates customer record")
        if row["lead_status"] in TERMINAL_STATUSES:
            if row["next_followup_date"]:
                errors.append(f"{prefix}: terminal lead has a follow-up date")
        else:
            try:
                followup = date.fromisoformat(row["next_followup_date"])
                if not date(2026, 8, 26) <= followup <= date(2026, 9, 8):
                    errors.append(f"{prefix}: follow-up date outside configured window")
            except ValueError:
                errors.append(f"{prefix}: active lead missing valid follow-up date")
        statuses[row["lead_status"]] += 1
        temperatures[row["lead_temperature"]] += 1
        salesperson_load[row["assigned_salesperson"]] += 1
        sources[row["source"]] += 1

    if len(statuses) < 8:
        warnings.append("Lead pipeline represents fewer than eight stages")
    if len(salesperson_load) < 8:
        warnings.append("Fewer than eight active salespeople have assigned leads")
    return {
        "result": "PASS" if not errors else "FAIL",
        "dataset_as_of": "2026-08-25",
        "summary": {
            "leads": len(leads), "unique_lead_ids": len(set(ids)),
            "unique_customer_relationships": len(set(customer_ids)),
            "vehicle_interests": vehicle_interest_count,
            "unavailable_vehicle_interests": unavailable_interest_count,
        },
        "status_distribution": dict(sorted(statuses.items())),
        "temperature_distribution": dict(sorted(temperatures.items())),
        "salesperson_load": dict(sorted(salesperson_load.items())),
        "source_distribution": dict(sorted(sources.items())),
        "errors": errors[:100], "error_count": len(errors), "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-count", type=int, default=4_000)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = validate(args.input.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        print(f"FAIL: {exc}")
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['leads']:,} leads, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
