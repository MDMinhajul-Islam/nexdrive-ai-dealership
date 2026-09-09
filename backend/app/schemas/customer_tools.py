"""Contracts for customer history and test-drive slot tools."""

from datetime import date, time
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class CustomerHistory(BaseModel):
    customer: dict[str, Any]
    leads: list[dict[str, Any]]
    appointments: list[dict[str, Any]]


class CustomerHistoryResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    history: CustomerHistory
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_data(self) -> "CustomerHistoryResponse":
        self.data = {"history": self.history}
        return self


class CustomerHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")


class TestDriveSlotQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    requested_date: date = Field(
        validation_alias=AliasChoices("requested_date", "start_date")
    )
    days: int = Field(default=7, ge=1, le=14)
    salesperson_id: str | None = Field(default=None, pattern=r"^SP-[0-9]{3}$")
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("requested_date")
    @classmethod
    def reject_past_requested_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("requested_date cannot be in the past")
        return value


class TestDriveSlotDiscoveryRequest(TestDriveSlotQuery):
    """Retell request contract for vehicle-specific, read-only slot discovery."""

    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")


class TestDriveSlot(BaseModel):
    salesperson_id: str
    salesperson_name: str
    appointment_date: date
    appointment_time: time


class TestDriveSlotsResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    count: int
    slots: list[TestDriveSlot]
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_data(self) -> "TestDriveSlotsResponse":
        self.data = {"count": self.count, "slots": self.slots}
        return self
