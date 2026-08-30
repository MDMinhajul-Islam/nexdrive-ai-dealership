"""Authenticated operations endpoints for the internal dealership dashboard."""
from datetime import datetime, timezone
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from app.auth import require_admin
from app.database import get_supabase
from app.schemas.admin import AppointmentAdminUpdateRequest, LeadAdminUpdateRequest, VehicleCreateRequest, VehicleUpdateRequest

router=APIRouter(prefix="/api/admin",tags=["Admin Dashboard"],dependencies=[Depends(require_admin)])
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


@router.get("/features")
def features(db:Client=Depends(client)):
 return run(db.table("features").select("feature_id,name,category").order("category").order("name"))


def _unique_inventory_identity(db:Client) -> tuple[str,str,str]:
 alphabet="ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
 for _ in range(20):
  number=random.randint(1,999999)
  vehicle_id=f"VEH-{number:06d}"; stock=f"NX-{number:06d}"
  vin="".join(random.choice(alphabet) for _ in range(17))
  if not db.table("vehicles").select("vehicle_id").or_(f"vehicle_id.eq.{vehicle_id},stock_number.eq.{stock},vin.eq.{vin}").limit(1).execute().data:
   return vehicle_id,vin,stock
 raise HTTPException(503,"Could not allocate a unique inventory identity")


@router.post("/inventory",status_code=201)
def create_inventory(body:VehicleCreateRequest,db:Client=Depends(client)):
 try:
  feature_ids=list(dict.fromkeys(body.feature_ids))
  if feature_ids:
   valid=db.table("features").select("feature_id").in_("feature_id",feature_ids).execute().data or []
   if {x["feature_id"] for x in valid} != set(feature_ids): raise HTTPException(422,"One or more feature IDs are invalid")
  vehicle_id,vin,stock=_unique_inventory_identity(db)
  payload=body.model_dump(exclude={"feature_ids"})|{"vehicle_id":vehicle_id,"vin":vin,"stock_number":stock,"created_at":datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()}
  record=db.table("vehicles").insert(payload).execute().data[0]
  if feature_ids: db.table("vehicle_features").insert([{"vehicle_id":vehicle_id,"feature_id":item} for item in feature_ids]).execute()
  return {"success":True,"source":"database","vehicle":record,"feature_ids":feature_ids}
 except HTTPException: raise
 except Exception: raise HTTPException(503,"Inventory creation failed") from None


@router.patch("/inventory/{vehicle_id}")
def update_inventory(vehicle_id:str,body:VehicleUpdateRequest,db:Client=Depends(client)):
 try:
  existing=db.table("vehicles").select("*").eq("vehicle_id",vehicle_id).limit(1).execute().data
  if not existing: raise HTTPException(404,"Vehicle not found")
  feature_ids=None
  if body.feature_ids is not None:
   feature_ids=list(dict.fromkeys(body.feature_ids))
   valid=db.table("features").select("feature_id").in_("feature_id",feature_ids).execute().data if feature_ids else []
   if {x["feature_id"] for x in (valid or [])} != set(feature_ids): raise HTTPException(422,"One or more feature IDs are invalid")
  payload=body.model_dump(exclude_none=True,exclude={"feature_ids"})
  merged=existing[0]|payload
  if float(merged["sale_price"])>float(merged["msrp"]): raise HTTPException(422,"sale_price cannot exceed msrp")
  if merged["test_drive_available"] and merged["vehicle_status"] not in ("Available","Demo Vehicle"): raise HTTPException(422,"test drive is unavailable for this inventory status")
  payload["updated_at"]=datetime.now(timezone.utc).isoformat()
  record=db.table("vehicles").update(payload).eq("vehicle_id",vehicle_id).execute().data[0]
  if feature_ids is not None:
   db.table("vehicle_features").delete().eq("vehicle_id",vehicle_id).execute()
   if feature_ids: db.table("vehicle_features").insert([{"vehicle_id":vehicle_id,"feature_id":item} for item in feature_ids]).execute()
  return {"success":True,"source":"database","vehicle":record,"feature_ids":body.feature_ids}
 except HTTPException: raise
 except Exception: raise HTTPException(503,"Inventory update failed") from None


@router.post("/inventory/{vehicle_id}/archive")
def archive_inventory(vehicle_id:str,db:Client=Depends(client)):
 try:
  rows=db.table("vehicles").select("vehicle_id").eq("vehicle_id",vehicle_id).limit(1).execute().data
  if not rows: raise HTTPException(404,"Vehicle not found")
  record=db.table("vehicles").update({"vehicle_status":"In Service","test_drive_available":False,"updated_at":datetime.now(timezone.utc).isoformat()}).eq("vehicle_id",vehicle_id).execute().data[0]
  return {"success":True,"source":"database","vehicle":record,"message":"Vehicle removed from customer discovery without deleting history"}
 except HTTPException: raise
 except Exception: raise HTTPException(503,"Inventory archive failed") from None


@router.get("/analytics")
def analytics(db:Client=Depends(client)):
 try:
  sessions=db.table("conversation_sessions").select("status,outcome,channel").limit(5000).execute().data or []
  leads_data=db.table("leads").select("budget,source,lead_temperature,vehicle_interest").limit(5000).execute().data or []
  appointments_data=db.table("appointments").select("status").limit(5000).execute().data or []
  def tally(rows,key):
   result={}
   for row in rows: result[str(row.get(key) or "Unknown")]=result.get(str(row.get(key) or "Unknown"),0)+1
   return result
  return {"success":True,"source":"database","calls":{"total":len(sessions),"status":tally(sessions,"status"),"outcomes":tally(sessions,"outcome")},"leads":{"average_budget":round(sum(float(x.get("budget") or 0) for x in leads_data)/len(leads_data),2) if leads_data else 0,"temperature":tally(leads_data,"lead_temperature"),"sources":tally(leads_data,"source")},"appointments":tally(appointments_data,"status")}
 except Exception: raise HTTPException(503,"Analytics are unavailable until agent operations migration 10 is applied") from None


@router.patch("/leads/{lead_id}")
def update_lead(lead_id:str,body:LeadAdminUpdateRequest,db:Client=Depends(client)):
 try:
  existing=db.table("leads").select("lead_id,next_followup_date").eq("lead_id",lead_id).limit(1).execute().data
  if not existing: raise HTTPException(404,"Lead not found")
  payload=body.model_dump(exclude_none=True)|{"updated_at":datetime.now(timezone.utc).isoformat()}
  if body.assigned_salesperson:
   salesperson=db.table("salespeople").select("salesperson_id,active").eq("salesperson_id",body.assigned_salesperson).limit(1).execute().data
   if not salesperson or not salesperson[0]["active"]: raise HTTPException(422,"Assigned salesperson is unavailable")
  if body.lead_status in ("Won","Lost"): payload["next_followup_date"]=None
  record=db.table("leads").update(payload).eq("lead_id",lead_id).execute().data[0]
  return {"success":True,"source":"database","lead":record}
 except HTTPException: raise
 except Exception: raise HTTPException(503,"Lead update failed") from None


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id:str,body:AppointmentAdminUpdateRequest,db:Client=Depends(client)):
 try:
  existing=db.table("appointments").select("appointment_id").eq("appointment_id",appointment_id).limit(1).execute().data
  if not existing: raise HTTPException(404,"Appointment not found")
  payload=body.model_dump(exclude_none=True)|{"updated_at":datetime.now(timezone.utc).isoformat()}
  record=db.table("appointments").update(payload).eq("appointment_id",appointment_id).execute().data[0]
  return {"success":True,"source":"database","appointment":record}
 except HTTPException: raise
 except Exception: raise HTTPException(503,"Appointment update failed") from None
