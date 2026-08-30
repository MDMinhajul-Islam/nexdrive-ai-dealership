# Failure-handling matrix

| Condition | HTTP | Agent behavior |
|---|---:|---|
| Validation error / invalid financing range | 422 | Explain the invalid field and ask once for correction |
| Customer or vehicle not found | 404 | Reconfirm the identifier; never invent a record |
| Vehicle unavailable for test drive | 409 | Offer another available vehicle or consultation |
| Idempotency key reused with changed input | 409 | Generate a new key only for a genuinely new action |
| Supabase unavailable in production | 503 (production adapter) | Apologize, preserve request ID, offer human follow-up |
| Unexpected server error | 500 | Do not retry writes blindly; escalate with request ID |

Retries are safe only when a create request carries the same idempotency key and
unchanged payload. Do not present financing output as approval or guaranteed terms.
