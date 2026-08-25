-- NexDrive Motors CRM lead schema (PostgreSQL / Supabase).
-- Requires customers, vehicles, and salespeople tables.

CREATE TABLE IF NOT EXISTS public.leads (
    lead_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    lead_status TEXT NOT NULL,
    budget INTEGER NOT NULL,
    vehicle_interest TEXT REFERENCES public.vehicles(vehicle_id) ON UPDATE CASCADE ON DELETE SET NULL,
    purchase_timeline TEXT NOT NULL,
    financing_needed BOOLEAN NOT NULL,
    trade_in BOOLEAN NOT NULL,
    lead_score SMALLINT NOT NULL,
    lead_temperature TEXT NOT NULL,
    assigned_salesperson TEXT NOT NULL REFERENCES public.salespeople(salesperson_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    next_followup_date DATE,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT leads_id_format_chk CHECK (lead_id ~ '^LEAD-[0-9]{6}$'),
    CONSTRAINT leads_source_chk CHECK (source IN (
        'Website', 'Inbound Call', 'Paid Search', 'Referral',
        'Social Media', 'Walk-In', 'Vehicle Marketplace'
    )),
    CONSTRAINT leads_status_chk CHECK (lead_status IN (
        'New', 'Contacted', 'Discovery', 'Qualified', 'Vehicle Recommended',
        'Test Drive', 'Negotiation', 'Financing', 'Won', 'Lost'
    )),
    CONSTRAINT leads_budget_chk CHECK (budget BETWEEN 3000 AND 100000),
    CONSTRAINT leads_timeline_chk CHECK (purchase_timeline IN (
        'Within 7 Days', 'Within 30 Days', '1-3 Months', '3-6 Months', 'Researching'
    )),
    CONSTRAINT leads_score_chk CHECK (lead_score BETWEEN 0 AND 100),
    CONSTRAINT leads_temperature_chk CHECK (
        (lead_score >= 70 AND lead_temperature = 'Hot')
        OR (lead_score BETWEEN 40 AND 69 AND lead_temperature = 'Warm')
        OR (lead_score <= 39 AND lead_temperature = 'Cold')
    ),
    CONSTRAINT leads_terminal_followup_chk CHECK (
        (lead_status IN ('Won', 'Lost') AND next_followup_date IS NULL)
        OR (lead_status NOT IN ('Won', 'Lost') AND next_followup_date IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_leads_customer ON public.leads (customer_id);
CREATE INDEX IF NOT EXISTS idx_leads_salesperson_status ON public.leads (assigned_salesperson, lead_status);
CREATE INDEX IF NOT EXISTS idx_leads_score ON public.leads (lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_followup ON public.leads (next_followup_date) WHERE next_followup_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_vehicle_interest ON public.leads (vehicle_interest) WHERE vehicle_interest IS NOT NULL;
