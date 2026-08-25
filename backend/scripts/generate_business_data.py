"""Entry point for future synthetic dealership business-data generation.

Vehicle and customer generation remain separate because they are foundational
datasets. Leads, appointments, salespeople, and trade-ins will be orchestrated
from here as their generators are implemented.
"""

from __future__ import annotations


def main() -> int:
    print("Business-data generators are scaffolded; no business rows generated yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
