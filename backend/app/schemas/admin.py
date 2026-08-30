"""Validated contracts for dealership inventory management."""

from typing import Literal
from pydantic import BaseModel, Field, model_validator

BodyType = Literal["SUV", "Sedan", "Truck", "Hatchback", "Coupe", "Wagon", "Minivan", "Van", "Convertible"]
Condition = Literal["New", "Used", "Certified Pre-Owned"]
Status = Literal["Available", "Reserved", "Sold", "Pending Sale", "In Service", "Arriving Soon", "Demo Vehicle", "No Test Drive"]


class VehicleCreateRequest(BaseModel):
    make: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=1980, le=2035)
    trim: str = Field(min_length=1, max_length=60)
    body_type: BodyType
    condition: Condition
    mileage: int = Field(ge=0, le=500000)
    exterior_color: str = Field(min_length=2, max_length=40)
    interior_color: str = Field(min_length=2, max_length=40)
    fuel_type: Literal["Gasoline", "Diesel", "Hybrid", "Plug-in Hybrid", "Electric"]
    transmission: Literal["Automatic", "Single-Speed Automatic", "Manual", "CVT"]
    drivetrain: Literal["FWD", "RWD", "AWD", "4WD"]
    seating_capacity: int = Field(ge=1, le=15)
    msrp: float = Field(gt=0, le=500000)
    sale_price: float = Field(gt=0, le=500000)
    vehicle_status: Status = "Available"
    test_drive_available: bool = True
    warranty: str = Field(min_length=2, max_length=200)
    certification: str = Field(default="None", max_length=100)
    dealership_location: str = Field(default="NexDrive Motors Plano", max_length=100)
    feature_ids: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def business_rules(self):
        if self.sale_price > self.msrp:
            raise ValueError("sale_price cannot exceed msrp")
        if self.condition == "New" and self.mileage > 500:
            raise ValueError("new vehicle mileage cannot exceed 500")
        if self.condition == "Certified Pre-Owned" and self.certification == "None":
            raise ValueError("certification is required for CPO inventory")
        if self.test_drive_available and self.vehicle_status not in ("Available", "Demo Vehicle"):
            raise ValueError("test drive is unavailable for this inventory status")
        return self


class VehicleUpdateRequest(BaseModel):
    sale_price: float | None = Field(default=None, gt=0, le=500000)
    mileage: int | None = Field(default=None, ge=0, le=500000)
    vehicle_status: Status | None = None
    test_drive_available: bool | None = None
    dealership_location: str | None = Field(default=None, min_length=2, max_length=100)
    feature_ids: list[str] | None = Field(default=None, max_length=40)


class LeadAdminUpdateRequest(BaseModel):
    lead_status: Literal["New", "Contacted", "Discovery", "Qualified", "Vehicle Recommended", "Test Drive", "Negotiation", "Financing", "Won", "Lost"] | None = None
    assigned_salesperson: str | None = Field(default=None, pattern=r"^SP-[0-9]{3}$")
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentAdminUpdateRequest(BaseModel):
    status: Literal["Requested", "Confirmed", "Completed", "Cancelled", "No Show", "Rescheduled"]
    notes: str | None = Field(default=None, max_length=1000)
