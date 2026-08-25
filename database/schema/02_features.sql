-- NexDrive Motors normalized vehicle-feature schema
-- PostgreSQL / Supabase compatible
-- Requires public.vehicles from 01_vehicles.sql.

CREATE TABLE IF NOT EXISTS public.features (
    feature_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT features_feature_id_format_chk
        CHECK (feature_id ~ '^FEAT-[0-9]{3}$'),
    CONSTRAINT features_category_chk
        CHECK (category IN (
            'Safety & Driver Assistance',
            'Comfort & Convenience',
            'Connectivity',
            'Utility'
        ))
);

CREATE TABLE IF NOT EXISTS public.vehicle_features (
    vehicle_id TEXT NOT NULL,
    feature_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT vehicle_features_pkey
        PRIMARY KEY (vehicle_id, feature_id),
    CONSTRAINT vehicle_features_vehicle_fk
        FOREIGN KEY (vehicle_id)
        REFERENCES public.vehicles (vehicle_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT vehicle_features_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES public.features (feature_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- Primary key already indexes (vehicle_id, feature_id).
-- This reverse index makes feature-based filtering efficient.
CREATE INDEX IF NOT EXISTS idx_vehicle_features_feature_vehicle
    ON public.vehicle_features (feature_id, vehicle_id);

CREATE INDEX IF NOT EXISTS idx_features_category
    ON public.features (category);