import json
from pathlib import Path
from app.main import app

TOOLS={
 "search_inventory":("/api/tools/search-inventory","post"),
 "get_vehicle_details":("/api/tools/get-vehicle-details/{vehicle_id}","get"),
 "check_vehicle_availability":("/api/tools/check-vehicle-availability/{vehicle_id}","get"),
 "get_customer_history":("/api/tools/get-customer-history/{customer_id}","get"),
 "get_test_drive_slots":("/api/tools/get-test-drive-slots","get"),
 "create_or_update_lead":("/api/tools/create-or-update-lead","post"),
 "create_test_drive":("/api/tools/create-test-drive","post"),
 "estimate_financing":("/api/tools/estimate-financing","post"),
}
SCENARIOS=json.loads((Path(__file__).parent/"e2e_scenarios.json").read_text(encoding="utf-8"))

def test_at_least_fifteen_unique_scenarios():
 assert len(SCENARIOS)>=15
 assert len({x["id"] for x in SCENARIOS})==len(SCENARIOS)

def test_every_scenario_targets_a_live_openapi_contract():
 paths=app.openapi()["paths"]
 for scenario in SCENARIOS:
  path,method=TOOLS[scenario["tool"]]
  assert method in paths[path], scenario["id"]

def test_required_failure_and_retry_coverage():
 expected={x["expected"] for x in SCENARIOS}
 assert {"validation","not_found","unavailable","existing","conflict","safe_failure"} <= expected

def test_financing_scenario_requires_disclaimer_contract():
 schema=app.openapi()["components"]["schemas"]["FinancingEstimateResponse"]
 assert "disclaimer" in schema["required"]
