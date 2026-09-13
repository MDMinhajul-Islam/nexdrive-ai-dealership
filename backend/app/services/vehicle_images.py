"""Attach ordered Supabase Storage images without exposing service credentials."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from supabase import Client

from app.utils.config import get_settings

VEHICLE_IMAGE_BUCKET = "vehicle-images"


def _model_key(make: object, model: object, year: object = None) -> tuple[str, str, str]:
    return (str(make or "").strip().casefold(), str(model or "").strip().casefold(),
            str(year) if year is not None else "")


def _attach_model_fallback(db: Client, vehicles: list[dict[str, Any]]) -> None:
    """Read the existing CarsXE cache only for vehicles without Storage photos."""
    missing = [v for v in vehicles if not v.get("primary_image_url") and v.get("make") and v.get("model")]
    if not missing:
        return
    try:
        rows = []
        offset = 0
        while True:
            batch = (db.table("vehicle_model_images")
                     .select("make,model,model_year,image_url,thumbnail_url,source_url,usage_license,provider")
                     .in_("make", list({v["make"] for v in missing}))
                     .in_("model", list({v["model"] for v in missing}))
                     .range(offset, offset + 999).execute().data or [])
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
    except Exception:
        return  # Optional provider metadata must never block inventory.
    by_model = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("image_url"), str):
            continue
        if not row["image_url"].startswith("https://") or row.get("provider") != "CarsXE":
            continue
        by_model[_model_key(row.get("make"), row.get("model"), row.get("model_year"))] = row
    for vehicle in missing:
        image = (by_model.get(_model_key(vehicle["make"], vehicle["model"], vehicle.get("year")))
                 or by_model.get(_model_key(vehicle["make"], vehicle["model"])))
        if image:
            vehicle.update({
                "primary_image_url": image["image_url"],
                "image_url": image["image_url"],
                "image_thumbnail_url": image.get("thumbnail_url"),
                "image_source_url": image.get("source_url"),
                "image_license": image.get("usage_license"),
                "image_provider": image["provider"],
                "image_is_representative": True,
            })


def _public_url(storage_path: str) -> str | None:
    base_url = get_settings().supabase_url.rstrip("/")
    if not base_url:
        return None
    return (
        f"{base_url}/storage/v1/object/public/{VEHICLE_IMAGE_BUCKET}/"
        f"{quote(storage_path, safe='/')}"
    )


def _valid_storage_path(vehicle_id: str, storage_path: object) -> bool:
    if not isinstance(storage_path, str):
        return False
    return (
        re.fullmatch(
            rf"vehicles/{re.escape(vehicle_id)}/"
            r"[A-Za-z0-9][A-Za-z0-9._/-]*\.(webp|jpg|jpeg|png|avif)",
            storage_path,
        )
        is not None
        and ".." not in storage_path.split("/")
    )


def attach_vehicle_images(db: Client, vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach exact vehicle images; missing metadata never blocks inventory."""
    vehicle_ids = [
        str(vehicle["vehicle_id"])
        for vehicle in vehicles
        if vehicle.get("vehicle_id")
    ]
    for vehicle in vehicles:
        vehicle.update({
            "primary_image_url": None,
            "images": [],
            "image_url": None,
            "image_thumbnail_url": None,
            "image_source_url": None,
            "image_license": None,
            "image_provider": None,
            "image_is_representative": False,
        })
    if not vehicle_ids:
        return vehicles

    try:
        rows = (
            db.table("vehicle_images")
            .select("id,vehicle_id,storage_path,sort_order,is_primary")
            .in_("vehicle_id", vehicle_ids)
            .order("is_primary", desc=True)
            .order("sort_order")
            .order("id")
            .execute()
            .data
            or []
        )
    except Exception:
        # Image metadata is optional during rollout; inventory remains authoritative.
        _attach_model_fallback(db, vehicles)
        return vehicles

    images_by_vehicle: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        vehicle_id = str(row.get("vehicle_id", ""))
        storage_path = row.get("storage_path")
        if vehicle_id not in vehicle_ids or not _valid_storage_path(
            vehicle_id, storage_path
        ):
            continue
        url = _public_url(storage_path)
        if not url:
            continue
        try:
            sort_order = int(row["sort_order"])
        except (KeyError, TypeError, ValueError):
            continue
        if sort_order < 0 or not isinstance(row.get("is_primary"), bool):
            continue
        images_by_vehicle.setdefault(vehicle_id, []).append({
            "url": url,
            "is_primary": row["is_primary"],
            "sort_order": sort_order,
        })

    for vehicle in vehicles:
        images = sorted(
            images_by_vehicle.get(str(vehicle.get("vehicle_id")), []),
            key=lambda image: (
                not image["is_primary"],
                image["sort_order"],
                image["url"],
            ),
        )
        primary_url = images[0]["url"] if images else None
        vehicle.update({
            "primary_image_url": primary_url,
            "images": images,
            # Preserve the existing public response fields for older clients.
            "image_url": primary_url,
            "image_thumbnail_url": primary_url,
            "image_source_url": None,
            "image_license": None,
            "image_provider": None,
            "image_is_representative": False,
        })
    _attach_model_fallback(db, vehicles)
    return vehicles
