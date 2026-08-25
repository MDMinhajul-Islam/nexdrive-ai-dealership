"""Generate the fixed synthetic NexDrive sales-team roster."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "database" / "seed" / "salespeople.csv"
FIELDS = [
    "salesperson_id", "name", "synthetic_email", "synthetic_phone", "languages",
    "specialization", "working_days", "shift_start", "shift_end", "active",
]

ROSTER = [
    ("Jordan Ellis", ["English"], "SUV Specialist", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "08:30", "17:00", True),
    ("Maya Brooks", ["English", "Spanish"], "Truck Specialist", ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "09:00", "18:00", True),
    ("Ethan Patel", ["English", "Hindi"], "EV/Hybrid Specialist", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "09:30", "18:30", True),
    ("Sofia Ramirez", ["English", "Spanish"], "Used/CPO Specialist", ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "10:00", "19:00", True),
    ("Caleb Morgan", ["English"], "Financing-Focused", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "09:00", "18:00", True),
    ("Aisha Khan", ["English", "Urdu"], "SUV Specialist", ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "10:00", "19:00", True),
    ("Diego Torres", ["English", "Spanish"], "General Sales", ["Saturday", "Sunday"], "09:00", "18:00", True),
    ("Chloe Bennett", ["English"], "EV/Hybrid Specialist", ["Thursday", "Friday", "Saturday", "Sunday", "Monday"], "10:00", "19:00", True),
    ("Noah Reed", ["English"], "Truck Specialist", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "08:30", "17:00", False),
    ("Priya Shah", ["English", "Hindi"], "Used/CPO Specialist", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "09:00", "18:00", True),
]


def pg_array(values: list[str]) -> str:
    return "{" + ",".join(values) + "}"


def generate(output: Path) -> None:
    rows = []
    for index, (name, languages, specialization, days, start, end, active) in enumerate(ROSTER, start=1):
        rows.append({
            "salesperson_id": f"SP-{index:03d}",
            "name": name,
            "synthetic_email": f"salesperson{index:03d}@nexdrive.example",
            "synthetic_phone": f"+1-555-020-{index:04d}",
            "languages": pg_array(languages),
            "specialization": specialization,
            "working_days": pg_array(days),
            "shift_start": start,
            "shift_end": end,
            "active": str(active).lower(),
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} synthetic salespeople in {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
