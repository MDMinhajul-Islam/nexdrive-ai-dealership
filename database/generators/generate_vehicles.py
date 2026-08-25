"""Generate deterministic, realistic NexDrive Motors vehicle inventory CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT / "database" / "reference"
DEFAULT_OUTPUT_DIR = ROOT / "database" / "seed"
DATASET_YEAR = 2026

TRIM_MULTIPLIERS = (1.00, 1.10, 1.22)
FUEL_ADJUSTMENTS = {
    "Gasoline": 0,
    "Diesel": 4500,
    "Hybrid": 3200,
    "Plug-in Hybrid": 7200,
    "Electric": 5500,
}
DRIVETRAIN_ADJUSTMENTS = {"FWD": 0, "RWD": 700, "AWD": 1900, "4WD": 2500}
STATUS_WEIGHTS = {
    "Available": 67,
    "Reserved": 9,
    "Sold": 8,
    "Pending Sale": 7,
    "In Service": 2,
    "Arriving Soon": 3,
    "Demo Vehicle": 2,
    "No Test Drive": 2,
}
CONDITION_WEIGHTS = {"New": 36, "Used": 48, "Certified Pre-Owned": 16}
FEATURE_MIN_YEAR = {
    "FEAT-001": 2018, "FEAT-002": 2017, "FEAT-003": 2018,
    "FEAT-004": 2018, "FEAT-006": 2017, "FEAT-013": 2017,
    "FEAT-014": 2017, "FEAT-015": 2019, "FEAT-018": 2018,
}

VEHICLE_FIELDS = [
    "vehicle_id", "vin", "stock_number", "make", "model", "year", "trim",
    "body_type", "condition", "mileage", "exterior_color", "interior_color",
    "fuel_type", "transmission", "drivetrain", "seating_capacity", "msrp",
    "sale_price", "vehicle_status", "test_drive_available", "warranty",
    "certification", "dealership_location",
]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def weighted_choice(rng: random.Random, weights: dict[str, int]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def synthetic_vin(index: int, seed: int) -> str:
    """Return a unique 17-character VIN-like identifier, never a claimed real VIN."""
    alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    digest = hashlib.sha256(f"NEXDRIVE:{seed}:{index}".encode()).digest()
    chars = ["N", "X", "D"]
    for position in range(14):
        chars.append(alphabet[digest[position] % len(alphabet)])
    return "".join(chars)


def choose_condition_year_mileage(rng: random.Random, first_model_year: int) -> tuple[str, int, int]:
    condition = weighted_choice(rng, CONDITION_WEIGHTS)
    if condition == "New":
        years = [year for year in [2025, 2026, 2027] if year >= first_model_year]
        weights = [[20, 79, 1][[2025, 2026, 2027].index(year)] for year in years]
        year = rng.choices(years, weights=weights, k=1)[0]
        mileage = rng.randint(3, 25 if year > DATASET_YEAR else 220)
    elif condition == "Certified Pre-Owned":
        all_years = [2020, 2021, 2022, 2023, 2024, 2025]
        all_weights = [5, 10, 17, 24, 27, 17]
        years = [year for year in all_years if year >= first_model_year]
        weights = [all_weights[all_years.index(year)] for year in years]
        year = rng.choices(years, weights=weights, k=1)[0]
        age = max(1, DATASET_YEAR - year)
        mileage = int(max(2500, min(75000, rng.gauss(age * 9500, 3500))))
    else:
        all_years = list(range(2016, 2026))
        all_weights = [2, 3, 5, 7, 9, 12, 14, 17, 17, 14]
        years = [year for year in all_years if year >= first_model_year]
        weights = [all_weights[all_years.index(year)] for year in years]
        year = rng.choices(years, weights=weights, k=1)[0]
        age = max(1, DATASET_YEAR - year)
        mileage = int(max(1500, min(165000, rng.gauss(age * 11800, 6500))))
    return condition, year, mileage


def choose_colors(rng: random.Random, colors: dict, trim_index: int) -> tuple[str, str]:
    exterior_groups = ["neutral", "neutral", "warm", "cool"]
    if trim_index == 2:
        exterior_groups.append("premium")
    exterior = rng.choice(colors["exterior"][rng.choice(exterior_groups)])
    interior_group = rng.choices(
        ["cloth", "leatherette", "leather"],
        weights=([70, 25, 5], [25, 55, 20], [5, 25, 70])[trim_index],
        k=1,
    )[0]
    return exterior, rng.choice(colors["interior"][interior_group])


def calculate_prices(
    rng: random.Random,
    model: dict,
    trim_index: int,
    fuel: str,
    drivetrain: str,
    condition: str,
    year: int,
    mileage: int,
) -> tuple[int, int]:
    configured = model["base_msrp"] * TRIM_MULTIPLIERS[trim_index]
    configured += FUEL_ADJUSTMENTS[fuel] + DRIVETRAIN_ADJUSTMENTS[drivetrain]
    model_year_factor = 1 - max(0, DATASET_YEAR - year) * 0.018
    msrp = round(configured * model_year_factor / 50) * 50

    if condition == "New":
        sale_factor = rng.uniform(0.965, 0.999)
    else:
        age = max(1, DATASET_YEAR - year)
        depreciation = 0.84 * (0.91 ** (age - 1))
        mileage_factor = max(0.68, 1 - max(0, mileage - age * 9000) / 300000)
        cpo_bonus = 1.055 if condition == "Certified Pre-Owned" else 1.0
        sale_factor = depreciation * mileage_factor * cpo_bonus * rng.uniform(0.97, 1.03)
    sale_price = round(max(8500, msrp * sale_factor) / 50) * 50
    return int(msrp), int(min(msrp, sale_price))


def feature_ids_for_vehicle(
    rng: random.Random,
    model: dict,
    trim_index: int,
    year: int,
    drivetrain: str,
) -> list[str]:
    selected = {"FEAT-023"}
    if year >= 2019:
        selected.update({"FEAT-013", "FEAT-014"})
    if year >= 2021:
        selected.add("FEAT-006")
    if drivetrain in {"AWD", "4WD"}:
        selected.add("FEAT-020")
    if model["seating"] >= 7:
        selected.add("FEAT-019")
    if model["body_type"] == "Truck":
        selected.add("FEAT-025")
        if trim_index > 0 or rng.random() < 0.45:
            selected.add("FEAT-021")
    if model["body_type"] in {"SUV", "Hatchback"}:
        selected.add("FEAT-024")
        if rng.random() < 0.72:
            selected.add("FEAT-011")

    probabilities = {
        "FEAT-001": (0.20, 0.58, 0.92), "FEAT-002": (0.42, 0.78, 0.97),
        "FEAT-003": (0.35, 0.73, 0.95), "FEAT-004": (0.02, 0.18, 0.72),
        "FEAT-005": (0.22, 0.68, 0.96), "FEAT-007": (0.02, 0.32, 0.91),
        "FEAT-008": (0.08, 0.62, 0.95), "FEAT-009": (0.01, 0.10, 0.66),
        "FEAT-010": (0.02, 0.24, 0.70), "FEAT-012": (0.20, 0.70, 0.96),
        "FEAT-015": (0.08, 0.48, 0.86), "FEAT-016": (0.05, 0.30, 0.82),
        "FEAT-017": (0.02, 0.18, 0.75), "FEAT-018": (0.10, 0.44, 0.80),
        "FEAT-022": (0.22, 0.66, 0.92),
    }
    age_penalty = min(0.30, max(0, DATASET_YEAR - year) * 0.035)
    for feature_id, by_trim in probabilities.items():
        if year >= FEATURE_MIN_YEAR.get(feature_id, 2016) and rng.random() < max(0, by_trim[trim_index] - age_penalty):
            selected.add(feature_id)
    baseline_pool = [
        "FEAT-001", "FEAT-002", "FEAT-003", "FEAT-005", "FEAT-006", "FEAT-008",
        "FEAT-012", "FEAT-013", "FEAT-014", "FEAT-018", "FEAT-022", "FEAT-023",
    ]
    baseline_pool = [feature_id for feature_id in baseline_pool if year >= FEATURE_MIN_YEAR.get(feature_id, 2016)]
    while len(selected) < 4:
        selected.add(rng.choice(baseline_pool))
    return sorted(selected)


def generate(count: int, seed: int, output_dir: Path) -> None:
    rng = random.Random(seed)
    catalog = load_json(REFERENCE_DIR / "vehicle_catalog.json")
    features = load_json(REFERENCE_DIR / "features.json")["features"]
    colors = load_json(REFERENCE_DIR / "colors.json")
    makes = catalog["makes"]
    make_weights = [make["weight"] for make in makes]

    vehicles: list[dict] = []
    relationships: list[dict] = []
    for index in range(1, count + 1):
        make = rng.choices(makes, weights=make_weights, k=1)[0]
        model = rng.choice(make["models"])
        trim_index = rng.choices([0, 1, 2], weights=[42, 38, 20], k=1)[0]
        trim = model["trims"][trim_index]
        condition, year, mileage = choose_condition_year_mileage(
            rng, model.get("first_model_year", 2016)
        )
        fuel = rng.choice(model["fuels"])
        drivetrain = rng.choice(model["drivetrains"])
        exterior, interior = choose_colors(rng, colors, trim_index)
        msrp, sale_price = calculate_prices(
            rng, model, trim_index, fuel, drivetrain, condition, year, mileage
        )
        status = "Arriving Soon" if year > DATASET_YEAR else weighted_choice(rng, STATUS_WEIGHTS)
        test_drive = status in {"Available", "Demo Vehicle"}
        warranty = (
            "Manufacturer Warranty"
            if condition == "New"
            else "7-Year/100,000-Mile Limited Powertrain Warranty"
            if condition == "Certified Pre-Owned"
            else rng.choice(["90-Day Dealer Limited Warranty", "As-Is", "12-Month Service Contract"])
        )
        certification = "Manufacturer CPO Inspection" if condition == "Certified Pre-Owned" else "None"
        vehicle_id = f"VEH-{index:06d}"
        vehicles.append({
            "vehicle_id": vehicle_id,
            "vin": synthetic_vin(index, seed),
            "stock_number": f"NX-{index:06d}",
            "make": make["make"],
            "model": model["model"],
            "year": year,
            "trim": trim,
            "body_type": model["body_type"],
            "condition": condition,
            "mileage": mileage,
            "exterior_color": exterior,
            "interior_color": interior,
            "fuel_type": fuel,
            "transmission": "Single-Speed Automatic" if fuel == "Electric" else "Automatic",
            "drivetrain": drivetrain,
            "seating_capacity": model["seating"],
            "msrp": msrp,
            "sale_price": sale_price,
            "vehicle_status": status,
            "test_drive_available": str(test_drive).lower(),
            "warranty": warranty,
            "certification": certification,
            "dealership_location": rng.choices(
                ["Plano Flagship", "Frisco North", "Dallas Central"], weights=[62, 21, 17], k=1
            )[0],
        })
        relationships.extend(
            {"vehicle_id": vehicle_id, "feature_id": feature_id}
            for feature_id in feature_ids_for_vehicle(rng, model, trim_index, year, drivetrain)
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "vehicles.csv", VEHICLE_FIELDS, vehicles)
    write_csv(output_dir / "features.csv", ["feature_id", "name", "category"], features)
    write_csv(output_dir / "vehicle_features.csv", ["vehicle_id", "feature_id"], relationships)
    print(f"Generated {len(vehicles):,} vehicles and {len(relationships):,} feature relationships in {output_dir}")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    generate(arguments.count, arguments.seed, arguments.output_dir.resolve())
