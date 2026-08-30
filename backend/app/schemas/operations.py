"""Contracts for trade-in, escalation and traceable call outcomes."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class TradeInCaptureRequest(BaseModel):
    lead_id: str = Field(pattern=r"^LEAD-[0-9]{6}$")
    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    make: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=2010, le=2024)
    mileage: int = Field(ge=0, le=220000)
    condition: Literal["Excellent", "Good", "Fair", "Poor"]
    loan_balance: int = Field(default=0, ge=0, le=125000)


class EscalationRequest(BaseModel):
    session_id: str = Field(pattern=r"^CALL-[A-Z0-9-]{6,40}$")
    customer_id: str | None = Field(default=None, pattern=r"^CUST-[0-9]{6}$")
    reason: Literal["Negotiation", "Financing Approval", "Complaint", "Accessibility", "Policy Question", "Tool Failure", "Customer Request", "Other"]
    summary: str = Field(min_length=3, max_length=1000)


class ConversationOutcomeRequest(BaseModel):
    session_id: str = Field(pattern=r"^CALL-[A-Z0-9-]{6,40}$")
    channel: Literal["Phone", "Web Voice"]
    status: Literal["Completed", "Escalated", "Dropped", "Failed"]
    outcome: Literal["Discovery", "Vehicle Recommended", "Lead Created", "Test Drive Booked", "Escalated", "No Action", "Failed"]
    customer_id: str | None = Field(default=None, pattern=r"^CUST-[0-9]{6}$")
    lead_id: str | None = Field(default=None, pattern=r"^LEAD-[0-9]{6}$")
    appointment_id: str | None = Field(default=None, pattern=r"^APT-[0-9]{6}$")
    summary: str = Field(default="", max_length=1500)
    started_at: datetime
