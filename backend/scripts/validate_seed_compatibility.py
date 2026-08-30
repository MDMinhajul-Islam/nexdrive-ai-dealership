"""Validate CSV headers against schema/import contracts before Supabase import."""
from __future__ import annotations
import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "database" / "seed"
CONTRACTS = {
 "vehicles.csv": ["vehicle_id","vin","stock_number","make","model","year","trim","body_type","condition","mileage","exterior_color","interior_color","fuel_type","transmission","drivetrain","seating_capacity","msrp","sale_price","vehicle_status","test_drive_available","warranty","certification","dealership_location"],
 "features.csv": ["feature_id","name","category"],
 "vehicle_features.csv": ["vehicle_id","feature_id"],
 "customers.csv": ["customer_id","first_name","last_name","synthetic_phone","synthetic_email","city","state","preferred_vehicle_type","preferred_brand","budget_min","budget_max","financing_needed","estimated_down_payment","family_size","trade_in","purchase_timeline","lead_source","buyer_profile","notes","created_at"],
 "salespeople.csv": ["salesperson_id","name","synthetic_email","synthetic_phone","languages","specialization","working_days","shift_start","shift_end","active"],
 "leads.csv": ["lead_id","customer_id","source","created_at","lead_status","budget","vehicle_interest","purchase_timeline","financing_needed","trade_in","lead_score","lead_temperature","assigned_salesperson","next_followup_date","notes"],
 "appointments.csv": ["appointment_id","lead_id","customer_id","vehicle_id","salesperson_id","appointment_date","appointment_time","appointment_type","status","created_by","notes","created_at"],
 "trade_ins.csv": ["trade_in_id","lead_id","customer_id","make","model","year","mileage","condition","estimated_value","loan_balance","notes"],
 "financing_options.csv": ["financing_rule_id","vehicle_condition","term_months","apr_min","apr_max","minimum_down_payment_percent","maximum_vehicle_age_years","active","disclaimer"],
}
def main() -> int:
 errors=[]
 for name, expected in CONTRACTS.items():
  with (SEED/name).open(encoding="utf-8",newline="") as handle:
   reader=csv.reader(handle); actual=next(reader); count=sum(1 for _ in reader)
  if actual != expected: errors.append(f"{name}: header mismatch")
  print(f"PASS {name}: {count:,} rows" if actual == expected else f"FAIL {name}: header mismatch")
 return 1 if errors else 0
if __name__ == "__main__": raise SystemExit(main())
