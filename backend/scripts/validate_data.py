"""Validate NexDrive vehicle inventory and normalized feature relationships."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_DIR = ROOT / "database" / "seed"
DEFAULT_REPORT = ROOT / "backend" / "docs" / "validation_report.json"
VIN_RE = re.compile(r"^NXD[A-HJ-NPR-Z0-9]{14}$")
ID_RE = re.compile(r"^VEH-\d{6}$")
STOCK_RE = re.compile(r"^NX-\d{6}$")
VALID_STATUSES = {
    "Available", "Reserved", "Sold", "Pending Sale", "In Service",
    "Arriving Soon", "Demo Vehicle", "No Test Drive",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def catalog_index() -> dict[tuple[str, str], dict]:
    with (ROOT / "database" / "reference" / "vehicle_catalog.json").open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    return {
        (make["make"], model["model"]): model
        for make in catalog["makes"]
        for model in make["models"]
    }


def validate(seed_dir: Path, expected_count: int) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    vehicles = read_csv(seed_dir / "vehicles.csv")
    features = read_csv(seed_dir / "features.csv")
    relationships = read_csv(seed_dir / "vehicle_features.csv")
    catalog = catalog_index()

    if len(vehicles) != expected_count:
        errors.append(f"Expected {expected_count:,} vehicles, found {len(vehicles):,}")

    for field in ("vehicle_id", "vin", "stock_number"):
        values = [row[field] for row in vehicles]
        if len(values) != len(set(values)):
            errors.append(f"Duplicate {field} values found")

    relationship_pairs = [(row["vehicle_id"], row["feature_id"]) for row in relationships]
    if len(relationship_pairs) != len(set(relationship_pairs)):
        errors.append("Duplicate vehicle-feature pairs found")

    vehicle_ids = {row["vehicle_id"] for row in vehicles}
    feature_ids = {row["feature_id"] for row in features}
    relation_count: Counter[str] = Counter()

    for row_number, row in enumerate(relationships, start=2):
        if row["vehicle_id"] not in vehicle_ids:
            errors.append(f"vehicle_features row {row_number}: unknown vehicle_id")
        if row["feature_id"] not in feature_ids:
            errors.append(f"vehicle_features row {row_number}: unknown feature_id")
        relation_count[row["vehicle_id"]] += 1

    status_counts: Counter[str] = Counter()
    condition_counts: Counter[str] = Counter()
    make_counts: Counter[str] = Counter()
    relationship_map: defaultdict[str, set[str]] = defaultdict(set)
    for vehicle_id, feature_id in relationship_pairs:
        relationship_map[vehicle_id].add(feature_id)

    for row_number, row in enumerate(vehicles, start=2):
        prefix = f"vehicles row {row_number} ({row.get('vehicle_id', 'unknown')})"
        try:
            year = int(row["year"])
            mileage = int(row["mileage"])
            msrp = int(row["msrp"])
            sale_price = int(row["sale_price"])
            seating = int(row["seating_capacity"])
        except (KeyError, ValueError):
            errors.append(f"{prefix}: invalid numeric value")
            continue

        if not ID_RE.fullmatch(row["vehicle_id"]):
            errors.append(f"{prefix}: malformed vehicle_id")
        if not VIN_RE.fullmatch(row["vin"]):
            errors.append(f"{prefix}: malformed synthetic VIN-like value")
        if not STOCK_RE.fullmatch(row["stock_number"]):
            errors.append(f"{prefix}: malformed stock_number")

        model = catalog.get((row["make"], row["model"]))
        if not model:
            errors.append(f"{prefix}: make/model is not in reference catalog")
        else:
            if row["trim"] not in model["trims"]:
                errors.append(f"{prefix}: trim does not match model")
            if row["body_type"] != model["body_type"]:
                errors.append(f"{prefix}: body_type does not match model")
            if row["fuel_type"] not in model["fuels"]:
                errors.append(f"{prefix}: fuel_type does not match model")
            if row["drivetrain"] not in model["drivetrains"]:
                errors.append(f"{prefix}: drivetrain does not match model")
            if seating != model["seating"]:
                errors.append(f"{prefix}: seating does not match model")

        if not 2016 <= year <= 2027:
            errors.append(f"{prefix}: year outside supported range")
        if mileage < 0 or mileage > 165_000:
            errors.append(f"{prefix}: mileage outside supported range")
        if row["condition"] == "New" and mileage > 300:
            errors.append(f"{prefix}: new vehicle has excessive mileage")
        if row["condition"] == "Certified Pre-Owned" and not (2020 <= year <= 2025 and mileage <= 75_000):
            errors.append(f"{prefix}: vehicle violates CPO age/mileage rules")
        if not 8_000 <= sale_price <= msrp <= 100_000:
            errors.append(f"{prefix}: impossible price relationship")
        if row["vehicle_status"] not in VALID_STATUSES:
            errors.append(f"{prefix}: unknown inventory status")

        expected_test_drive = row["vehicle_status"] in {"Available", "Demo Vehicle"}
        if (row["test_drive_available"].lower() == "true") != expected_test_drive:
            errors.append(f"{prefix}: test-drive flag conflicts with inventory status")
        if row["condition"] == "Certified Pre-Owned" and row["certification"] == "None":
            errors.append(f"{prefix}: CPO vehicle is missing certification")
        if relation_count[row["vehicle_id"]] < 4:
            errors.append(f"{prefix}: fewer than four queryable features")
        if seating >= 7 and "FEAT-019" not in relationship_map[row["vehicle_id"]]:
            errors.append(f"{prefix}: third-row vehicle missing feature relationship")
        if row["drivetrain"] in {"AWD", "4WD"} and "FEAT-020" not in relationship_map[row["vehicle_id"]]:
            errors.append(f"{prefix}: AWD/4WD vehicle missing feature relationship")

        status_counts[row["vehicle_status"]] += 1
        condition_counts[row["condition"]] += 1
        make_counts[row["make"]] += 1

    if vehicles:
        available_pct = status_counts["Available"] / len(vehicles) * 100
        secondary_pct = sum(status_counts[x] for x in ("Reserved", "Pending Sale", "Sold")) / len(vehicles) * 100
        edge_pct = 100 - available_pct - secondary_pct
        if not 60 <= available_pct <= 70:
            errors.append(f"Available status mix is {available_pct:.2f}%, expected 60-70%")
        if not 20 <= secondary_pct <= 30:
            errors.append(f"Reserved/Pending/Sold mix is {secondary_pct:.2f}%, expected 20-30%")
        if not 5 <= edge_pct <= 10:
            errors.append(f"Arriving/Service/Demo/No-Test-Drive mix is {edge_pct:.2f}%, expected 5-10%")
    if len(make_counts) < 10:
        warnings.append(f"Only {len(make_counts)} makes represented")

    return {
        "result": "PASS" if not errors else "FAIL",
        "dataset_as_of": "2026-08-25",
        "summary": {
            "vehicles": len(vehicles),
            "features": len(features),
            "vehicle_feature_relationships": len(relationships),
            "unique_makes": len(make_counts),
            "unique_models": len({(v["make"], v["model"]) for v in vehicles}),
        },
        "status_distribution": dict(sorted(status_counts.items())),
        "condition_distribution": dict(sorted(condition_counts.items())),
        "make_distribution": dict(sorted(make_counts.items())),
        "errors": errors[:100],
        "error_count": len(errors),
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_SEED_DIR)
    parser.add_argument("--expected-count", type=int, default=10_000)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = validate(args.seed_dir.resolve(), args.expected_count)
    except (FileNotFoundError, KeyError, csv.Error, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['result']}: {report['summary']['vehicles']:,} vehicles, "
          f"{report['summary']['vehicle_feature_relationships']:,} relationships, "
          f"{report['error_count']} errors")
    print(f"Report: {args.report.resolve()}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
