"""Generate deterministic synthetic NexDrive customer profiles."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "database" / "seed" / "customers.csv"
AS_OF = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)

FIRST_NAMES = [
    "Aaliyah", "Adrian", "Aisha", "Alex", "Amelia", "Andre", "Aria", "Avery",
    "Benjamin", "Bianca", "Caleb", "Camila", "Carlos", "Chloe", "Daniel", "David",
    "Diego", "Elena", "Ethan", "Fatima", "Gabriel", "Grace", "Hannah", "Harper",
    "Henry", "Isabella", "Isaac", "Jasmine", "Jordan", "Jose", "Layla", "Leo",
    "Liam", "Lucas", "Maya", "Mateo", "Mia", "Nadia", "Noah", "Olivia",
    "Omar", "Priya", "Rafael", "Riley", "Samuel", "Sofia", "Sophia", "Zoe",
]
LAST_NAMES = [
    "Adams", "Ahmed", "Allen", "Baker", "Brown", "Campbell", "Carter", "Chen",
    "Clark", "Davis", "Diaz", "Edwards", "Flores", "Garcia", "Gonzalez", "Green",
    "Gupta", "Hall", "Harris", "Hernandez", "Hill", "Jackson", "Johnson", "Khan",
    "Kim", "Lee", "Lewis", "Lopez", "Martin", "Martinez", "Miller", "Mitchell",
    "Moore", "Nelson", "Nguyen", "Patel", "Perez", "Ramirez", "Reed", "Rivera",
    "Robinson", "Rodriguez", "Scott", "Singh", "Taylor", "Thomas", "Walker", "Williams",
]
CITIES = {"Plano": 38, "Frisco": 16, "Dallas": 15, "McKinney": 11, "Allen": 8, "Carrollton": 6, "Richardson": 6}
BRANDS = ["Toyota", "Honda", "Ford", "Hyundai", "Kia", "Nissan", "Chevrolet", "Mazda", "Subaru", "Volkswagen", "No Preference"]
LEAD_SOURCES = {"Website": 28, "Inbound Call": 18, "Paid Search": 14, "Referral": 12, "Social Media": 10, "Walk-In": 9, "Vehicle Marketplace": 9}
PROFILE_WEIGHTS = {"Hot": 18, "Warm": 42, "Research": 32, "Edge Case": 8}
FIELDS = [
    "customer_id", "first_name", "last_name", "synthetic_phone", "synthetic_email",
    "city", "state", "preferred_vehicle_type", "preferred_brand", "budget_min",
    "budget_max", "financing_needed", "estimated_down_payment", "family_size",
    "trade_in", "purchase_timeline", "lead_source", "buyer_profile", "notes", "created_at",
]


def weighted_choice(rng: random.Random, weights: dict[str, int]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def budget_for(rng: random.Random, vehicle_type: str, profile: str) -> tuple[int, int]:
    ranges = {"Sedan": (16_000, 48_000), "SUV": (22_000, 62_000), "Truck": (26_000, 72_000), "Hatchback": (15_000, 38_000)}
    low, high = ranges[vehicle_type]
    if profile == "Edge Case" and rng.random() < 0.55:
        maximum = rng.randrange(7_000, 15_001, 500)
        return max(3_000, maximum - rng.randrange(2_000, 6_001, 500)), maximum
    maximum = rng.randrange(low + 7_000, high + 1, 500)
    spread = rng.randrange(5_000, min(18_000, maximum - low) + 1, 500)
    return maximum - spread, maximum


def timeline_for(rng: random.Random, profile: str) -> str:
    choices = {
        "Hot": (["Within 7 Days", "Within 30 Days"], [62, 38]),
        "Warm": (["Within 30 Days", "1-3 Months"], [55, 45]),
        "Research": (["1-3 Months", "3-6 Months", "Researching"], [25, 40, 35]),
        "Edge Case": (["Within 7 Days", "Within 30 Days", "Researching"], [25, 20, 55]),
    }
    values, weights = choices[profile]
    return rng.choices(values, weights=weights, k=1)[0]


def generate(count: int, seed: int, output: Path) -> None:
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for index in range(1, count + 1):
        profile = weighted_choice(rng, PROFILE_WEIGHTS)
        family_size = rng.choices(range(1, 9), weights=[18, 27, 18, 17, 9, 6, 3, 2], k=1)[0]
        if family_size >= 6 and profile != "Edge Case":
            vehicle_type = rng.choices(["SUV", "Truck"], weights=[88, 12], k=1)[0]
        else:
            vehicle_type = rng.choices(["SUV", "Sedan", "Truck", "Hatchback"], weights=[52, 29, 12, 7], k=1)[0]
        budget_min, budget_max = budget_for(rng, vehicle_type, profile)
        financing = rng.random() < {"Hot": 0.68, "Warm": 0.72, "Research": 0.61, "Edge Case": 0.78}[profile]
        down_payment = round(budget_max * rng.uniform(0.07, 0.24) / 100) * 100 if financing else 0
        trade_in = rng.random() < {"Hot": 0.42, "Warm": 0.36, "Research": 0.25, "Edge Case": 0.31}[profile]
        timeline = timeline_for(rng, profile)
        notes = {
            "Hot": "Specific near-term purchase intent; ready for inventory shortlist.",
            "Warm": "Preferences captured; comparing suitable vehicles and ownership costs.",
            "Research": "Early research stage; provide options without pressuring for commitment.",
            "Edge Case": "Requirements may conflict with budget or contact preferences; clarify before action.",
        }[profile]
        created_at = AS_OF - timedelta(days=rng.randint(0, 365), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        rows.append({
            "customer_id": f"CUST-{index:06d}",
            "first_name": rng.choice(FIRST_NAMES),
            "last_name": rng.choice(LAST_NAMES),
            "synthetic_phone": f"+1-555-010-{index:04d}",
            "synthetic_email": f"customer{index:06d}@nexdrive.example",
            "city": weighted_choice(rng, CITIES), "state": "TX",
            "preferred_vehicle_type": vehicle_type,
            "preferred_brand": rng.choices(BRANDS, weights=[13, 12, 11, 9, 8, 8, 9, 7, 7, 6, 10], k=1)[0],
            "budget_min": budget_min, "budget_max": budget_max,
            "financing_needed": str(financing).lower(),
            "estimated_down_payment": int(down_payment), "family_size": family_size,
            "trade_in": str(trade_in).lower(), "purchase_timeline": timeline,
            "lead_source": weighted_choice(rng, LEAD_SOURCES), "buyer_profile": profile,
            "notes": notes, "created_at": created_at.isoformat(),
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows):,} synthetic customers in {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    return args


if __name__ == "__main__":
    args = parse_args()
    generate(args.count, args.seed, args.output.resolve())
