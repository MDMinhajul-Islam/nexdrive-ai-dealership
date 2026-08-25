"""Validate deterministic demo financing rules and safe-language requirements."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "database" / "seed" / "financing_options.csv"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "financing_validation_report.json"
ID_RE = re.compile(r"^FIN-\d{3}$")
CONDITIONS = {"New", "Used", "Certified Pre-Owned"}
TERMS = {36, 48, 60, 72}


def validate(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    if len(rows) != 12:
        errors.append(f"Expected 12 financing rules, found {len(rows)}")
    ids = [row["financing_rule_id"] for row in rows]
    pairs = [(row["vehicle_condition"], row["term_months"]) for row in rows]
    if len(ids) != len(set(ids)): errors.append("Duplicate financing_rule_id values found")
    if len(pairs) != len(set(pairs)): errors.append("Duplicate condition/term pairs found")
    condition_counts: Counter[str] = Counter()
    for row_number, row in enumerate(rows, start=2):
        prefix = f"row {row_number} ({row.get('financing_rule_id', 'unknown')})"
        if not ID_RE.fullmatch(row["financing_rule_id"]): errors.append(f"{prefix}: malformed rule ID")
        if row["vehicle_condition"] not in CONDITIONS: errors.append(f"{prefix}: invalid condition")
        try:
            term = int(row["term_months"]); apr_min = float(row["apr_min"]); apr_max = float(row["apr_max"])
            down = float(row["minimum_down_payment_percent"]); max_age = int(row["maximum_vehicle_age_years"])
        except ValueError:
            errors.append(f"{prefix}: invalid numeric value"); continue
        if term not in TERMS: errors.append(f"{prefix}: invalid loan term")
        if not 0 <= apr_min <= apr_max <= 30: errors.append(f"{prefix}: invalid APR range")
        if not 0 <= down <= 100 or not 0 <= max_age <= 15: errors.append(f"{prefix}: invalid eligibility rule")
        disclaimer = row["disclaimer"].lower()
        if "estimate" not in disclaimer or "lender approval" not in disclaimer:
            errors.append(f"{prefix}: safe financing disclaimer is missing")
        if row["active"] not in {"true", "false"}: errors.append(f"{prefix}: invalid active flag")
        condition_counts[row["vehicle_condition"]] += 1
    for condition in CONDITIONS:
        condition_terms = {int(row["term_months"]) for row in rows if row["vehicle_condition"] == condition}
        if condition_terms != TERMS: errors.append(f"{condition}: missing required term options")
    return {
        "result": "PASS" if not errors else "FAIL", "dataset_as_of": "2026-08-25",
        "summary": {"financing_rules": len(rows), "active_rules": sum(row["active"] == "true" for row in rows)},
        "condition_distribution": dict(sorted(condition_counts.items())),
        "errors": errors, "error_count": len(errors), "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try: report = validate(args.input.resolve())
    except (FileNotFoundError, KeyError, csv.Error) as exc: print(f"FAIL: {exc}"); return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['financing_rules']} financing rules, {report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
