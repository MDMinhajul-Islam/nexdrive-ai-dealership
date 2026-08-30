# Architecture

```text
Customer phone call
  -> Retell agent (prompt + tool definitions)
  -> HTTPS FastAPI /api/tools
  -> validation -> service rules -> repository
  -> Supabase PostgreSQL (RLS; service-role backend only)
  -> grounded response + request ID

Admin browser -> React dashboard -> /api/admin read endpoints -> Supabase
```

Synthetic generators produce CSV seed artifacts. Validators gate import. Migrations run 01 through 09,
then the repeatable importer upserts tables in foreign-key dependency order.
