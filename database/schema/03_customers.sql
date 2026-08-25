-- NexDrive Motors synthetic customer schema (PostgreSQL / Supabase).

CREATE TABLE IF NOT EXISTS public.customers (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    synthetic_phone TEXT NOT NULL UNIQUE,
    synthetic_email TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'TX',
    preferred_vehicle_type TEXT NOT NULL,
    preferred_brand TEXT NOT NULL,
    budget_min INTEGER NOT NULL,
    budget_max INTEGER NOT NULL,
    financing_needed BOOLEAN NOT NULL,
    estimated_down_payment INTEGER NOT NULL DEFAULT 0,
    family_size SMALLINT NOT NULL,
    trade_in BOOLEAN NOT NULL,
    purchase_timeline TEXT NOT NULL,
    lead_source TEXT NOT NULL,
    buyer_profile TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT customers_id_format_chk CHECK (customer_id ~ '^CUST-[0-9]{6}$'),
    CONSTRAINT customers_phone_synthetic_chk CHECK (synthetic_phone ~ '^\+1-555-010-[0-9]{4}$'),
    CONSTRAINT customers_email_synthetic_chk CHECK (synthetic_email ~ '^[a-z0-9._-]+@nexdrive\.example$'),
    CONSTRAINT customers_state_chk CHECK (state = 'TX'),
    CONSTRAINT customers_vehicle_type_chk CHECK (preferred_vehicle_type IN ('SUV', 'Sedan', 'Truck', 'Hatchback')),
    CONSTRAINT customers_budget_chk CHECK (budget_min >= 3000 AND budget_max >= budget_min AND budget_max <= 100000),
    CONSTRAINT customers_down_payment_chk CHECK (
        estimated_down_payment >= 0
        AND estimated_down_payment <= budget_max
        AND (financing_needed OR estimated_down_payment = 0)
    ),
    CONSTRAINT customers_family_size_chk CHECK (family_size BETWEEN 1 AND 8),
    CONSTRAINT customers_timeline_chk CHECK (purchase_timeline IN (
        'Within 7 Days', 'Within 30 Days', '1-3 Months', '3-6 Months', 'Researching'
    )),
    CONSTRAINT customers_profile_chk CHECK (buyer_profile IN ('Hot', 'Warm', 'Research', 'Edge Case'))
);

CREATE INDEX IF NOT EXISTS idx_customers_preferences
    ON public.customers (preferred_vehicle_type, preferred_brand);
CREATE INDEX IF NOT EXISTS idx_customers_budget
    ON public.customers (budget_min, budget_max);
CREATE INDEX IF NOT EXISTS idx_customers_timeline_profile
    ON public.customers (purchase_timeline, buyer_profile);
CREATE INDEX IF NOT EXISTS idx_customers_city
    ON public.customers (city);
