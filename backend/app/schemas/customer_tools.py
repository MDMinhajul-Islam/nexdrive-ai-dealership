"""Contracts for customer history and test-drive slot tools."""

from datetime import date, time
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.dealership_time import dealership_today


class CustomerHistory(BaseModel):
    customer: dict[str, Any]
    leads: list[dict[str, Any]]
    appointments: list[dict[str, Any]]


class CustomerHistoryResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    history: CustomerHistory
    message: str = ""


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
        if value < dealership_today():
            raise ValueError("requested_date cannot be in the past")
        return value


class TestDriveSlotDiscoveryRequest(TestDriveSlotQuery):
    """Retell request contract for vehicle-specific, read-only slot discovery."""

    vehicle_id: str = Field(pattern=r"^VEH-[0-9]{6}$")

    @model_validator(mode="before")
    @classmethod
    def extract_retell_envelope(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "args" in data:
                if "name" not in data:
                    raise ValueError(
                        "Malformed Retell wrapper: 'args' present without 'name'"
                    )
                if data["name"] != "get_test_drive_slots":
                    raise ValueError(
                        f"Invalid function name in wrapper: expected 'get_test_drive_slots', got '{data['name']}'"
                    )
                if not isinstance(data["args"], dict):
                    raise ValueError("Malformed Retell wrapper: 'args' must be a dictionary")
                return data["args"]
            if "call" in data and "name" in data:
                if data["name"] != "get_test_drive_slots":
                    raise ValueError(
                        f"Invalid function name in wrapper: expected 'get_test_drive_slots', got '{data['name']}'"
                    )
                raise ValueError("Malformed Retell wrapper: missing 'args'")
            if "call" in data or "name" in data:
                raise ValueError(
                    "Ambiguous payload: contains Retell envelope fields mixed "
                    "with direct fields or incomplete wrapper"
                )
        return data


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