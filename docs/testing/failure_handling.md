# Failure-handling matrix

| Condition | API | Agent behavior |
|---|---:|---|
| Invalid input | 422 | Ask for corrected detail |
| Record missing | 404 | Explain and offer alternatives |
| Vehicle/slot conflict | 409 | Re-query and offer alternatives |
| Duplicate lead/booking retry | 200 | Return updated/existing record |
| Supabase/network failure | 503 | Never guess; retry once, then escalate |
| Financing result | 200 | Speak estimate and full disclaimer |
| Unexpected error | sanitized 503 | Preserve request ID and escalate |
