# NexDrive Backend

FastAPI backend and synthetic-data tooling for NexDrive AI Dealership.

## Setup

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # only if backend/.env does not already exist
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation or call
`GET /health` for the health check. Add Supabase credentials to `.env` before
using database-backed features.

## Read-only inventory tools

The first Retell-ready tools are exposed as typed endpoints:

```text
POST /api/tools/search-inventory
GET  /api/tools/get-vehicle-details/{vehicle_id}
GET  /api/tools/check-vehicle-availability/{vehicle_id}
GET  /api/tools/get-customer-history/{customer_id}
GET  /api/tools/get-test-drive-slots?start_date=YYYY-MM-DD
POST /api/tools/create-or-update-lead
POST /api/tools/create-test-drive
POST /api/tools/estimate-financing
```

`search-inventory` returns only currently available database records and supports make, model,
body type, condition, price, year, mileage, drivetrain, fuel, seating, and normalized feature
filters. Routes depend on an inventory repository abstraction: production uses Supabase, while
local tests use the read-only CSV repository.

Customer history returns the authoritative customer record with related CRM leads and appointments.
Test-drive slots are derived from active salesperson shifts and exclude existing Requested,
Confirmed, or Rescheduled appointments. Slot discovery is read-only and does not create a booking.

Write tools use natural idempotency: an active customer lead is updated instead of duplicated,
and a repeated booking for the same lead returns its existing appointment. Booking rechecks the
vehicle, salesperson shift, and slot immediately before insert. Financing responses are estimates,
use active database rules, and always return the lender-approval disclaimer. All API requests emit
PII-safe structured audit logs and an `X-Request-ID` response header.

`SUPABASE_PUBLISHABLE_KEY` is the public/client-safe key used for standard
requests. `SUPABASE_SECRET_KEY` is privileged and must remain backend-only; do
not include it in frontend configuration or API responses.

To verify the live Supabase connection after configuring `.env`, call:

```text
GET http://127.0.0.1:8000/health/database
```

A successful check returns `{"status":"ok","database":"connected","source":"supabase"}`.
The endpoint queries at most one `vehicles` row and returns HTTP 503 with a
sanitized response if configuration or connectivity fails.

Retrieve authoritative vehicle details and normalized feature names with:

```text
GET http://127.0.0.1:8000/api/vehicles/VEH-000001
```

Unknown valid-format IDs return HTTP 404, while malformed IDs return HTTP 422.

## Data scripts

Run scripts from the repository root so commands are consistent:

```bash
python backend/scripts/generate_vehicles.py
python backend/scripts/generate_customers.py
python backend/scripts/validate_customers.py
python backend/scripts/generate_salespeople.py
python backend/scripts/validate_salespeople.py
python backend/scripts/generate_leads.py
python backend/scripts/validate_leads.py
python backend/scripts/generate_appointments.py
python backend/scripts/validate_appointments.py
python backend/scripts/generate_trade_ins.py
python backend/scripts/validate_trade_ins.py
python backend/scripts/generate_financing.py
python backend/scripts/validate_financing.py
python backend/scripts/validate_business_data.py
python backend/scripts/generate_business_data.py
python backend/scripts/validate_data.py
```

Vehicle output remains in `database/seed`, while reference files and SQL schema
remain under `database/`. The validation report is written to
`backend/docs/validation_report.json`.

## Tests

```bash
cd backend
pytest
```

## Supabase import and deployment

Run migrations `01` through `09`, then validate and repeatably upsert seed data:

```bash
python scripts/validate_seed_compatibility.py
python scripts/import_supabase.py --dry-run
python scripts/import_supabase.py
```

Production can build from `backend/Dockerfile`. Configure secrets in the deployment platform,
set `CORS_ORIGINS` to the dashboard origin, and verify both health endpoints before enabling Retell.
