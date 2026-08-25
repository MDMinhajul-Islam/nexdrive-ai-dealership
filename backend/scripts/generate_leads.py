"""Generate deterministic synthetic NexDrive sales leads with valid relationships."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
DEFAULT_OUTPUT = SEED_DIR / "leads.csv"
AS_OF = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
FIELDS = [
    "lead_id", "customer_id", "source", "created_at", "lead_status", "budget",
    "vehicle_interest", "purchase_timeline", "financing_needed", "trade_in",
    "lead_score", "lead_temperature", "assigned_salesperson", "next_followup_date", "notes",
]
ACTIVE_SALESPEOPLE = ["SP-001", "SP-002", "SP-003", "SP-004", "SP-005", "SP-006", "SP-007", "SP-008", "SP-010"]
ACTION_STATUSES = {"Test Drive", "Negotiation", "Financing", "Won"}
TERMINAL_STATUSES = {"Won", "Lost"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_status(rng: random.Random, profile: str) -> str:
    values = {
        "Hot": (["Qualified", "Vehicle Recommended", "Test Drive", "Negotiation", "Financing", "Won"], [12, 18, 24, 18, 14, 14]),
        "Warm": (["Contacted", "Discovery", "Qualified", "Vehicle Recommended", "Test Drive", "Negotiation"], [12, 18, 27, 24, 13, 6]),
        "Research": (["New", "Contacted", "Discovery", "Qualified", "Lost"], [24, 25, 28, 15, 8]),
        "Edge Case": (["New", "Contacted", "Discovery", "Lost"], [28, 18, 20, 34]),
    }
    statuses, weights = values[profile]
    return rng.choices(statuses, weights=weights, k=1)[0]


def assign_salesperson(rng: random.Random, customer: dict[str, str]) -> str:
    if customer["financing_needed"] == "true" and rng.random() < 0.18:
        return "SP-005"
    if customer["preferred_vehicle_type"] == "Truck":
        return rng.choices(["SP-002", "SP-007"], weights=[82, 18], k=1)[0]
    if customer["preferred_vehicle_type"] == "SUV":
        return rng.choices(["SP-001", "SP-006", "SP-007"], weights=[42, 42, 16], k=1)[0]
    return rng.choice(ACTIVE_SALESPEOPLE)


def select_vehicle(
    rng: random.Random,
    customer: dict[str, str],
    vehicles: list[dict[str, str]],
    required: bool,
    available_only: bool,
) -> str:
    if not required and rng.random() < (0.36 if customer["buyer_profile"] == "Edge Case" else 0.12):
        return ""
    budget_min, budget_max = int(customer["budget_min"]), int(customer["budget_max"])
    candidates = [
        vehicle for vehicle in vehicles
        if vehicle["body_type"] == customer["preferred_vehicle_type"]
        and budget_min <= int(vehicle["sale_price"]) <= budget_max
        and (customer["preferred_brand"] == "No Preference" or vehicle["make"] == customer["preferred_brand"])
    ]
    if not candidates and customer["preferred_brand"] != "No Preference":
        candidates = [
            vehicle for vehicle in vehicles
            if vehicle["body_type"] == customer["preferred_vehicle_type"]
            and budget_min <= int(vehicle["sale_price"]) <= budget_max
        ]
    if not candidates:
        return ""
    available = [vehicle for vehicle in candidates if vehicle["vehicle_status"] == "Available"]
    if available_only:
        return rng.choice(available)["vehicle_id"] if available else ""
    pool = available if available and rng.random() < 0.88 else candidates
    return rng.choice(pool)["vehicle_id"]


def calculate_score(customer: dict[str, str], vehicle_interest: str, status: str) -> int:
    timeline_points = {"Within 7 Days": 30, "Within 30 Days": 20}.get(customer["purchase_timeline"], 0)
    score = timeline_points + 15  # budget is established for every generated lead
    score += 15 if vehicle_interest else 0
    score += 20 if status in ACTION_STATUSES else 0
    score += 10 if customer["financing_needed"] == "true" else 0
    score += 5 if customer["trade_in"] == "true" else 0
    return min(100, score)


def generate(count: int, seed: int, output: Path) -> None:
    rng = random.Random(seed)
    customers = read_csv(SEED_DIR / "customers.csv")
    vehicles = read_csv(SEED_DIR / "vehicles.csv")
    salespeople = read_csv(SEED_DIR / "salespeople.csv")
    active_ids = {row["salesperson_id"] for row in salespeople if row["active"] == "true"}
    if count > len(customers):
        raise ValueError(f"Requested {count} leads but only {len(customers)} customers exist")
    if not set(ACTIVE_SALESPEOPLE) <= active_ids:
        raise ValueError("Expected active salespeople are missing from salespeople.csv")

    selected_customers = rng.sample(customers, count)
    rows: list[dict[str, object]] = []
    for index, customer in enumerate(selected_customers, start=1):
        status = choose_status(rng, customer["buyer_profile"])
        downstream = status in {"Vehicle Recommended", *ACTION_STATUSES}
        vehicle_interest = select_vehicle(rng, customer, vehicles, required=downstream, available_only=downstream)
        # A downstream stage cannot claim a selected vehicle when the inventory has no match.
        if not vehicle_interest and status in {"Vehicle Recommended", *ACTION_STATUSES}:
            status = "Qualified"
        score = calculate_score(customer, vehicle_interest, status)
        temperature = "Hot" if score >= 70 else "Warm" if score >= 40 else "Cold"
        customer_created = datetime.fromisoformat(customer["created_at"])
        available_seconds = max(0, int((AS_OF - customer_created).total_seconds()))
        created_at = customer_created + timedelta(seconds=rng.randint(0, available_seconds))
        followup = "" if status in TERMINAL_STATUSES else (AS_OF.date() + timedelta(days=rng.randint(1, 14))).isoformat()
        rows.append({
            "lead_id": f"LEAD-{index:06d}", "customer_id": customer["customer_id"],
            "source": customer["lead_source"], "created_at": created_at.isoformat(),
            "lead_status": status, "budget": customer["budget_max"],
            "vehicle_interest": vehicle_interest,
            "purchase_timeline": customer["purchase_timeline"],
            "financing_needed": customer["financing_needed"], "trade_in": customer["trade_in"],
            "lead_score": score, "lead_temperature": temperature,
            "assigned_salesperson": assign_salesperson(rng, customer),
            "next_followup_date": followup,
            "notes": "Synthetic CRM lead generated from the customer's captured preferences.",
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows):,} synthetic leads in {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=20260827)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    generate(args.count, args.seed, args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
