-- Licensed representative photography for synthetic inventory. Run after 01-10.
CREATE TABLE IF NOT EXISTS public.vehicle_images (
    image_key TEXT PRIMARY KEY,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    model_year INTEGER,
    image_url TEXT NOT NULL CHECK (image_url ~ '^https://'),
    thumbnail_url TEXT CHECK (thumbnail_url IS NULL OR thumbnail_url ~ '^https://'),
    source_url TEXT CHECK (source_url IS NULL OR source_url ~ '^https://'),
    usage_license TEXT NOT NULL DEFAULT 'ShareCommercially',
    provider TEXT NOT NULL DEFAULT 'CarsXE',
    width INTEGER,
    height INTEGER,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vehicle_images_dimensions_chk CHECK (
        (width IS NULL OR width > 0) AND (height IS NULL OR height > 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_vehicle_images_lookup
    ON public.vehicle_images (make, model, model_year);

ALTER TABLE public.vehicle_images ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.vehicle_images FROM anon, authenticated;
GRANT ALL ON public.vehicle_images TO service_role;
