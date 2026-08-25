"""Run the cross-dataset NexDrive relationship quality gate."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
REPORT = ROOT / "backend" / "docs" / "business_data_validation_report.json"


def read(name: str) -> list[dict[str, str]]:
    with (SEED_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    vehicles = {row["vehicle_id"]: row for row in read("vehicles.csv")}
    customers = {row["customer_id"]: row for row in read("customers.csv")}
    salespeople = {row["salesperson_id"]: row for row in read("salespeople.csv")}
    leads = {row["lead_id"]: row for row in read("leads.csv")}
    appointments = read("appointments.csv")
    trade_ins = read("trade_ins.csv")
    financing = read("financing_options.csv")
    errors: list[str] = []
    for lead in leads.values():
        if lead["customer_id"] not in customers: errors.append(f"{lead['lead_id']}: missing customer")
        if lead["assigned_salesperson"] not in salespeople: errors.append(f"{lead['lead_id']}: missing salesperson")
        if lead["vehicle_interest"] and lead["vehicle_interest"] not in vehicles: errors.append(f"{lead['lead_id']}: missing vehicle")
    for appointment in appointments:
        lead = leads.get(appointment["lead_id"])
        if not lead: errors.append(f"{appointment['appointment_id']}: missing lead"); continue
        if (appointment["customer_id"], appointment["vehicle_id"], appointment["salesperson_id"]) != (
            lead["customer_id"], lead["vehicle_interest"], lead["assigned_salesperson"]
        ): errors.append(f"{appointment['appointment_id']}: relationship snapshot mismatch")
    for trade_in in trade_ins:
        lead = leads.get(trade_in["lead_id"])
        if not lead or lead["customer_id"] != trade_in["customer_id"]:
            errors.append(f"{trade_in['trade_in_id']}: broken lead/customer relationship")
    expected_counts = {"vehicles": 10_000, "customers": 5_000, "salespeople": 10, "leads": 4_000, "appointments": 1_500, "trade_ins": 40, "financing_options": 12}
    actual_counts = {"vehicles": len(vehicles), "customers": len(customers), "salespeople": len(salespeople), "leads": len(leads), "appointments": len(appointments), "trade_ins": len(trade_ins), "financing_options": len(financing)}
    for name, expected in expected_counts.items():
        if actual_counts[name] != expected: errors.append(f"{name}: expected {expected}, found {actual_counts[name]}")
    report = {
        "result": "PASS" if not errors else "FAIL", "dataset_as_of": "2026-08-25",
        "record_counts": actual_counts, "relationship_errors": len(errors),
        "errors": errors[:100], "error_count": len(errors), "warnings": [],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: cross-dataset validation, {report['error_count']} errors")
    print(f"Report: {REPORT}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
