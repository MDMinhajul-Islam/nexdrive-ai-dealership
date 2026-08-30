# Architecture

```text
Customer phone call / public web voice
  -> Retell agent (prompt + tool definitions)
  -> HTTPS FastAPI /api/tools
  -> validation -> service rules -> repository
  -> Supabase PostgreSQL (RLS; service-role backend only)
  -> grounded response + request ID

Public browser -> React showroom -> /api/public read endpoints -> Supabase

Admin browser -> Supabase Auth -> React operations portal
  -> Bearer-protected /api/admin read/write endpoints -> Supabase

Voice outcome -> trade-in / escalation / conversation tools
  -> conversation_sessions + escalation_events -> analytics evidence
```

Synthetic generators produce CSV seed artifacts. Validators gate import. Migrations run 01 through 10,
then the repeatable importer upserts tables in foreign-key dependency order.
