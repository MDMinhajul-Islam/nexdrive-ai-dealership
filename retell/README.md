# Retell AI setup

1. Deploy the FastAPI backend over HTTPS and replace `{{BACKEND_BASE_URL}}` in `tools.json`.
2. Use the published Retell conversation-flow agent `agent_21b622a1bc23eaf14f2606f458`.
3. Set backend `RETELL_AGENT_ID=agent_21b622a1bc23eaf14f2606f458` in every environment. This value replaces the earlier single-prompt agent id.
4. Create custom functions from `tools.json` and attach them to the flow nodes that call backend tools.
5. Keep `SUPABASE_SECRET_KEY` only in the backend; Retell never calls Supabase directly.
6. Run `python backend/scripts/validate_retell_tools.py` before configuring the agent.

Write safety: summarize and receive explicit confirmation before lead or booking calls. Retries are
idempotent by active customer lead and lead appointment. Always speak the financing disclaimer.

Escalate financing approval, negotiation, policy exceptions, complaints, or repeated tool failure.

