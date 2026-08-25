"""Regenerate all post-inventory business datasets in dependency order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PIPELINE = [
    "generate_customers.py", "generate_salespeople.py", "generate_leads.py",
    "generate_appointments.py", "generate_trade_ins.py", "generate_financing.py",
    "validate_customers.py", "validate_salespeople.py", "validate_leads.py",
    "validate_appointments.py", "validate_trade_ins.py", "validate_financing.py",
    "validate_business_data.py",
]


def main() -> int:
    for script in PIPELINE:
        print(f"\n==> {script}")
        subprocess.run([sys.executable, str(SCRIPTS_DIR / script)], check=True)
    print("\nBusiness dataset pipeline PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
