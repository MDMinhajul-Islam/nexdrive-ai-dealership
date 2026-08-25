-- NexDrive Motors vehicle inventory schema
-- PostgreSQL / Supabase compatible
-- Run before 02_features.sql because vehicle_features references vehicles.

CREATE TABLE IF NOT EXISTS public.vehicles (
    vehicle_id TEXT PRIMARY KEY,
    vin TEXT NOT NULL UNIQUE,
    stock_number TEXT NOT NULL UNIQUE,

    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year SMALLINT NOT NULL,
    trim TEXT NOT NULL,

    body_type TEXT NOT NULL,
    condition TEXT NOT NULL,
    mileage INTEGER NOT NULL DEFAULT 0,

    exterior_color TEXT NOT NULL,
    interior_color TEXT NOT NULL,

    fuel_type TEXT NOT NULL,
    transmission TEXT NOT NULL,
    drivetrain TEXT NOT NULL,
    seating_capacity SMALLINT NOT NULL,

    msrp NUMERIC(12, 2) NOT NULL,
    sale_price NUMERIC(12, 2) NOT NULL,

    vehicle_status TEXT NOT NULL,
    test_drive_available BOOLEAN NOT NULL DEFAULT FALSE,

    warranty TEXT NOT NULL,
    certification TEXT NOT NULL,
    dealership_location TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT vehicles_vehicle_id_format_chk
        CHECK (vehicle_id ~ '^VEH-[0-9]{6}$'),
    CONSTRAINT vehicles_vin_format_chk
        CHECK (vin ~ '^[A-HJ-NPR-Z0-9]{17}$'),
    CONSTRAINT vehicles_stock_number_format_chk
        CHECK (stock_number ~ '^NX-[0-9]{6}$'),
    CONSTRAINT vehicles_year_chk
        CHECK (year BETWEEN 1980 AND 2035),
    CONSTRAINT vehicles_body_type_chk
        CHECK (body_type IN (
            'SUV', 'Sedan', 'Truck', 'Hatchback', 'Coupe',
            'Wagon', 'Minivan', 'Van', 'Convertible'
        )),
    CONSTRAINT vehicles_condition_chk
        CHECK (condition IN ('New', 'Used', 'Certified Pre-Owned')),
    CONSTRAINT vehicles_mileage_chk
        CHECK (mileage BETWEEN 0 AND 500000),
    CONSTRAINT vehicles_fuel_type_chk
        CHECK (fuel_type IN (
            'Gasoline', 'Diesel', 'Hybrid', 'Plug-in Hybrid', 'Electric'
        )),
    CONSTRAINT vehicles_transmission_chk
        CHECK (transmission IN (
            'Automatic', 'Single-Speed Automatic', 'Manual', 'CVT'
        )),
    CONSTRAINT vehicles_drivetrain_chk
        CHECK (drivetrain IN ('FWD', 'RWD', 'AWD', '4WD')),
    CONSTRAINT vehicles_seating_capacity_chk
        CHECK (seating_capacity BETWEEN 1 AND 15),
    CONSTRAINT vehicles_msrp_chk
        CHECK (msrp > 0),
    CONSTRAINT vehicles_sale_price_chk
        CHECK (sale_price > 0 AND sale_price <= msrp),
    CONSTRAINT vehicles_status_chk
        CHECK (vehicle_status IN (
            'Available', 'Reserved', 'Sold', 'Pending Sale',
            'In Service', 'Arriving Soon', 'Demo Vehicle', 'No Test Drive'
        )),
    CONSTRAINT vehicles_test_drive_state_chk
        CHECK (
            NOT test_drive_available
            OR vehicle_status IN ('Available', 'Demo Vehicle')
        ),
    CONSTRAINT vehicles_new_mileage_chk
        CHECK (condition <> 'New' OR mileage <= 500),
    CONSTRAINT vehicles_cpo_certification_chk
        CHECK (
            condition <> 'Certified Pre-Owned'
            OR certification <> 'None'
        )
);

-- Common inventory-search paths used by the voice agent.
CREATE INDEX IF NOT EXISTS idx_vehicles_status_price
    ON public.vehicles (vehicle_status, sale_price);

CREATE INDEX IF NOT EXISTS idx_vehicles_make_model_year
    ON public.vehicles (make, model, year DESC);

CREATE INDEX IF NOT EXISTS idx_vehicles_body_condition_price
    ON public.vehicles (body_type, condition, sale_price);

CREATE INDEX IF NOT EXISTS idx_vehicles_drivetrain_fuel
    ON public.vehicles (drivetrain, fuel_type);

CREATE INDEX IF NOT EXISTS idx_vehicles_seating_capacity
    ON public.vehicles (seating_capacity);

CREATE INDEX IF NOT EXISTS idx_vehicles_location
    ON public.vehicles (dealership_location);

CREATE INDEX IF NOT EXISTS idx_vehicles_available_search
    ON public.vehicles (sale_price, body_type, make, model)
    WHERE vehicle_status = 'Available';