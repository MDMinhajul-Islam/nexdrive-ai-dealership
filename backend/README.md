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
