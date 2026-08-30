"""Fetch licensed representative model photos from CarsXE into Supabase.

Run from the backend container after migration 11. The provider key stays in the
backend environment and is never returned to the browser.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_supabase  # noqa: E402
from app.utils.config import get_settings  # noqa: E402


def combinations_from_csv(scope: str) -> list[dict[str, str]]:
    with (PROJECT_ROOT / "database" / "seed" / "vehicles.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fields = ("year", "make", "model") if scope == "year-model" else ("make", "model")
    unique = {tuple(row[field].strip() for field in fields) for row in rows}
    return [dict(zip(fields, values, strict=True)) for values in sorted(unique)]


def combinations_from_database(scope: str, db) -> list[dict[str, str]]:
    fields = ("year", "make", "model") if scope == "year-model" else ("make", "model")
    rows: list[dict] = []
    offset = 0
    while True:
        batch = db.table("vehicles").select(",".join(fields)).range(offset, offset + 999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    unique = {tuple(str(row[field]).strip() for field in fields) for row in rows}
    return [dict(zip(fields, values, strict=True)) for values in sorted(unique)]


def image_key(item: dict[str, str]) -> str:
    prefix = f"{item['year']}|" if item.get("year") else ""
    return f"{prefix}{item['make'].lower()}|{item['model'].lower()}"


def best_image(images: list[dict]) -> dict | None:
    usable = [item for item in images if str(item.get("link", "")).startswith("https://")]
    if not usable:
        return None
    def score(item: dict) -> tuple[int, int]:
        width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        return (int(width >= height), width * height)
    return max(usable, key=score)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("model", "year-model"), default="model")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between provider calls")
    args = parser.parse_args()
    if args.dry_run:
        items = combinations_from_csv(args.scope)
        print(f"IMAGE SYNC scope={args.scope} combinations={len(items)}")
        return 0

    settings = get_settings()
    if not settings.carsxe_api_key:
        raise SystemExit("CARSXE_API_KEY is not configured")
    db = get_supabase()
    items = combinations_from_database(args.scope, db)
    print(f"IMAGE SYNC scope={args.scope} combinations={len(items)}")
    synced = missing = failed = 0
    with httpx.Client(timeout=25, follow_redirects=True) as client:
        for index, item in enumerate(items, 1):
            params = {
                "key": settings.carsxe_api_key,
                "make": item["make"],
                "model": item["model"],
                "size": "Large",
                "license": "ShareCommercially",
                "transparent": "false",
                "validate": "true",
            }
            if item.get("year"):
                params["year"] = item["year"]
            try:
                response = client.get("https://api.carsxe.com/images", params=params)
                response.raise_for_status()
                selected = best_image(response.json().get("images") or [])
                if not selected:
                    missing += 1
                    print(f"MISS {index}/{len(items)} {item}")
                    continue
                record = {
                    "image_key": image_key(item),
                    "make": item["make"],
                    "model": item["model"],
                    "model_year": int(item["year"]) if item.get("year") else None,
                    "image_url": selected["link"],
                    "thumbnail_url": selected.get("thumbnailLink"),
                    "source_url": selected.get("contextLink"),
                    "usage_license": "ShareCommercially",
                    "provider": "CarsXE",
                    "width": int(selected.get("width") or 0) or None,
                    "height": int(selected.get("height") or 0) or None,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                db.table("vehicle_images").upsert(record, on_conflict="image_key").execute()
                synced += 1
                print(f"OK   {index}/{len(items)} {item['make']} {item['model']}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {index}/{len(items)} {item}: {type(exc).__name__}")
            time.sleep(max(0, args.delay))
    print(f"COMPLETE synced={synced} missing={missing} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
