-- NexDrive Motors deterministic financing-estimate rules (PostgreSQL / Supabase).

CREATE TABLE IF NOT EXISTS public.financing_options (
    financing_rule_id TEXT PRIMARY KEY,
    vehicle_condition TEXT NOT NULL,
    term_months SMALLINT NOT NULL,
    apr_min NUMERIC(5,2) NOT NULL,
    apr_max NUMERIC(5,2) NOT NULL,
    minimum_down_payment_percent NUMERIC(5,2) NOT NULL,
    maximum_vehicle_age_years SMALLINT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    disclaimer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT financing_id_format_chk CHECK (financing_rule_id ~ '^FIN-[0-9]{3}$'),
    CONSTRAINT financing_condition_chk CHECK (vehicle_condition IN ('New', 'Used', 'Certified Pre-Owned')),
    CONSTRAINT financing_term_chk CHECK (term_months IN (36, 48, 60, 72)),
    CONSTRAINT financing_apr_chk CHECK (apr_min >= 0 AND apr_max >= apr_min AND apr_max <= 30),
    CONSTRAINT financing_down_payment_chk CHECK (minimum_down_payment_percent BETWEEN 0 AND 100),
    CONSTRAINT financing_age_chk CHECK (maximum_vehicle_age_years BETWEEN 0 AND 15),
    CONSTRAINT financing_disclaimer_chk CHECK (disclaimer ILIKE '%lender approval%'),
    CONSTRAINT financing_condition_term_uniq UNIQUE (vehicle_condition, term_months)
);

CREATE INDEX IF NOT EXISTS idx_financing_condition_active
    ON public.financing_options (vehicle_condition, active, term_months);
