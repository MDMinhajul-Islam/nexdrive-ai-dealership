"""Generate deterministic synthetic salespeople, leads, appointments and trade-ins."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "database" / "seed"
AS_OF = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def read_rows(name: str) -> list[dict[str, str]]:
    with (SEED_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(name: str, fields: list[str], rows: list[dict[str, object]]) -> None:
    with (SEED_DIR / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def lead_score(customer: dict[str, str], has_vehicle: bool) -> tuple[int, str]:
    score = {"Hot": 70, "Warm": 50, "Research": 30, "Edge Case": 20}[customer["buyer_profile"]]
    reasons = [f"profile={customer['buyer_profile']}"]
    if customer["purchase_timeline"] == "Within 7 Days": score += 15; reasons.append("near-term")
    elif customer["purchase_timeline"] == "Within 30 Days": score += 8; reasons.append("30-day")
    if has_vehicle: score += 7; reasons.append("vehicle selected")
    if customer["financing_needed"] == "true" and int(customer["estimated_down_payment"]) > 0:
        score += 5; reasons.append("down payment")
    return min(score, 100), ", ".join(reasons)


def generate(seed: int = 20260830) -> None:
    rng = random.Random(seed)
    customers, vehicles = read_rows("customers.csv"), read_rows("vehicles.csv")
    locations = sorted({row["dealership_location"] for row in vehicles})
    salespeople = [{"salesperson_id": f"SALES-{i:03d}", "name": f"NexDrive Advisor {i}",
                    "synthetic_email": f"advisor{i:03d}@nexdrive.example",
                    "dealership_location": locations[(i - 1) % len(locations)], "active": "true"}
                   for i in range(1, 25)]
    write_rows("salespeople.csv", list(salespeople[0]), salespeople)

    leads: list[dict[str, object]] = []
    for i, customer in enumerate(customers[:3000], 1):
        vehicle = vehicles[rng.randrange(len(vehicles))] if rng.random() < .82 else None
        score, reason = lead_score(customer, vehicle is not None)
        created = AS_OF - timedelta(days=rng.randint(0, 120), hours=rng.randint(0, 23))
        leads.append({"lead_id": f"LEAD-{i:06d}", "customer_id": customer["customer_id"],
                      "vehicle_id": vehicle["vehicle_id"] if vehicle else "",
                      "salesperson_id": salespeople[(i - 1) % len(salespeople)]["salesperson_id"],
                      "source": customer["lead_source"],
                      "status": rng.choices(["New","Contacted","Qualified","Appointment Set","Won","Lost"], [22,22,24,18,8,6])[0],
                      "score": score, "score_reason": reason, "notes": customer["notes"],
                      "created_at": created.isoformat()})
    write_rows("leads.csv", list(leads[0]), leads)

    appointments: list[dict[str, object]] = []
    eligible = [x for x in leads if x["vehicle_id"]]
    for i, lead in enumerate(eligible[:1200], 1):
        starts = AS_OF + timedelta(days=rng.randint(-30, 60), hours=rng.randint(0, 7))
        appointments.append({"appointment_id": f"APPT-{i:06d}", "customer_id": lead["customer_id"],
            "vehicle_id": lead["vehicle_id"], "salesperson_id": lead["salesperson_id"],
            "appointment_type": rng.choices(["Test Drive","Consultation","Trade-In Appraisal"],[70,22,8])[0],
            "starts_at": starts.isoformat(), "duration_minutes": 45,
            "status": "Completed" if starts < AS_OF else "Scheduled", "notes": "Synthetic demo appointment."})
    write_rows("appointments.csv", list(appointments[0]), appointments)

    trade_customers = [c for c in customers if c["trade_in"] == "true"][:900]
    trade_ins = []
    for i, customer in enumerate(trade_customers, 1):
        year = rng.randint(2008, 2024); mileage = rng.randint(8000, 180000)
        condition = rng.choices(["Excellent","Good","Fair","Poor"],[12,53,29,6])[0]
        value = max(750, (year - 2000) * 1150 - mileage * .045 + {"Excellent":3000,"Good":1500,"Fair":0,"Poor":-1800}[condition])
        trade_ins.append({"trade_in_id": f"TRADE-{i:06d}", "customer_id": customer["customer_id"],
            "year": year, "make": rng.choice(["Toyota","Honda","Ford","Nissan","Chevrolet"]),
            "model": "Synthetic Trade Vehicle", "mileage": mileage, "condition": condition,
            "estimated_value": round(value, 2), "status": "Estimated"})
    write_rows("trade_ins.csv", list(trade_ins[0]), trade_ins)
    print(f"Generated {len(salespeople)} salespeople, {len(leads)} leads, {len(appointments)} appointments, and {len(trade_ins)} trade-ins.")


def main() -> int:
    generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
