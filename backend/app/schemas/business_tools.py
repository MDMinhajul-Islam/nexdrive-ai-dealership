"""Contracts for write workflows and financing estimates."""

from datetime import date, time
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator



class ResolveCustomerRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=10, max_length=20)
    email: str | None = None

    @model_validator(mode="before")
    @classmethod
    def extract_retell_envelope(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "args" in data:
                return data["args"]
        return data

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v: Any) -> Any:
        import re
        if not v:
            return None
        if not isinstance(v, str):
            return v
        email = v.lower()
        email = re.sub(r'\s+dot\s+', '.', email)
        email = re.sub(r'\s+at the rate of\s+', '@', email)
        email = re.sub(r'\s+at\s+', '@', email)
        email = email.replace('g mail', 'gmail')
        email = email.replace(' ', '')
        if '@' not in email or '.' not in email:
            raise ValueError('Invalid email format after normalization')
        return email

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v: Any) -> Any:
        import re
        if not v:
            return v
        if not isinstance(v, str):
            return v
        p = re.sub(r'\D', '', v)
        if p.startswith('1') and len(p) == 11:
            p = p[1:]
        if len(p) != 10:
            raise ValueError('Phone number must contain exactly 10 digits')
        return f"+1-{p[:3]}-{p[3:6]}-{p[6:]}" 


class ResolveCustomerResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    created: bool
    customer_id: str
    message: str = ""




class LeadUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    source: Literal["Website", "Inbound Call", "Paid Search", "Referral", "Social Media", "Walk-In", "Vehicle Marketplace"] = "Inbound Call"

    budget: int | None = Field(default=None, ge=3000, le=100000)
    vehicle_interest: str | None = Field(default=None, pattern=r"^VEH-[0-9]{6}$")
    purchase_timeline: Literal["Within 7 Days", "Within 30 Days", "1-3 Months", "3-6 Months", "Researching"] | None = None
    financing_needed: bool | None = None
    trade_in: bool | None = None
    assigned_salesperson: str | None = Field(default=None, pattern=r"^SP-[0-9]{3}$")
    test_drive_requested: bool = False
    notes: str = Field(default="", max_length=1000)


class LeadResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    created: bool
    lead: dict[str, Any]
    message: str = ""


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(pattern=r"^LEAD-[0-9]{6}$")
    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")
    salesperson_id: str = Field(pattern=r"^SP-[0-9]{3}$")
    appointment_date: date
    appointment_time: time
    notes: str = Field(default="", max_length=1000)

    @field_validator("appointment_date")
    @classmethod
    def reject_past_appointment_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("appointment_date cannot be in the past")
        return value

    @field_validator("appointment_time")
    @classmethod
    def require_bookable_time_boundary(cls, value: time) -> time:
        if value.minute not in (0, 30) or value.second or value.microsecond:
            raise ValueError("appointment_time must be on a 30-minute boundary")
        return value


class BookingResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    created: bool
    appointment: dict[str, Any]
    message: str = ""


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
