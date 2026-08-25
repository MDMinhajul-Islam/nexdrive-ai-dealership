"""Validate NexDrive trade-in estimates and their CRM relationships."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_INPUT = SEED_DIR / "trade_ins.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "trade_ins_validation_report.json"
ID_RE = re.compile(r"^TRD-\d{5}$")
CONDITIONS = {"Excellent", "Good", "Fair", "Poor"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(path: Path, expected_count: int) -> dict:
    rows = read_csv(path)
    leads = {row["lead_id"]: row for row in read_csv(SEED_DIR / "leads.csv")}
    customers = {row["customer_id"]: row for row in read_csv(SEED_DIR / "customers.csv")}
    errors: list[str] = []
    if len(rows) != expected_count:
        errors.append(f"Expected {expected_count} trade-ins, found {len(rows)}")
    for field in ("trade_in_id", "lead_id", "customer_id"):
        values = [row[field] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {field} values found")
    conditions: Counter[str] = Counter()
    positive_equity = 0
    negative_equity = 0
    paid_off = 0
    for row_number, row in enumerate(rows, start=2):
        prefix = f"row {row_number} ({row.get('trade_in_id', 'unknown')})"
        if not ID_RE.fullmatch(row["trade_in_id"]):
            errors.append(f"{prefix}: malformed trade_in_id")
        lead = leads.get(row["lead_id"])
        customer = customers.get(row["customer_id"])
        if not lead or not customer:
            errors.append(f"{prefix}: broken lead/customer relationship")
            continue
        if lead["customer_id"] != row["customer_id"]:
            errors.append(f"{prefix}: lead belongs to a different customer")
        if lead["trade_in"] != "true" or customer["trade_in"] != "true":
            errors.append(f"{prefix}: trade-in conflicts with lead/customer flags")
        try:
            year = int(row["year"]); mileage = int(row["mileage"])
            value = int(row["estimated_value"]); loan = int(row["loan_balance"])
        except ValueError:
            errors.append(f"{prefix}: invalid numeric value")
            continue
        if not 2010 <= year <= 2024 or not 0 <= mileage <= 220_000:
            errors.append(f"{prefix}: invalid year/mileage")
        age = 2026 - year
        if mileage > max(45_000, age * 25_000):
            errors.append(f"{prefix}: implausible mileage for age")
        if row["condition"] not in CONDITIONS:
            errors.append(f"{prefix}: invalid condition")
        if not 1_500 <= value <= 100_000 or not 0 <= loan <= 125_000:
            errors.append(f"{prefix}: invalid value or loan balance")
        if "estimate" not in row["notes"].lower():
            errors.append(f"{prefix}: valuation disclaimer is missing")
        conditions[row["condition"]] += 1
        paid_off += int(loan == 0)
        positive_equity += int(0 < loan < value)
        negative_equity += int(loan > value)
    return {
        "result": "PASS" if not errors else "FAIL", "dataset_as_of": "2026-08-25",
        "summary": {"trade_ins": len(rows), "paid_off": paid_off, "positive_equity": positive_equity, "negative_equity": negative_equity},
        "condition_distribution": dict(sorted(conditions.items())),
        "errors": errors, "error_count": len(errors), "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-count", type=int, default=40)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        report = validate(args.input.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error) as exc:
        print(f"FAIL: {exc}"); return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['trade_ins']} trade-ins, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
