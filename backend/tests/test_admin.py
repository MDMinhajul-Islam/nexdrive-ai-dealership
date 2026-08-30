from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app
from app.routes.admin import client as admin_client

class Query:
 def __init__(self): self.filters=[]
 def select(self,*_a,**_k): return self
 def order(self,*_a,**_k): return self
 def limit(self,*_a,**_k): return self
 def eq(self,key,value): self.filters.append((key,value)); return self
 def or_(self,value): self.filters.append(("or",value)); return self
 def execute(self): return SimpleNamespace(data=[{"vehicle_id":"VEH-000001","vehicle_status":"Available"}])
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
