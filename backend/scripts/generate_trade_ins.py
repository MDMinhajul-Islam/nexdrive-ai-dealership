"""Generate deterministic synthetic trade-in appraisal captures."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_OUTPUT = SEED_DIR / "trade_ins.csv"
FIELDS = [
    "trade_in_id", "lead_id", "customer_id", "make", "model", "year",
    "mileage", "condition", "estimated_value", "loan_balance", "notes",
]
CONDITION_FACTORS = {"Excellent": 1.08, "Good": 1.00, "Fair": 0.86, "Poor": 0.68}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def catalog_models() -> list[tuple[str, dict]]:
    with (ROOT / "database" / "reference" / "vehicle_catalog.json").open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    return [
        (make["make"], model)
        for make in catalog["makes"]
        for model in make["models"]
        if model.get("first_model_year", 2010) <= 2024
    ]


def generate(count: int, seed: int, output: Path) -> None:
    rng = random.Random(seed)
    customers = {row["customer_id"]: row for row in read_csv(SEED_DIR / "customers.csv")}
    eligible_leads = [
        row for row in read_csv(SEED_DIR / "leads.csv")
        if row["trade_in"] == "true" and customers[row["customer_id"]]["trade_in"] == "true"
    ]
    if count > len(eligible_leads):
        raise ValueError(f"Requested {count} trade-ins but only {len(eligible_leads)} eligible leads exist")
    models = catalog_models()
    rows: list[dict[str, object]] = []
    for index, lead in enumerate(rng.sample(eligible_leads, count), start=1):
        make, model = rng.choice(models)
        first_year = max(2010, model.get("first_model_year", 2010))
        year = rng.randint(first_year, 2024)
        age = 2026 - year
        mileage = int(max(2_000, min(220_000, rng.gauss(age * 12_000, 8_000))))
        condition = rng.choices(["Excellent", "Good", "Fair", "Poor"], weights=[12, 55, 27, 6], k=1)[0]
        depreciation = 0.82 * (0.88 ** max(0, age - 1))
        mileage_factor = max(0.58, 1 - max(0, mileage - age * 10_000) / 280_000)
        estimated_value = round(max(1_500, model["base_msrp"] * depreciation * mileage_factor * CONDITION_FACTORS[condition]) / 100) * 100
        loan_balance = 0 if rng.random() < 0.38 else round(estimated_value * rng.uniform(0.28, 1.22) / 100) * 100
        rows.append({
            "trade_in_id": f"TRD-{index:05d}", "lead_id": lead["lead_id"],
            "customer_id": lead["customer_id"], "make": make, "model": model["model"],
            "year": year, "mileage": mileage, "condition": condition,
            "estimated_value": int(estimated_value), "loan_balance": int(loan_balance),
            "notes": "Synthetic estimate only; final value requires an in-person appraisal.",
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} synthetic trade-ins in {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.count, args.seed, args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
