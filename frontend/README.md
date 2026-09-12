# NexDrive customer website and operations portal

The Vite/React application contains customer-safe routes and a separate
internal admin experience:

- `/` premium dealership landing page
- `/inventory` live customer inventory, details and compare selection
- `/talk-to-ai` Retell-ready voice concierge surface
- `/admin/login` Supabase Auth sign-in
- `/admin` inventory, CRM, appointments and call analytics

## Local configuration

Copy `.env.example` to `.env` and set `VITE_API_BASE_URL`. Admin sign-in also
requires the public Supabase URL and publishable key. Voice calls obtain a
short-lived access token from `POST /api/retell/create-web-call`; Retell API
keys and agent configuration remain exclusively on the backend.

Inventory cards and details consume `primary_image_url` and the ordered
`images` array returned by the backend. Supabase Storage credentials are not
needed in the browser. Generic body-type artwork remains a visibly labelled
fallback when no verified per-vehicle photo is available.

## Dokploy

Use build path `/frontend`, Dockerfile `Dockerfile`, context `/frontend`, domain
container port `80`, and HTTPS. Add these as Docker **Build Time Arguments**:

```env
VITE_API_BASE_URL=https://api.example.com
VITE_SUPABASE_URL=https://project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=public-key
```

After the frontend domain is live, set the exact HTTPS origin in backend
`CORS_ORIGINS` and rebuild the backend. Production voice calls require HTTPS
so the browser can grant microphone access securely.

For separate frontend/backend services, `VITE_API_BASE_URL` must be the backend
HTTPS origin only (no `/api` suffix). For example, `https://api.example.com`
produces `https://api.example.com/api/admin/appointments/APT-000321` for deletion.
Vite embeds this value at build time; changing an nginx runtime environment
variable does not update an existing bundle. Rebuild the frontend after changes.
An unset value uses same-origin `/api/...` requests, which requires an explicitly
configured API reverse proxy. The supplied nginx configuration serves the SPA
only, so separate Dokploy services require the build argument above.

Set backend `CORS_ORIGINS=https://your-frontend-domain` (comma-separated for
multiple approved origins, no path or trailing slash). Admin DELETE preflight
must allow `DELETE`, `Authorization`, and `Content-Type` for that origin.
Keep `ADMIN_AUTH_REQUIRED=true` and the existing `ADMIN_EMAILS` allowlist.
