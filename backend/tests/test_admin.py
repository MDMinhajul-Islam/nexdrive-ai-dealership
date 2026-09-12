from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app
from app.routes.admin import client as admin_client
from app.utils.config import Settings
from app import auth as admin_auth

class Query:
 def __init__(self): self.filters=[]
 def select(self,*_a,**_k): return self
 def order(self,*_a,**_k): return self
 def limit(self,*_a,**_k): return self
 def eq(self,key,value): self.filters.append((key,value)); return self
 def or_(self,value): self.filters.append(("or",value)); return self
 def execute(self): return SimpleNamespace(data=[{"vehicle_id":"VEH-000001","vehicle_status":"Available"}],count=10)
class Client:
 def __init__(self): self.query=Query()
 def table(self,_name): return self.query

def test_admin_inventory_is_database_backed_and_filterable():
 fake=Client(); app.dependency_overrides[admin_client]=lambda:fake
 try:
  response=TestClient(app).get("/api/admin/inventory",params={"q":"Toyota","status":"Available"})
  assert response.status_code==200
  assert response.json()["source"]=="database"
  assert ("vehicle_status","Available") in fake.query.filters
  assert any(key=="or" for key,_ in fake.query.filters)
 finally: app.dependency_overrides.clear()

def test_admin_limits_are_validated():
 app.dependency_overrides[admin_client]=Client
 try: assert TestClient(app).get("/api/admin/leads?limit=500").status_code==422
 finally: app.dependency_overrides.clear()

def test_admin_summary_returns_operational_counts():
 app.dependency_overrides[admin_client]=Client
 try:
  response=TestClient(app).get("/api/admin/summary")
  assert response.status_code==200
  assert response.json()["vehicles"]==10
  assert response.json()["available_vehicles"]==10
 finally: app.dependency_overrides.clear()


class MutableQuery:
 def __init__(self, store, table): self.store=store; self.table_name=table; self.filters=[]; self.operation="select"; self.payload={}
 def select(self,*_a,**_k): return self
 def order(self,*_a,**_k): return self
 def limit(self,*_a,**_k): return self
 def eq(self,key,value): self.filters.append((key,value)); return self
 def update(self,payload): self.operation="update"; self.payload=payload; return self
 def delete(self): self.operation="delete"; return self
 def execute(self):
  records=self.store.get(self.table_name,[])
  matches=[row for row in records if all(row.get(key)==value for key,value in self.filters)]
  if self.operation=="update":
   for row in matches: row.update(self.payload)
  elif self.operation=="delete":
   for row in matches: records.remove(row)
  return SimpleNamespace(data=[dict(row) for row in matches],count=len(matches))


class MutableClient:
 def __init__(self):
  self.store={
   "appointments":[{"appointment_id":"APT-000001","lead_id":"LEAD-000001","status":"Requested"}],
   "leads":[{"lead_id":"LEAD-000001"},{"lead_id":"LEAD-000002"}],
   "trade_ins":[],
  }
 def table(self,name): return MutableQuery(self.store,name)


def test_admin_can_approve_requested_booking():
 fake=MutableClient(); app.dependency_overrides[admin_client]=lambda:fake
 try:
  response=TestClient(app).patch("/api/admin/appointments/APT-000001/approve")
  assert response.status_code==200
  assert response.json()["booking"]["status"]=="Confirmed"
  assert fake.store["appointments"][0]["status"]=="Confirmed"
  assert TestClient(app).patch("/api/admin/appointments/APT-000001/approve").status_code==409
  assert TestClient(app).patch("/api/admin/appointments/APT-999999/approve").status_code==404
 finally: app.dependency_overrides.clear()


def test_admin_can_reject_requested_booking_and_delete_booking():
 fake=MutableClient(); app.dependency_overrides[admin_client]=lambda:fake
 try:
  client=TestClient(app)
  rejected=client.patch("/api/admin/appointments/APT-000001/reject")
  assert rejected.status_code==200
  assert rejected.json()["booking"]["status"]=="Cancelled"
  deleted=client.delete("/api/admin/appointments/APT-000001")
  assert deleted.status_code==200
  assert fake.store["appointments"]==[]
  assert client.delete("/api/admin/appointments/APT-000001").status_code==404
 finally: app.dependency_overrides.clear()


def test_admin_lead_delete_blocks_related_booking_and_deletes_unrelated_lead():
 fake=MutableClient(); app.dependency_overrides[admin_client]=lambda:fake
 try:
  client=TestClient(app)
  assert client.delete("/api/admin/leads/LEAD-000001").status_code==409
  deleted=client.delete("/api/admin/leads/LEAD-000002")
  assert deleted.status_code==200
  assert fake.store["leads"]==[{"lead_id":"LEAD-000001"}]
  assert client.delete("/api/admin/leads/LEAD-999999").status_code==404
 finally: app.dependency_overrides.clear()


def test_admin_mutations_require_authentication_when_enabled(monkeypatch):
 monkeypatch.setattr(admin_auth, "get_settings", lambda: Settings(admin_auth_required=True, admin_emails="admin@nexdrive.demo"))
 app.dependency_overrides[admin_client]=MutableClient
 try:
  assert TestClient(app).patch("/api/admin/appointments/APT-000001/approve").status_code==401
  assert TestClient(app).delete("/api/admin/appointments/APT-000001").status_code==401
 finally: app.dependency_overrides.clear()


def test_admin_overview_requires_authentication_when_enabled(monkeypatch):
 monkeypatch.setattr(admin_auth, "get_settings", lambda: Settings(admin_auth_required=True, admin_emails="admin@nexdrive.demo"))
 app.dependency_overrides[admin_client]=MutableClient
 try:
  assert TestClient(app).get("/api/admin/summary").status_code==401
 finally: app.dependency_overrides.clear()
