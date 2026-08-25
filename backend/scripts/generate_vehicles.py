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
LARGE_SUVS = {
    "Highlander", "Pilot", "Explorer", "Santa Fe", "Telluride",
    "Traverse", "CX-90", "Ascent", "Tiguan",
}
TOW_CAPABLE_CROSSOVERS = {"RAV4", "CR-V", "Escape", "Tucson", "Sportage", "Rogue", "CX-50", "Forester"}

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
    # A model-relative, jittered wholesale floor avoids an obvious pile-up at one price.
    price_floor = max(5500, model["base_msrp"] * rng.uniform(0.24, 0.32))
    sale_price = round(max(price_floor, msrp * sale_factor) / 50) * 50
    return int(msrp), int(min(msrp, sale_price))


def feature_ids_for_vehicle(
    rng: random.Random,
    model: dict,
    trim_index: int,
    year: int,
    drivetrain: str,
) -> list[str]:
    selected: set[str] = set()
    model_name = model["model"]
    body_type = model["body_type"]

    def maybe(feature_id: str, probability: float) -> None:
        if year >= FEATURE_MIN_YEAR.get(feature_id, 2016) and rng.random() < max(0.0, min(1.0, probability)):
            selected.add(feature_id)

    # Facts and configuration-linked features are deterministic.
    if drivetrain == "AWD":
        selected.add("FEAT-020")
    if model["seating"] >= 7:
        selected.add("FEAT-019")

    # Connectivity adoption grows by year; CarPlay and Android Auto are not coupled.
    connectivity_base = 0.15 if year <= 2017 else 0.48 if year <= 2019 else 0.72 if year <= 2021 else 0.89
    maybe("FEAT-013", connectivity_base + trim_index * 0.015)
    maybe("FEAT-014", connectivity_base - 0.05 + trim_index * 0.015)
    keyless_probability = 0.58 if year <= 2019 else 0.80 if year <= 2022 else 0.92
    maybe("FEAT-023", keyless_probability + trim_index * 0.01)

    # Utility features require a compatible body/model before trim probability applies.
    roof_rail_probability = {
        "SUV": (0.42, 0.62, 0.80),
        "Hatchback": (0.08, 0.16, 0.25),
        "Sedan": (0.01, 0.03, 0.06),
        "Truck": (0.01, 0.04, 0.08),
    }[body_type][trim_index]
    maybe("FEAT-024", roof_rail_probability)
    if body_type == "Truck":
        maybe("FEAT-025", (0.42, 0.58, 0.72)[trim_index])
        maybe("FEAT-021", (0.42, 0.58, 0.70)[trim_index])
    elif model_name in LARGE_SUVS:
        maybe("FEAT-021", (0.12, 0.25, 0.38)[trim_index])
    elif model_name in TOW_CAPABLE_CROSSOVERS:
        maybe("FEAT-021", (0.03, 0.09, 0.16)[trim_index])
    if body_type == "SUV":
        maybe("FEAT-011", (0.18, 0.58, 0.90)[trim_index])
    elif body_type == "Hatchback":
        maybe("FEAT-011", (0.02, 0.07, 0.15)[trim_index])

    # Year and trim jointly drive safety equipment instead of global random rates.
    safety_year_factor = 0.35 if year <= 2017 else 0.60 if year <= 2020 else 0.82 if year <= 2022 else 1.00
    safety_probabilities = {
        "FEAT-001": (0.15, 0.55, 0.90), "FEAT-002": (0.25, 0.65, 0.95),
        "FEAT-003": (0.20, 0.60, 0.92), "FEAT-004": (0.01, 0.12, 0.55),
        "FEAT-005": (0.25, 0.65, 0.90), "FEAT-006": (0.35, 0.75, 0.98),
    }
    for feature_id, by_trim in safety_probabilities.items():
        maybe(feature_id, by_trim[trim_index] * safety_year_factor)

    # Shared trim context creates realistic correlations without identical packages.
    comfort_probabilities = {
        "FEAT-007": (0.02, 0.30, 0.82), "FEAT-008": (0.08, 0.52, 0.90),
        "FEAT-009": (0.01, 0.09, 0.58), "FEAT-010": (0.02, 0.22, 0.64),
        "FEAT-012": (0.18, 0.62, 0.91), "FEAT-015": (0.06, 0.38, 0.78),
        "FEAT-016": (0.04, 0.25, 0.72), "FEAT-017": (0.02, 0.16, 0.65),
        "FEAT-018": (0.08, 0.34, 0.68), "FEAT-022": (0.18, 0.56, 0.86),
    }
    age_penalty = min(0.22, max(0, DATASET_YEAR - year) * 0.025)
    for feature_id, by_trim in comfort_probabilities.items():
        maybe(feature_id, by_trim[trim_index] - age_penalty)

    # Avoid featureless rows while keeping the floor low enough not to distort frequencies.
    plausible_baseline = ["FEAT-005", "FEAT-008", "FEAT-012", "FEAT-022", "FEAT-023"]
    while len(selected) < 2:
        selected.add(rng.choice(plausible_baseline))
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
