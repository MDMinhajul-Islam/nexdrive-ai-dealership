"""Contracts for write workflows and financing estimates."""

from datetime import date, time
from typing import Any, Literal
from pydantic import BaseModel, Field


class LeadUpsertRequest(BaseModel):
    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    source: Literal["Website", "Inbound Call", "Paid Search", "Referral", "Social Media", "Walk-In", "Vehicle Marketplace"] = "Inbound Call"
    budget: int = Field(ge=3000, le=100000)
    vehicle_interest: str | None = Field(default=None, pattern=r"^VEH-[0-9]{6}$")
    purchase_timeline: Literal["Within 7 Days", "Within 30 Days", "1-3 Months", "3-6 Months", "Researching"]
    financing_needed: bool
    trade_in: bool
    assigned_salesperson: str = Field(pattern=r"^SP-[0-9]{3}$")
    notes: str = Field(default="", max_length=1000)


class LeadResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    created: bool
    lead: dict[str, Any]


class BookingRequest(BaseModel):
    lead_id: str = Field(pattern=r"^LEAD-[0-9]{6}$")
    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")
    salesperson_id: str = Field(pattern=r"^SP-[0-9]{3}$")
    appointment_date: date
    appointment_time: time
    notes: str = Field(default="", max_length=1000)


class BookingResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    created: bool
    appointment: dict[str, Any]


class FinancingEstimateRequest(BaseModel):
    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")
    term_months: Literal[36, 48, 60, 72]
    down_payment: float = Field(ge=0, le=100000)


class FinancingEstimateResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    vehicle_id: str
    sale_price: float
    down_payment: float
    amount_financed: float
    term_months: int
    estimated_apr: float
    estimated_monthly_payment: float
    disclaimer: str
