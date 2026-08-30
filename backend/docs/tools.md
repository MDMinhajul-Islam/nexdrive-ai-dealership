# Voice-agent tool contract

| Tool | Method and path | Required input | Successful result |
|---|---|---|---|
| Create lead | `POST /api/v1/leads` | `customer_id`; optional `vehicle_id`, `source`, `notes` | Lead with deterministic score and explanation |
| Update lead | `PATCH /api/v1/leads/{lead_id}` | Any of `vehicle_id`, `status`, `notes` | Updated and rescored lead |
| Book appointment | `POST /api/v1/appointments` | Customer, vehicle, future ISO timestamp | Scheduled appointment |
| Customer history | `GET /api/v1/customers/{customer_id}/history` | Customer ID | Customer, leads, appointments, trade-ins |
| Estimate financing | `POST /api/v1/financing/estimate` | Price, down payment, credit score, term | APR, principal, payment and disclaimer |

Callers should send a unique `Idempotency-Key` for create calls and retain the
`X-Request-ID` response header for support. Financing is an estimate—not an offer.
