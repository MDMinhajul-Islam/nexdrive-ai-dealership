"""Typed contracts for read-only inventory tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.vehicle import VehicleDetails, VehicleImage


class InventorySearchFilters(BaseModel):
    make: str | None = Field(default=None, min_length=1, max_length=40)
    model: str | None = Field(default=None, min_length=1, max_length=60)
    body_type: Literal["SUV", "Sedan", "Truck", "Hatchback"] | None = None
    condition: Literal["New", "Used", "Certified Pre-Owned"] | None = None
    budget_min: int | None = Field(default=None, ge=0, le=100_000)
    budget_max: int | None = Field(default=None, ge=0, le=100_000)
    year_min: int | None = Field(default=None, ge=2016, le=2027)
    year_max: int | None = Field(default=None, ge=2016, le=2027)
    mileage_max: int | None = Field(default=None, ge=0, le=220_000)
    drivetrain: Literal["FWD", "RWD", "AWD", "4WD"] | None = None
    fuel_type: Literal["Gasoline", "Diesel", "Hybrid", "Plug-in Hybrid", "Electric"] | None = None
    seating_capacity_min: int | None = Field(default=None, ge=1, le=8)
    features: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("make", "model")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @field_validator("body_type", "condition", "drivetrain", "fuel_type", mode="before")
    @classmethod
    def normalize_choice_formatting(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        choices = {
            "suv": "SUV", "sedan": "Sedan", "truck": "Truck", "hatchback": "Hatchback",
            "new": "New", "used": "Used", "certified pre-owned": "Certified Pre-Owned",
            "fwd": "FWD", "rwd": "RWD", "awd": "AWD", "4wd": "4WD",
            "gasoline": "Gasoline", "diesel": "Diesel", "hybrid": "Hybrid",
            "plug-in hybrid": "Plug-in Hybrid", "electric": "Electric",
        }
        normalized = " ".join(value.split()).casefold()
        return choices.get(normalized, value)

    @field_validator("features")
    @classmethod
    def normalize_features(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.split()) for value in values]
        if any(not value for value in normalized):
            raise ValueError("Feature names cannot be blank")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("Feature names must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_ranges(self) -> "InventorySearchFilters":
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min cannot exceed budget_max")
        if self.year_min is not None and self.year_max is not None and self.year_min > self.year_max:
            raise ValueError("year_min cannot exceed year_max")
        return self

    def has_meaningful_criteria(self) -> bool:
        return any(
            value not in (None, [])
            for field, value in self.model_dump().items()
            if field != "limit"
        )


class InventorySearchVehicle(BaseModel):
    vehicle_id: str
    make: str
    model: str
    year: int
    trim: str
    body_type: str
    condition: str
    mileage: int
    fuel_type: str
    drivetrain: str
    seating_capacity: int
    sale_price: float
    vehicle_status: str
    test_drive_available: bool
    dealership_location: str
    features: list[str]
    primary_image_url: str | None = None
    images: list[VehicleImage] = Field(default_factory=list)
    image_url: str | None = None
    image_thumbnail_url: str | None = None
    image_source_url: str | None = None
    image_license: str | None = None
    image_provider: str | None = None
    image_is_representative: bool = False


class InventorySearchResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    count: int
    vehicles: list[InventorySearchVehicle]
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_data(self) -> "InventorySearchResponse":
        self.data = {"count": self.count, "vehicles": self.vehicles}
        return self


class ToolVehicleDetailsResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    vehicle: VehicleDetails
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_data(self) -> "ToolVehicleDetailsResponse":
        self.data = {"vehicle": self.vehicle}
        return self


class VehicleDetailsRequest(BaseModel):
    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")


class VehicleAvailability(BaseModel):
    vehicle_id: str
    vehicle_status: str
    test_drive_available: bool
    can_book_test_drive: bool
    reason: str


class VehicleAvailabilityResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    availability: VehicleAvailability
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_data(self) -> "VehicleAvailabilityResponse":
        self.data = {"availability": self.availability}
        return self
