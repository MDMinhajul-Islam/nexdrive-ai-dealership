"""Repeatably upsert validated NexDrive seed CSVs into Supabase."""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"backend"))
from app.database import get_supabase

ORDER=[("vehicles","vehicles.csv","vehicle_id"),("features","features.csv","feature_id"),("vehicle_features","vehicle_features.csv","vehicle_id,feature_id"),("customers","customers.csv","customer_id"),("salespeople","salespeople.csv","salesperson_id"),("leads","leads.csv","lead_id"),("appointments","appointments.csv","appointment_id"),("trade_ins","trade_ins.csv","trade_in_id"),("financing_options","financing_options.csv","financing_rule_id")]
ARRAY_FIELDS={"languages","working_days"}; BOOL_FIELDS={"active","test_drive_available","financing_needed","trade_in"}; NULLABLE={"vehicle_interest","next_followup_date"}
def convert(row):
 out={}
 for key,value in row.items():
  if key in ARRAY_FIELDS: out[key]=value.strip("{}").split(",") if value.strip("{}") else []
  elif key in BOOL_FIELDS: out[key]=value.lower()=="true"
  elif key in NULLABLE and value=="": out[key]=None
  else: out[key]=value
 return out
def main():
 parser=argparse.ArgumentParser(); parser.add_argument("--batch-size",type=int,default=500); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
 client=None if args.dry_run else get_supabase()
 for table,file,conflict in ORDER:
  with (ROOT/"database"/"seed"/file).open(encoding="utf-8",newline="") as handle: rows=[convert(r) for r in csv.DictReader(handle)]
  if not args.dry_run:
   for start in range(0,len(rows),args.batch_size): client.table(table).upsert(rows[start:start+args.batch_size],on_conflict=conflict).execute()
  print(f"{'CHECK' if args.dry_run else 'UPSERT'} {table}: {len(rows):,}")
 return 0
if __name__=="__main__": raise SystemExit(main())
