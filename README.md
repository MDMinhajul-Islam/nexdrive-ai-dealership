# NexDrive AI Dealership

Production-style AI car dealership demo with synthetic dealership data, Supabase, Retell AI, and tool-driven business workflows.

The repository includes a realistic relational inventory dataset and a FastAPI backend scaffold for the fictional NexDrive Motors dealership group in Plano, Texas.

## Milestone 1: Vehicle dataset

Generate 10,000 deterministic synthetic vehicles and normalized feature relationships:

```powershell
python backend/scripts/generate_vehicles.py
python backend/scripts/validate_data.py
```

The generator writes:

- `database/seed/vehicles.csv`
- `database/seed/features.csv`
- `database/seed/vehicle_features.csv`

## Milestone 2: Customer dataset

Generate and validate 5,000 privacy-safe synthetic customer profiles:

```powershell
python backend/scripts/generate_customers.py
python backend/scripts/validate_customers.py
```

The customer generator writes `database/seed/customers.csv`. All phone numbers use a clearly
synthetic 555 namespace and all email addresses use the reserved `.example` domain.

## Milestone 3: Salespeople dataset

Generate and validate the 10-person synthetic dealership roster:

```powershell
python backend/scripts/generate_salespeople.py
python backend/scripts/validate_salespeople.py
```

The roster is written to `database/seed/salespeople.csv` with queryable PostgreSQL array
literals for languages and working days.

## Milestone 4: Leads dataset

Generate and validate 4,000 relational CRM leads:

```powershell
python backend/scripts/generate_leads.py
python backend/scripts/validate_leads.py
```

Leads reference existing customers, active salespeople, and matching inventory. Lead scores are
computed deterministically from captured business signals.

## Milestone 5: Action datasets

Regenerate and validate all post-inventory business data in dependency order:

```powershell
python backend/scripts/generate_business_data.py
```

This produces 1,500 appointments, 40 trade-in estimates, and 12 financing rules in addition to
customers, salespeople, and leads, then runs the cross-dataset relationship quality gate.

Use `--seed` and `--count` to create a reproducible alternative dataset. Run either script with `--help` for all options.

## Repository layout

- `database/reference`: controlled vehicle, feature, color, and financing reference data
- `database/schema`: Supabase/PostgreSQL schema migrations
- `database/seed`: generated CSV artifacts
- `backend/app`: FastAPI application, routes, services, schemas, and utilities
- `backend/scripts`: deterministic data generators and validation tools
- `backend/docs`: backend architecture, ERD, testing, reports, and screenshots
- `frontend`: responsive React/Vite operations dashboard
- `retell`: voice-agent prompt, tool contracts, confirmation and escalation rules

## Product experience

The frontend now separates the customer dealership experience from dealership
operations. `/`, `/inventory` and `/talk-to-ai` are customer-safe. `/admin/login`
uses Supabase Auth and `/admin` exposes inventory management, CRM, appointments
and traceable call analytics. Production must enable `ADMIN_AUTH_REQUIRED` and
run migration `10_agent_operations.sql` before enabling the new voice outcomes.
- `docs`: architecture, tool reference, failure matrix, deployment and demo guides

## Demo-readiness verification

```powershell
python backend/scripts/validate_seed_compatibility.py
python backend/scripts/import_supabase.py --dry-run
python backend/scripts/validate_retell_tools.py
cd backend; pytest
cd ../frontend; npm install; npm run lint; npm run build
```

Run database migrations in filename order (`01`–`11`). RLS denies direct browser access; only the
trusted FastAPI backend uses the Supabase secret/service-role key. Never commit `.env` files.

All people, contact details, vehicle identifiers, and business records in this project must be synthetic.
