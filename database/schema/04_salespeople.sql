-- NexDrive Motors synthetic sales-team schema (PostgreSQL / Supabase).

CREATE TABLE IF NOT EXISTS public.salespeople (
    salesperson_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    synthetic_email TEXT NOT NULL UNIQUE,
    synthetic_phone TEXT NOT NULL UNIQUE,
    languages TEXT[] NOT NULL,
    specialization TEXT NOT NULL,
    working_days TEXT[] NOT NULL,
    shift_start TIME NOT NULL,
    shift_end TIME NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT salespeople_id_format_chk CHECK (salesperson_id ~ '^SP-[0-9]{3}$'),
    CONSTRAINT salespeople_email_synthetic_chk CHECK (synthetic_email ~ '^[a-z0-9._-]+@nexdrive\.example$'),
    CONSTRAINT salespeople_phone_synthetic_chk CHECK (synthetic_phone ~ '^\+1-555-020-[0-9]{4}$'),
    CONSTRAINT salespeople_languages_chk CHECK (
        cardinality(languages) >= 1
        AND languages <@ ARRAY['English', 'Spanish', 'Hindi', 'Urdu']::TEXT[]
    ),
    CONSTRAINT salespeople_specialization_chk CHECK (specialization IN (
        'General Sales', 'SUV Specialist', 'Truck Specialist',
        'EV/Hybrid Specialist', 'Used/CPO Specialist', 'Financing-Focused'
    )),
    CONSTRAINT salespeople_working_days_chk CHECK (
        cardinality(working_days) >= 1
        AND working_days <@ ARRAY[
            'Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'
        ]::TEXT[]
    ),
    CONSTRAINT salespeople_shift_chk CHECK (shift_start < shift_end)
);

CREATE INDEX IF NOT EXISTS idx_salespeople_active_specialization
    ON public.salespeople (active, specialization);
CREATE INDEX IF NOT EXISTS idx_salespeople_working_days
    ON public.salespeople USING GIN (working_days);
CREATE INDEX IF NOT EXISTS idx_salespeople_languages
    ON public.salespeople USING GIN (languages);
