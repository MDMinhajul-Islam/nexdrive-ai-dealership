-- Traceable voice-agent outcomes and human escalation. Run after 01-09.
CREATE TABLE IF NOT EXISTS public.conversation_sessions (
    session_id TEXT PRIMARY KEY CHECK (session_id ~ '^CALL-[A-Z0-9-]{6,40}$'),
    channel TEXT NOT NULL CHECK (channel IN ('Phone','Web Voice')),
    status TEXT NOT NULL CHECK (status IN ('Completed','Escalated','Dropped','Failed')),
    outcome TEXT NOT NULL CHECK (outcome IN ('Discovery','Vehicle Recommended','Lead Created','Test Drive Booked','Escalated','No Action','Failed')),
    customer_id TEXT REFERENCES public.customers(customer_id) ON DELETE SET NULL,
    lead_id TEXT REFERENCES public.leads(lead_id) ON DELETE SET NULL,
    appointment_id TEXT REFERENCES public.appointments(appointment_id) ON DELETE SET NULL,
    summary TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.escalation_events (
    escalation_id TEXT PRIMARY KEY CHECK (escalation_id ~ '^ESC-[0-9]{6}$'),
    session_id TEXT NOT NULL REFERENCES public.conversation_sessions(session_id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES public.customers(customer_id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_salesperson TEXT REFERENCES public.salespeople(salesperson_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_status ON public.conversation_sessions(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_outcome ON public.conversation_sessions(outcome, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_escalation_events_open ON public.escalation_events(resolved, created_at DESC);

ALTER TABLE public.conversation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalation_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.conversation_sessions, public.escalation_events FROM anon, authenticated;
