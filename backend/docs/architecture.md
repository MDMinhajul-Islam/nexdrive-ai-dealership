# Agent and API architecture

```text
Retell voice agent / dashboard
             |
       FastAPI /api/v1
       |      |       |
   leads  bookings  customer history
       \      |       /
        deterministic services
          |          |
 financing rules   repository
                     |
          Supabase schemas / local demo seeds
```

The HTTP layer validates input and maps errors. Workflow services own deterministic
scoring and financing calculations. The current local/demo repository loads the
synthetic CSV seeds at startup; production deployment should replace it with a
Supabase-backed repository while retaining the same routes and response shapes.

Every response includes `X-Request-ID`. Lead and appointment creation accept an
`Idempotency-Key`; replaying the same request is safe, while changing its payload
returns `409 Conflict`.
