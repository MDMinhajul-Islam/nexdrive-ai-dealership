"""Request and response models for dealership workflows."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LeadInput(BaseModel):
    customer_id: str
    vehicle_id: str | None = None
    source: str = "Voice Agent"
    notes: str = ""


class LeadUpdate(BaseModel):
    vehicle_id: str | None = None
    status: Literal["New", "Contacted", "Qualified", "Appointment Set", "Won", "Lost"] | None = None
    notes: str | None = None


class AppointmentInput(BaseModel):
    customer_id: str
    vehicle_id: str
    starts_at: datetime
    appointment_type: Literal["Test Drive", "Consultation", "Trade-In Appraisal"] = "Test Drive"
    duration_minutes: int = Field(45, ge=15, le=180)
    notes: str = ""


class FinancingInput(BaseModel):
    vehicle_price: Decimal = Field(gt=0, le=500_000)
    down_payment: Decimal = Field(ge=0)
    trade_in_value: Decimal = Field(0, ge=0)
    credit_score: int = Field(ge=300, le=850)
    term_months: Literal[36, 48, 60, 72] = 60
    tax_rate: Decimal = Field(Decimal("0.0625"), ge=0, le=Decimal("0.20"))

    @model_validator(mode="after")
    def validate_equity(self) -> "FinancingInput":
        if self.down_payment + self.trade_in_value >= self.vehicle_price * Decimal("1.2"):
            raise ValueError("down payment and trade-in cannot exceed price plus estimated tax")
        return self
