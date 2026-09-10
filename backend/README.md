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
POST /api/tools/get-test-drive-slots
POST /api/tools/create-or-update-lead
POST /api/tools/create-test-drive
POST /api/tools/estimate-financing
```

`search-inventory` returns only currently available database records and supports make, model,
body type, condition, price, year, mileage, drivetrain, fuel, seating, and normalized feature
filters. Routes depend on an inventory repository abstraction: production uses Supabase, while
local tests use the read-only CSV repository.

Customer history returns the authoritative customer record with related CRM leads and appointments.
Test-drive slots require `vehicle_id` and `requested_date`, verify that the vehicle is currently
test-drive eligible, and exclude existing Requested, Confirmed, or Rescheduled appointments. The
legacy POST request field `start_date` remains accepted as an alias. Slot discovery is read-only.

Write tools use atomic PostgreSQL functions from migration `12_atomic_tool_writes.sql`: concurrent
lead upserts serialize per customer, and booking eligibility, idempotency, slot validation, and
insert happen in one transaction. A repeated exact booking returns its persisted appointment.
Financing responses are estimates,
use active database rules, and always return the lender-approval disclaimer. All API requests emit
PII-safe structured audit logs and an `X-Request-ID` response header.

All `/api/tools` requests require the server-to-server header
`X-Retell-Tool-Key`, whose value must match backend-only
`RETELL_TOOL_API_KEY`. Configure the same secret in Retell's tool request
headers; never expose it to the browser. Customer-history requests also require
`X-Retell-Verified-Customer-ID`, populated from the customer identity verified
by the trusted Retell flow, and it must match the requested `customer_id`.
Retell tool requests may send `X-Retell-Call-ID`; the backend validates this
correlation value and includes it in PII-safe structured execution logs.

`POST /api/retell/create-web-call` is limited per backend-observed client IP and,
when present, a validated `X-Session-ID` header or `session_id` cookie. Defaults
are five requests per 60 seconds and can be tuned with
`RETELL_WEB_CALL_RATE_LIMIT_REQUESTS` and
`RETELL_WEB_CALL_RATE_LIMIT_WINDOW_SECONDS`. A rejected request returns HTTP
429 with a `Retry-After` header and a safe `RATE_LIMITED` response.

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

`GET /health/readiness` validates the database, Retell, and tool-authentication
configuration groups without returning secret values. In production it also
checks that admin authentication is enabled and CORS is not wildcard. It
returns HTTP 503 with group-level status when configuration is incomplete.

Retrieve authoritative vehicle details, normalized feature names, and ordered
Supabase Storage image metadata with:

```text
GET http://127.0.0.1:8000/api/vehicles/VEH-000001
```

Unknown valid-format IDs return HTTP 404, while malformed IDs return HTTP 422.
Inventory records expose `primary_image_url` and `images`; the older
`image_url` and `image_thumbnail_url` fields remain compatible aliases. See
`docs/vehicle_images_storage.md` for the public `vehicle-images` bucket rollout
and upload mapping rules.

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

Run migrations `01` through `13`, then validate and repeatably upsert seed data. To add licensed
representative make/model photography, configure `CARSXE_API_KEY` only in the backend environment
and run the controlled legacy-cache sync after migration 13:

```powershell
python scripts/sync_vehicle_images.py --dry-run
python scripts/sync_vehicle_images.py --scope model
```

The default sync performs 41 provider lookups for the current catalog. Use `--scope year-model`
only when the API plan supports roughly 401 lookups. The public API never exposes the provider key
and falls back to bundled body-type artwork if a licensed photo is unavailable.

```bash
python scripts/validate_seed_compatibility.py
python scripts/import_supabase.py --dry-run
python scripts/import_supabase.py
```

Production can build from `backend/Dockerfile`. Configure secrets in the deployment platform,
set `CORS_ORIGINS` to the dashboard origin, and verify availability, readiness,
and database health endpoints before enabling Retell.
