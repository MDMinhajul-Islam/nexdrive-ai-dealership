"""Authoritative vehicle lookups backed by Supabase."""

from typing import Any

from app.database import get_supabase
from app.schemas.vehicle import VehicleDetails


VEHICLE_COLUMNS = ",".join(
    (
        "vehicle_id",
        "vin",
        "stock_number",
        "make",
        "model",
        "year",
        "trim",
        "body_type",
        "condition",
        "mileage",
        "exterior_color",
        "interior_color",
        "fuel_type",
        "transmission",
        "drivetrain",
        "seating_capacity",
        "msrp",
        "sale_price",
        "vehicle_status",
        "test_drive_available",
        "warranty",
        "certification",
        "dealership_location",
    )
)


class VehicleNotFoundError(LookupError):
    """Raised when a requested vehicle does not exist."""


class VehicleDatabaseError(RuntimeError):
    """Raised when an authoritative vehicle lookup cannot complete."""


def _feature_names(rows: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        related = row.get("features")
        feature_records = related if isinstance(related, list) else [related]
        for feature in feature_records:
            if isinstance(feature, dict) and isinstance(feature.get("name"), str):
                names.add(feature["name"])
    return sorted(names)


def get_vehicle_details(vehicle_id: str) -> VehicleDetails:
    """Retrieve one vehicle and its normalized feature names."""
    try:
        client = get_supabase()
        vehicle_result = (
            client.table("vehicles")
            .select(VEHICLE_COLUMNS)
            .eq("vehicle_id", vehicle_id)
            .limit(1)
            .execute()
        )
        vehicle_rows = vehicle_result.data or []
    except Exception:
        raise VehicleDatabaseError("Vehicle database lookup failed") from None

    if not vehicle_rows:
        raise VehicleNotFoundError(vehicle_id)

    try:
        feature_result = (
            client.table("vehicle_features")
            .select("features(name)")
            .eq("vehicle_id", vehicle_id)
            .execute()
        )
        vehicle = dict(vehicle_rows[0])
        vehicle["features"] = _feature_names(feature_result.data or [])
        return VehicleDetails.model_validate(vehicle)
    except Exception:
        raise VehicleDatabaseError("Vehicle database lookup failed") from None
