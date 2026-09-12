"""Dealership-local time helpers used by scheduling rules."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


DEALERSHIP_TIMEZONE = ZoneInfo("America/Chicago")


def dealership_now() -> datetime:
    """Return the current time at NexDrive's Texas dealerships."""
    return datetime.now(DEALERSHIP_TIMEZONE)


def dealership_today() -> date:
    return dealership_now().date()
