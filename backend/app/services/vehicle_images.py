"""Attach cached, licensed representative photos without exposing provider keys."""

from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Any

from supabase import Client

_LOCK = Lock()
_CACHE: dict[str, dict[str, Any]] = {}
_LOADED_AT = 0.0
_TTL_SECONDS = 300


def _key(make: object, model: object, year: object | None = None) -> str:
    prefix = f"{year}|" if year else ""
    return f"{prefix}{str(make).strip().lower()}|{str(model).strip().lower()}"


def _load(db: Client) -> dict[str, dict[str, Any]]:
    global _CACHE, _LOADED_AT
    now = monotonic()
    if _CACHE and now - _LOADED_AT < _TTL_SECONDS:
        return _CACHE
    with _LOCK:
        if _CACHE and now - _LOADED_AT < _TTL_SECONDS:
            return _CACHE
        try:
            rows = db.table("vehicle_images").select(
                "image_key,make,model,model_year,image_url,thumbnail_url,source_url,usage_license,provider"
            ).execute().data or []
        except Exception:
            # Migration is optional during rollout; public inventory must still work.
            return _CACHE
        _CACHE = {str(row["image_key"]): row for row in rows}
        _LOADED_AT = now
        return _CACHE


def attach_vehicle_images(db: Client, vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    images = _load(db)
    for vehicle in vehicles:
        exact = _key(vehicle.get("make"), vehicle.get("model"), vehicle.get("year"))
        generic = _key(vehicle.get("make"), vehicle.get("model"))
        image = images.get(exact) or images.get(generic)
        if image:
            vehicle.update({
                "image_url": image["image_url"],
                "image_thumbnail_url": image.get("thumbnail_url"),
                "image_source_url": image.get("source_url"),
                "image_license": image.get("usage_license"),
                "image_provider": image.get("provider"),
                "image_is_representative": True,
            })
    return vehicles
