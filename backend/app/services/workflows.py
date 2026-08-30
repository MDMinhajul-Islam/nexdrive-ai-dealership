"""Seed-backed deterministic workflow service used locally and in demos."""

import csv
import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from threading import RLock

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "database" / "seed"


def _read(name: str) -> list[dict[str, str]]:
    with (SEED / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class WorkflowService:
    def __init__(self) -> None:
        self.customers = {r["customer_id"]: r for r in _read("customers.csv")}
        self.vehicles = {r["vehicle_id"]: r for r in _read("vehicles.csv")}
        self.leads = {r["lead_id"]: r for r in _read("leads.csv")}
        self.appointments = {r["appointment_id"]: r for r in _read("appointments.csv")}
        self.trade_ins = _read("trade_ins.csv")
        self._idempotency: dict[str, tuple[str, dict]] = {}
        self._lock = RLock()

    def _require_customer(self, customer_id: str) -> dict[str, str]:
        if customer_id not in self.customers:
            raise HTTPException(404, "Customer not found")
        return self.customers[customer_id]

    def _require_vehicle(self, vehicle_id: str) -> dict[str, str]:
        if vehicle_id not in self.vehicles:
            raise HTTPException(404, "Vehicle not found")
        return self.vehicles[vehicle_id]

    @staticmethod
    def score(customer: dict[str, str], vehicle_id: str | None) -> tuple[int, str]:
        score = {"Hot": 70, "Warm": 50, "Research": 30, "Edge Case": 20}[customer["buyer_profile"]]
        reasons = [f"buyer profile: {customer['buyer_profile']}"]
        if customer["purchase_timeline"] == "Within 7 Days": score += 15; reasons.append("purchase within 7 days")
        elif customer["purchase_timeline"] == "Within 30 Days": score += 8; reasons.append("purchase within 30 days")
        if vehicle_id: score += 7; reasons.append("specific vehicle selected")
        if customer["financing_needed"] == "true" and int(customer["estimated_down_payment"]) > 0:
            score += 5; reasons.append("down payment identified")
        return min(score, 100), "; ".join(reasons)

    def create_lead(self, payload: dict, key: str | None) -> tuple[dict, bool]:
        customer = self._require_customer(payload["customer_id"])
        if payload.get("vehicle_id"): self._require_vehicle(payload["vehicle_id"])
        fingerprint = repr(sorted(payload.items()))
        with self._lock:
            if key and key in self._idempotency:
                old_fingerprint, response = self._idempotency[key]
                if old_fingerprint != fingerprint: raise HTTPException(409, "Idempotency key reused with different payload")
                return response, True
            lead_id = f"LEAD-{len(self.leads) + 1:06d}"
            score, reason = self.score(customer, payload.get("vehicle_id"))
            row = {**payload, "lead_id": lead_id, "status": "New", "score": score,
                   "score_reason": reason, "created_at": datetime.now(timezone.utc).isoformat()}
            self.leads[lead_id] = row
            if key: self._idempotency[key] = (fingerprint, row)
            return row, False

    def update_lead(self, lead_id: str, changes: dict) -> dict:
        if lead_id not in self.leads: raise HTTPException(404, "Lead not found")
        if changes.get("vehicle_id"): self._require_vehicle(changes["vehicle_id"])
        row = self.leads[lead_id]; row.update({k: v for k, v in changes.items() if v is not None})
        score, reason = self.score(self._require_customer(row["customer_id"]), row.get("vehicle_id"))
        row.update(score=score, score_reason=reason, updated_at=datetime.now(timezone.utc).isoformat())
        return row

    def create_appointment(self, payload: dict, key: str | None) -> tuple[dict, bool]:
        self._require_customer(payload["customer_id"]); vehicle = self._require_vehicle(payload["vehicle_id"])
        if vehicle["test_drive_available"] != "true" and payload["appointment_type"] == "Test Drive":
            raise HTTPException(409, "Vehicle is not available for a test drive")
        fingerprint = repr(sorted((k, str(v)) for k, v in payload.items()))
        with self._lock:
            if key and key in self._idempotency:
                old, response = self._idempotency[key]
                if old != fingerprint: raise HTTPException(409, "Idempotency key reused with different payload")
                return response, True
            starts = payload["starts_at"]
            if starts <= datetime.now(timezone.utc): raise HTTPException(422, "Appointment must be in the future")
            row = {**payload, "starts_at": starts.isoformat(), "appointment_id": f"APPT-{len(self.appointments)+1:06d}",
                   "status": "Scheduled", "created_at": datetime.now(timezone.utc).isoformat()}
            self.appointments[row["appointment_id"]] = row
            if key: self._idempotency[key] = (fingerprint, row)
            return row, False

    def history(self, customer_id: str) -> dict:
        customer = self._require_customer(customer_id)
        return {"customer": customer,
                "leads": [x for x in self.leads.values() if x["customer_id"] == customer_id],
                "appointments": [x for x in self.appointments.values() if x["customer_id"] == customer_id],
                "trade_ins": [x for x in self.trade_ins if x["customer_id"] == customer_id]}

    @staticmethod
    def financing(payload: dict) -> dict:
        score, term = payload["credit_score"], payload["term_months"]
        tier, base = (("Excellent", Decimal("4.49")) if score >= 740 else ("Good", Decimal("6.49")) if score >= 670 else
                      ("Fair", Decimal("10.49")) if score >= 580 else ("Building", Decimal("15.99")))
        apr = base + {36: Decimal("0"), 48: Decimal("0.35"), 60: Decimal("0.85"), 72: Decimal("1.50")}[term]
        tax = payload["vehicle_price"] * payload["tax_rate"]
        principal = payload["vehicle_price"] + tax - payload["down_payment"] - payload["trade_in_value"]
        monthly_rate = apr / Decimal(1200)
        payment = principal * monthly_rate / (Decimal(1) - Decimal(str(math.pow(float(1 + monthly_rate), -term))))
        money = lambda x: x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {"credit_tier": tier, "apr_percent": money(apr), "amount_financed": money(principal),
                "estimated_monthly_payment": money(payment), "term_months": term,
                "estimated_total_interest": money(payment * term - principal),
                "disclaimer": "Estimate only; not a credit decision or financing offer."}


workflow_service = WorkflowService()
