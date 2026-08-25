-- NexDrive Motors trade-in estimate schema (PostgreSQL / Supabase).

CREATE TABLE IF NOT EXISTS public.trade_ins (
    trade_in_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL UNIQUE REFERENCES public.leads(lead_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year SMALLINT NOT NULL,
    mileage INTEGER NOT NULL,
    condition TEXT NOT NULL,
    estimated_value INTEGER NOT NULL,
    loan_balance INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT trade_ins_id_format_chk CHECK (trade_in_id ~ '^TRD-[0-9]{5}$'),
    CONSTRAINT trade_ins_year_chk CHECK (year BETWEEN 2010 AND 2024),
    CONSTRAINT trade_ins_mileage_chk CHECK (mileage BETWEEN 0 AND 220000),
    CONSTRAINT trade_ins_condition_chk CHECK (condition IN ('Excellent', 'Good', 'Fair', 'Poor')),
    CONSTRAINT trade_ins_value_chk CHECK (estimated_value BETWEEN 1500 AND 100000),
    CONSTRAINT trade_ins_loan_chk CHECK (loan_balance BETWEEN 0 AND 125000),
    CONSTRAINT trade_ins_disclaimer_chk CHECK (notes ILIKE '%estimate%')
);

CREATE INDEX IF NOT EXISTS idx_trade_ins_customer ON public.trade_ins (customer_id);
CREATE INDEX IF NOT EXISTS idx_trade_ins_equity ON public.trade_ins ((estimated_value - loan_balance));
