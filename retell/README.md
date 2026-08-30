# Retell AI setup

1. Deploy the FastAPI backend over HTTPS and replace `{{BACKEND_BASE_URL}}` in `tools.json`.
2. Create a Retell agent and paste `agent_prompt.md` as its prompt.
3. Create custom functions from `tools.json`.
4. Keep `SUPABASE_SECRET_KEY` only in the backend; Retell never calls Supabase directly.
5. Run `python backend/scripts/validate_retell_tools.py` before configuring the agent.

Write safety: summarize and receive explicit confirmation before lead or booking calls. Retries are
idempotent by active customer lead and lead appointment. Always speak the financing disclaimer.

Escalate financing approval, negotiation, policy exceptions, complaints, or repeated tool failure.

