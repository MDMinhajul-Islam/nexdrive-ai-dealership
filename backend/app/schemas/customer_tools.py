"""Contracts for customer history and test-drive slot tools."""

from datetime import date, time
from typing import Any, Literal

from pydantic import BaseModel, Field


class CustomerHistory(BaseModel):
    customer: dict[str, Any]
    leads: list[dict[str, Any]]
    appointments: list[dict[str, Any]]


class CustomerHistoryResponse(BaseModel):
    success: bool = True
    source: Literal["database"] = "database"
    history: CustomerHistory


class TestDriveSlotQuery(BaseModel):
    start_date: date
    days: int = Field(default=7, ge=1, le=14)
    salesperson_id: str | None = Field(default=None, pattern=r"^SP-[0-9]{3}$")
    limit: int = Field(default=20, ge=1, le=50)


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
