# Deployment checklist

- Run schemas `01_vehicles.sql` through `11_vehicle_images.sql` in order.
- Configure backend-only `CARSXE_API_KEY`, then run `python scripts/sync_vehicle_images.py --scope model` once.
- Run every dataset validator and `validate_seed_compatibility.py`.
- Dry-run, then run `import_supabase.py`; verify table counts.
- Configure backend `SUPABASE_URL`, publishable/secret keys, `CORS_ORIGINS`,
  `ADMIN_AUTH_REQUIRED=true` and `ADMIN_EMAILS` outside Git.
- Build and deploy `backend/Dockerfile`; verify `/health` and `/health/database` over HTTPS.
- Build frontend with `VITE_API_BASE_URL`, `VITE_SUPABASE_URL` and
  `VITE_SUPABASE_PUBLISHABLE_KEY`. These are build arguments; never expose the secret/service-role key.
- Replace `{{BACKEND_BASE_URL}}` in Retell tools and validate contracts.
- Run backend tests, frontend lint/build, 24 scenarios, and one controlled end-to-end call.
- Confirm logs contain request IDs but no keys or unnecessary PII.
