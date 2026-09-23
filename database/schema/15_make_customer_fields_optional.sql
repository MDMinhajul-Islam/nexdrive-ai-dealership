-- Migration: Make customer qualification fields optional for real customer creation
-- Allows minimal customer creation with just first_name, last_name, synthetic_phone.
-- Broadens phone/email CHECK constraints to accept both synthetic and real formats.
-- Does NOT modify existing rows. Does NOT drop or recreate the table.

BEGIN;

-- 1. Make eleven qualification columns nullable
ALTER TABLE public.customers
    ALTER COLUMN city DROP NOT NULL,
    ALTER COLUMN preferred_vehicle_type DROP NOT NULL,
    ALTER COLUMN preferred_brand DROP NOT NULL,
    ALTER COLUMN budget_min DROP NOT NULL,
    ALTER COLUMN budget_max DROP NOT NULL,
    ALTER COLUMN financing_needed DROP NOT NULL,
    ALTER COLUMN family_size DROP NOT NULL,
    ALTER COLUMN trade_in DROP NOT NULL,
    ALTER COLUMN purchase_timeline DROP NOT NULL,
    ALTER COLUMN lead_source DROP NOT NULL,
    ALTER COLUMN buyer_profile DROP NOT NULL;

-- 2. Make synthetic_email nullable (email is optional for new customers)
ALTER TABLE public.customers
    ALTER COLUMN synthetic_email DROP NOT NULL;

-- 3. Replace synthetic-only phone constraint with one that accepts both formats:
--    Synthetic: +1-555-010-XXXX
--    Real (normalized by backend): +1-XXX-XXX-XXXX
ALTER TABLE public.customers
    DROP CONSTRAINT customers_phone_synthetic_chk;

ALTER TABLE public.customers
    ADD CONSTRAINT customers_phone_format_chk
    CHECK (synthetic_phone ~ '^\+1-[0-9]{3}-[0-9]{3}-[0-9]{4}$');

-- 4. Replace synthetic-only email constraint with one that accepts both formats:
--    Synthetic: xxx@nexdrive.example
--    Real (normalized by backend): standard email format
--    NULL is allowed (email is optional)
ALTER TABLE public.customers
    DROP CONSTRAINT customers_email_synthetic_chk;

ALTER TABLE public.customers
    ADD CONSTRAINT customers_email_format_chk
    CHECK (synthetic_email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$');

-- 5. Budget constraint: existing CHECK references budget_min, budget_max.
--    In PostgreSQL, CHECK constraints treat NULL as "not false" (i.e. pass).
--    So when budget_min and budget_max are both NULL, the existing constraint
--    customers_budget_chk will pass. No change needed.

-- 6. Down-payment constraint: references budget_max and financing_needed.
--    When these are NULL the CHECK passes (NULL is not false in PostgreSQL).
--    No change needed.

-- 7. Family-size constraint: when family_size is NULL the CHECK passes.
--    No change needed.

-- 8. Timeline, profile, vehicle-type constraints: when column is NULL the
--    CHECK passes. No change needed.

-- 9. State constraint: state retains NOT NULL DEFAULT 'TX'. No change needed.

COMMIT;
