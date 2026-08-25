"""Database-grounded lead, booking, scoring, and financing workflows."""

import logging
from datetime import date, datetime
from math import pow
from typing import Any

from app.schemas.business_tools import *

logger = logging.getLogger("nexdrive.audit")


class BusinessToolError(RuntimeError): pass
class BusinessConflictError(RuntimeError): pass
class BusinessNotFoundError(RuntimeError): pass


def score_lead(request: LeadUpsertRequest) -> tuple[int, str]:
    timeline = {"Within 7 Days": 45, "Within 30 Days": 35, "1-3 Months": 25, "3-6 Months": 15, "Researching": 5}
    score = timeline[request.purchase_timeline] + (20 if request.vehicle_interest else 0) + (10 if request.trade_in else 0) + (10 if request.financing_needed else 5) + min(15, request.budget // 10000)
    score = min(100, score)
    return score, "Hot" if score >= 70 else "Warm" if score >= 40 else "Cold"


def _next_id(client: Any, table: str, field: str, prefix: str) -> str:
    result = client.table(table).select(field).order(field, desc=True).limit(1).execute()
    number = int(result.data[0][field].split("-")[1]) + 1 if result.data else 1
    return f"{prefix}-{number:06d}"


def create_or_update_lead(request: LeadUpsertRequest, client: Any) -> LeadResponse:
    try:
        if not client.table("customers").select("customer_id").eq("customer_id", request.customer_id).limit(1).execute().data:
            raise BusinessNotFoundError("Customer not found")
        score, temperature = score_lead(request)
        existing = client.table("leads").select("*").eq("customer_id", request.customer_id).not_.in_("lead_status", ["Won", "Lost"]).order("updated_at", desc=True).limit(1).execute().data
        payload = request.model_dump()
        payload.update({"lead_score": score, "lead_temperature": temperature, "updated_at": datetime.utcnow().isoformat(), "next_followup_date": date.today().isoformat()})
        if existing:
            lead_id = existing[0]["lead_id"]
            result = client.table("leads").update(payload).eq("lead_id", lead_id).execute().data[0]
            created = False
        else:
            payload.update({"lead_id": _next_id(client, "leads", "lead_id", "LEAD"), "lead_status": "New", "created_at": datetime.utcnow().isoformat()})
            result = client.table("leads").insert(payload).execute().data[0]
            created = True
        logger.info("lead_upsert success=%s created=%s lead_id=%s", True, created, result["lead_id"])
        return LeadResponse(created=created, lead=result)
    except (BusinessNotFoundError, BusinessConflictError): raise
    except Exception as exc: raise BusinessToolError("Lead write failed") from exc


def create_test_drive(request: BookingRequest, client: Any) -> BookingResponse:
    try:
        existing = client.table("appointments").select("*").eq("lead_id", request.lead_id).limit(1).execute().data
        if existing:
            return BookingResponse(created=False, appointment=existing[0])
        vehicle = client.table("vehicles").select("vehicle_status,test_drive_available").eq("vehicle_id", request.vehicle_id).limit(1).execute().data
        if not vehicle: raise BusinessNotFoundError("Vehicle not found")
        if vehicle[0]["vehicle_status"] not in ("Available", "Demo Vehicle") or not vehicle[0]["test_drive_available"]:
            raise BusinessConflictError("Vehicle is unavailable for test drive")
        person = client.table("salespeople").select("working_days,shift_start,shift_end,active").eq("salesperson_id", request.salesperson_id).limit(1).execute().data
        if not person or not person[0]["active"]: raise BusinessConflictError("Salesperson is unavailable")
        slot_time = request.appointment_time.strftime("%H:%M")
        if request.appointment_date.strftime("%A") not in person[0]["working_days"] or not (str(person[0]["shift_start"])[:5] <= slot_time < str(person[0]["shift_end"])[:5]):
            raise BusinessConflictError("Requested time is outside the salesperson shift")
        clash = client.table("appointments").select("appointment_id").eq("salesperson_id", request.salesperson_id).eq("appointment_date", request.appointment_date.isoformat()).eq("appointment_time", slot_time).in_("status", ["Requested", "Confirmed", "Rescheduled"]).limit(1).execute().data
        if clash: raise BusinessConflictError("Requested slot is no longer available")
        payload = request.model_dump(mode="json")
        payload.update({"appointment_id": _next_id(client, "appointments", "appointment_id", "APT"), "appointment_type": "Test Drive", "status": "Confirmed", "created_by": "Voice Agent", "created_at": datetime.utcnow().isoformat()})
        result = client.table("appointments").insert(payload).execute().data[0]
        logger.info("booking_create success=True appointment_id=%s", result["appointment_id"])
        return BookingResponse(created=True, appointment=result)
    except (BusinessNotFoundError, BusinessConflictError): raise
    except Exception as exc: raise BusinessToolError("Booking failed") from exc


def estimate_financing(request: FinancingEstimateRequest, client: Any) -> FinancingEstimateResponse:
    try:
        vehicle = client.table("vehicles").select("vehicle_id,condition,sale_price,year").eq("vehicle_id", request.vehicle_id).limit(1).execute().data
        if not vehicle: raise BusinessNotFoundError("Vehicle not found")
        rule = client.table("financing_options").select("*").eq("vehicle_condition", vehicle[0]["condition"]).eq("term_months", request.term_months).eq("active", True).limit(1).execute().data
        if not rule: raise BusinessNotFoundError("No applicable financing rule")
        price = float(vehicle[0]["sale_price"]); minimum = price * float(rule[0]["minimum_down_payment_percent"]) / 100
        if request.down_payment < minimum: raise BusinessConflictError(f"Minimum down payment is {minimum:.2f}")
        principal = price - request.down_payment
        if principal <= 0: raise BusinessConflictError("Down payment must be less than sale price")
        apr = (float(rule[0]["apr_min"]) + float(rule[0]["apr_max"])) / 2; monthly_rate = apr / 1200
        payment = principal * monthly_rate * pow(1 + monthly_rate, request.term_months) / (pow(1 + monthly_rate, request.term_months) - 1)
        return FinancingEstimateResponse(vehicle_id=request.vehicle_id, sale_price=price, down_payment=request.down_payment, amount_financed=round(principal, 2), term_months=request.term_months, estimated_apr=round(apr, 2), estimated_monthly_payment=round(payment, 2), disclaimer=rule[0]["disclaimer"])
    except (BusinessNotFoundError, BusinessConflictError): raise
    except Exception as exc: raise BusinessToolError("Financing estimate failed") from exc
