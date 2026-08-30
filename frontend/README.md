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
