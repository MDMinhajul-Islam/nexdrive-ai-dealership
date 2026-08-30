CREATE TABLE IF NOT EXISTS public.trade_ins (
    trade_in_id TEXT PRIMARY KEY CHECK (trade_in_id ~ '^TRADE-[0-9]{6}$'),
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id),
    year SMALLINT NOT NULL CHECK (year BETWEEN 1980 AND 2035),
    make TEXT NOT NULL, model TEXT NOT NULL, mileage INTEGER NOT NULL CHECK (mileage BETWEEN 0 AND 500000),
    condition TEXT NOT NULL CHECK (condition IN ('Excellent','Good','Fair','Poor')),
    estimated_value NUMERIC(12,2) NOT NULL CHECK (estimated_value >= 0),
    status TEXT NOT NULL DEFAULT 'Estimated' CHECK (status IN ('Estimated','Appraisal Scheduled','Accepted','Declined')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trade_ins_customer ON public.trade_ins (customer_id, created_at DESC);
