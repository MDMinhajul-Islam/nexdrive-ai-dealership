"""Customer-safe dealership discovery endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.database import get_supabase

router = APIRouter(prefix="/api/public", tags=["Public Dealership"])


@router.get("/inventory")
def inventory(
    q: str | None = None,
    make: str | None = None,
    body_type: str | None = None,
    condition: str | None = None,
    fuel_type: str | None = None,
    drivetrain: str | None = None,
    budget_max: int | None = Query(default=None, ge=3000, le=500000),
    limit: int = Query(12, ge=1, le=60),
    db: Client = Depends(get_supabase),
):
    try:
        query = db.table("vehicles").select("vehicle_id,make,model,year,trim,body_type,condition,mileage,exterior_color,fuel_type,drivetrain,seating_capacity,msrp,sale_price,vehicle_status,test_drive_available,dealership_location").in_("vehicle_status", ["Available", "Demo Vehicle"]).order("sale_price").limit(limit)
        for field, value in (("make", make), ("body_type", body_type), ("condition", condition), ("fuel_type", fuel_type), ("drivetrain", drivetrain)):
            if value: query = query.eq(field, value)
        if budget_max: query = query.lte("sale_price", budget_max)
        if q: query = query.or_(f"make.ilike.%{q}%,model.ilike.%{q}%,trim.ilike.%{q}%")
        return {"success": True, "source": "database", "records": query.execute().data or []}
    except Exception:
        raise HTTPException(503, "Inventory is temporarily unavailable") from None


@router.get("/inventory/{vehicle_id}")
def vehicle_detail(vehicle_id: str, db: Client = Depends(get_supabase)):
    try:
        rows = db.table("vehicles").select("*").eq("vehicle_id", vehicle_id).limit(1).execute().data
        if not rows: raise HTTPException(404, "Vehicle not found")
        features = db.table("vehicle_features").select("features(name,category)").eq("vehicle_id", vehicle_id).execute().data or []
        return {"success": True, "source": "database", "vehicle": rows[0], "features": [item.get("features") for item in features if item.get("features")]}
    except HTTPException: raise
    except Exception: raise HTTPException(503, "Vehicle details are temporarily unavailable") from None
