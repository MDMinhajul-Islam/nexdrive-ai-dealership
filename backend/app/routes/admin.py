"""Read-only endpoints for the internal demo dashboard."""
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from app.database import get_supabase

router=APIRouter(prefix="/api/admin",tags=["Admin Dashboard"])
def client(): return get_supabase()
def run(query):
 try: return {"success":True,"source":"database","records":query.execute().data or []}
 except Exception: raise HTTPException(503,"Dashboard data unavailable") from None

@router.get("/summary")
def summary(db:Client=Depends(client)):
 try:
  counts={}
  for table in ("vehicles","customers","leads","appointments"):
   counts[table]=db.table(table).select("*",count="exact").limit(0).execute().count or 0
  available=db.table("vehicles").select("*",count="exact").eq("vehicle_status","Available").limit(0).execute().count or 0
  hot=db.table("leads").select("*",count="exact").eq("lead_temperature","Hot").limit(0).execute().count or 0
  confirmed=db.table("appointments").select("*",count="exact").eq("status","Confirmed").limit(0).execute().count or 0
  return {"success":True,"source":"database",**counts,"available_vehicles":available,"hot_leads":hot,"confirmed_appointments":confirmed}
 except Exception: raise HTTPException(503,"Dashboard summary unavailable") from None

@router.get("/inventory")
def inventory(q:str|None=None,status:str|None=None,limit:int=Query(50,ge=1,le=200),db:Client=Depends(client)):
 query=db.table("vehicles").select("vehicle_id,make,model,year,trim,condition,sale_price,vehicle_status,dealership_location").order("vehicle_id").limit(limit)
 if status: query=query.eq("vehicle_status",status)
 if q: query=query.or_(f"make.ilike.%{q}%,model.ilike.%{q}%,stock_number.ilike.%{q}%")
 return run(query)

@router.get("/leads")
def leads(status:str|None=None,limit:int=Query(50,ge=1,le=200),db:Client=Depends(client)):
 query=db.table("leads").select("lead_id,customer_id,lead_status,budget,lead_score,lead_temperature,vehicle_interest,assigned_salesperson,next_followup_date").order("created_at",desc=True).limit(limit)
 if status: query=query.eq("lead_status",status)
 return run(query)

@router.get("/appointments")
def appointments(status:str|None=None,limit:int=Query(50,ge=1,le=200),db:Client=Depends(client)):
 query=db.table("appointments").select("appointment_id,customer_id,vehicle_id,salesperson_id,appointment_date,appointment_time,appointment_type,status").order("appointment_date",desc=True).limit(limit)
 if status: query=query.eq("status",status)
 return run(query)
