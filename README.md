# NexDrive AI Dealership

Production-style AI car dealership demo with synthetic dealership data, Supabase, Retell AI, and tool-driven business workflows.

The current milestone focuses only on a realistic, relational inventory dataset for the fictional NexDrive Motors dealership group in Plano, Texas. Frontend, backend, and voice-agent implementations are intentionally deferred.

## Milestone 1: Vehicle dataset

Generate 10,000 deterministic synthetic vehicles and normalized feature relationships:

```powershell
python database/generators/generate_vehicles.py
python database/validation/validate_vehicles.py
```

The generator writes:

- `database/seed/vehicles.csv`
- `database/seed/features.csv`
- `database/seed/vehicle_features.csv`

Use `--seed` and `--count` to create a reproducible alternative dataset. Run either script with `--help` for all options.

## Repository layout

- `database/reference`: controlled vehicle, feature, color, and financing reference data
- `database/generators`: deterministic synthetic-data generators
- `database/validation`: data-quality and relationship checks
- `database/schema`: Supabase/PostgreSQL schema migrations
- `database/seed`: generated CSV artifacts
- `backend`, `frontend`, `retell`: placeholders for future milestones
- `docs`: architecture, ERD, testing, and screenshots

All people, contact details, vehicle identifiers, and business records in this project must be synthetic.

