CREATE TABLE IF NOT EXISTS public.leads (
    lead_id TEXT PRIMARY KEY CHECK (lead_id ~ '^LEAD-[0-9]{6}$'),
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id),
    vehicle_id TEXT REFERENCES public.vehicles(vehicle_id),
    salesperson_id TEXT REFERENCES public.salespeople(salesperson_id),
    source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New'
        CHECK (status IN ('New','Contacted','Qualified','Appointment Set','Won','Lost')),
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    score_reason TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_leads_customer_created ON public.leads (customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_status_score ON public.leads (status, score DESC);
