"""Export controlled financing reference rules to a Supabase-ready CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "database" / "reference" / "financing_rules.json"
DEFAULT_OUTPUT = ROOT / "database" / "seed" / "financing_options.csv"
FIELDS = ["financing_rule_id", "vehicle_condition", "term_months", "apr_min", "apr_max", "minimum_down_payment_percent", "maximum_vehicle_age_years", "active", "disclaimer"]


def generate(output: Path) -> None:
    data = json.loads(REFERENCE.read_text(encoding="utf-8"))
    rows = [{**rule, "active": str(rule["active"]).lower(), "disclaimer": data["disclaimer"]} for rule in data["rules"]]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    print(f"Generated {len(rows)} financing rules in {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(); generate(args.output.resolve()); return 0


if __name__ == "__main__":
    raise SystemExit(main())
