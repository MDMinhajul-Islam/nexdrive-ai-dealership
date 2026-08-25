"""Inventory repository contract with Supabase and CSV implementations."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol

from app.schemas.inventory_tools import InventorySearchFilters

VEHICLE_COLUMNS = ",".join((
    "vehicle_id", "vin", "stock_number", "make", "model", "year", "trim",
    "body_type", "condition", "mileage", "exterior_color", "interior_color",
    "fuel_type", "transmission", "drivetrain", "seating_capacity", "msrp",
    "sale_price", "vehicle_status", "test_drive_available", "warranty",
    "certification", "dealership_location",
))


class InventoryRepositoryError(RuntimeError):
    """Raised when inventory data cannot be read authoritatively."""


class InventoryRepository(Protocol):
    def search(self, filters: InventorySearchFilters) -> list[dict[str, Any]]: ...
    def get(self, vehicle_id: str) -> dict[str, Any] | None: ...


def _feature_names(relationships: Any) -> list[str]:
    names: set[str] = set()
    if not isinstance(relationships, list):
        return []
    for relationship in relationships:
        feature = relationship.get("features") if isinstance(relationship, dict) else None
        if isinstance(feature, dict) and isinstance(feature.get("name"), str):
            names.add(feature["name"])
    return sorted(names)


class SupabaseInventoryRepository:
    """Read inventory from normalized Supabase tables."""

    def __init__(self, client: Any | None = None, client_factory: Callable[[], Any] | None = None):
        if client is None and client_factory is None:
            raise ValueError("A Supabase client or client factory is required")
        self._client = client
        self._client_factory = client_factory

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _qualifying_vehicle_ids(self, required_features: list[str]) -> list[str] | None:
        if not required_features:
            return None
        feature_result = (
            self.client.table("features")
            .select("feature_id,name")
            .in_("name", required_features)
            .execute()
        )
        feature_rows = feature_result.data or []
        if {row["name"] for row in feature_rows} != set(required_features):
            return []
        feature_ids = [row["feature_id"] for row in feature_rows]
        relation_result = (
            self.client.table("vehicle_features")
            .select("vehicle_id,feature_id")
            .in_("feature_id", feature_ids)
            .execute()
        )
        matches: dict[str, set[str]] = defaultdict(set)
        for row in relation_result.data or []:
            matches[row["vehicle_id"]].add(row["feature_id"])
        return [vehicle_id for vehicle_id, ids in matches.items() if len(ids) == len(feature_ids)]

    def search(self, filters: InventorySearchFilters) -> list[dict[str, Any]]:
        try:
            vehicle_ids = self._qualifying_vehicle_ids(filters.features)
            if vehicle_ids == []:
                return []
            columns = f"{VEHICLE_COLUMNS},vehicle_features(features(name))"
            query = self.client.table("vehicles").select(columns).eq("vehicle_status", "Available")
            exact_filters = {
                "make": filters.make, "model": filters.model, "body_type": filters.body_type,
                "condition": filters.condition, "drivetrain": filters.drivetrain,
                "fuel_type": filters.fuel_type,
            }
            for field, value in exact_filters.items():
                if value is not None:
                    query = query.eq(field, value)
            range_filters = (
                ("sale_price", "gte", filters.budget_min), ("sale_price", "lte", filters.budget_max),
                ("year", "gte", filters.year_min), ("year", "lte", filters.year_max),
                ("mileage", "lte", filters.mileage_max),
                ("seating_capacity", "gte", filters.seating_capacity_min),
            )
            for field, operation, value in range_filters:
                if value is not None:
                    query = getattr(query, operation)(field, value)
            if vehicle_ids is not None:
                query = query.in_("vehicle_id", vehicle_ids)
            result = query.order("sale_price").limit(filters.limit).execute()
            rows = []
            for raw in result.data or []:
                row = dict(raw)
                row["features"] = _feature_names(row.pop("vehicle_features", []))
                rows.append(row)
            return rows
        except Exception as exc:
            raise InventoryRepositoryError("Inventory search failed") from exc

    def get(self, vehicle_id: str) -> dict[str, Any] | None:
        try:
            columns = f"{VEHICLE_COLUMNS},vehicle_features(features(name))"
            result = self.client.table("vehicles").select(columns).eq("vehicle_id", vehicle_id).limit(1).execute()
            if not result.data:
                return None
            row = dict(result.data[0])
            row["features"] = _feature_names(row.pop("vehicle_features", []))
            return row
        except Exception as exc:
            raise InventoryRepositoryError("Inventory lookup failed") from exc


class CsvInventoryRepository:
    """Local read-only repository used for development and deterministic tests."""

    def __init__(self, seed_dir: Path):
        self.seed_dir = seed_dir
        self._vehicles = self._read("vehicles.csv")
        features = {row["feature_id"]: row["name"] for row in self._read("features.csv")}
        feature_map: dict[str, set[str]] = defaultdict(set)
        for row in self._read("vehicle_features.csv"):
            feature_map[row["vehicle_id"]].add(features[row["feature_id"]])
        self._feature_map = feature_map

    def _read(self, name: str) -> list[dict[str, str]]:
        with (self.seed_dir / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _typed(row: dict[str, str], features: set[str]) -> dict[str, Any]:
        result: dict[str, Any] = dict(row)
        for field in ("year", "mileage", "seating_capacity", "msrp", "sale_price"):
            result[field] = int(result[field])
        result["test_drive_available"] = result["test_drive_available"].lower() == "true"
        result["features"] = sorted(features)
        return result

    def search(self, filters: InventorySearchFilters) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        required = set(filters.features)
        for raw in self._vehicles:
            if raw["vehicle_status"] != "Available":
                continue
            exact = {
                "make": filters.make, "model": filters.model, "body_type": filters.body_type,
                "condition": filters.condition, "drivetrain": filters.drivetrain,
                "fuel_type": filters.fuel_type,
            }
            if any(value is not None and raw[field] != value for field, value in exact.items()):
                continue
            if filters.budget_min is not None and int(raw["sale_price"]) < filters.budget_min: continue
            if filters.budget_max is not None and int(raw["sale_price"]) > filters.budget_max: continue
            if filters.year_min is not None and int(raw["year"]) < filters.year_min: continue
            if filters.year_max is not None and int(raw["year"]) > filters.year_max: continue
            if filters.mileage_max is not None and int(raw["mileage"]) > filters.mileage_max: continue
            if filters.seating_capacity_min is not None and int(raw["seating_capacity"]) < filters.seating_capacity_min: continue
            if not required <= self._feature_map[raw["vehicle_id"]]: continue
            matches.append(self._typed(raw, self._feature_map[raw["vehicle_id"]]))
        matches.sort(key=lambda row: (row["sale_price"], row["mileage"], row["vehicle_id"]))
        return matches[: filters.limit]

    def get(self, vehicle_id: str) -> dict[str, Any] | None:
        for row in self._vehicles:
            if row["vehicle_id"] == vehicle_id:
                return self._typed(row, self._feature_map[vehicle_id])
        return None
