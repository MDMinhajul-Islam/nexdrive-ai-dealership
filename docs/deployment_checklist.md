# Deployment checklist

- Run schemas `01_vehicles.sql` through `09_rls_policies.sql` in order.
- Run every dataset validator and `validate_seed_compatibility.py`.
- Dry-run, then run `import_supabase.py`; verify table counts.
- Configure backend `SUPABASE_URL`, publishable/secret keys and `CORS_ORIGINS` outside Git.
- Build and deploy `backend/Dockerfile`; verify `/health` and `/health/database` over HTTPS.
- Build frontend with `VITE_API_BASE_URL` set to the public backend.
- Replace `{{BACKEND_BASE_URL}}` in Retell tools and validate contracts.
- Run backend tests, frontend lint/build, 19 scenarios, and one controlled end-to-end call.
- Confirm logs contain request IDs but no keys or unnecessary PII.
