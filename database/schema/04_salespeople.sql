CREATE TABLE IF NOT EXISTS public.salespeople (
    salesperson_id TEXT PRIMARY KEY CHECK (salesperson_id ~ '^SALES-[0-9]{3}$'),
    name TEXT NOT NULL, synthetic_email TEXT NOT NULL UNIQUE,
    dealership_location TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_salespeople_location_active
    ON public.salespeople (dealership_location, active);
