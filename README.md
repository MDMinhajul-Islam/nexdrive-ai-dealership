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

Use `--seed` and `--count` to create a reproducible alternative dataset. Run either script with `--help` for all options.

## Repository layout

- `database/reference`: controlled vehicle, feature, color, and financing reference data
- `database/schema`: Supabase/PostgreSQL schema migrations
- `database/seed`: generated CSV artifacts
- `backend/app`: FastAPI application, routes, services, schemas, and utilities
- `backend/scripts`: deterministic data generators and validation tools
- `backend/docs`: backend architecture, ERD, testing, reports, and screenshots
- `frontend`, `retell`: placeholders for future milestones

All people, contact details, vehicle identifiers, and business records in this project must be synthetic.
