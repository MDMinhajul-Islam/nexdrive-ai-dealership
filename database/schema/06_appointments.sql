CREATE TABLE IF NOT EXISTS public.appointments (
    appointment_id TEXT PRIMARY KEY CHECK (appointment_id ~ '^APPT-[0-9]{6}$'),
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id),
    vehicle_id TEXT NOT NULL REFERENCES public.vehicles(vehicle_id),
    salesperson_id TEXT REFERENCES public.salespeople(salesperson_id),
    appointment_type TEXT NOT NULL CHECK (appointment_type IN ('Test Drive','Consultation','Trade-In Appraisal')),
    starts_at TIMESTAMPTZ NOT NULL, duration_minutes SMALLINT NOT NULL DEFAULT 45
        CHECK (duration_minutes BETWEEN 15 AND 180),
    status TEXT NOT NULL DEFAULT 'Scheduled'
        CHECK (status IN ('Scheduled','Confirmed','Completed','Cancelled','No Show')),
    notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT appointments_unique_slot UNIQUE (salesperson_id, starts_at)
);
CREATE INDEX IF NOT EXISTS idx_appointments_customer_time ON public.appointments (customer_id, starts_at DESC);
CREATE INDEX IF NOT EXISTS idx_appointments_time_status ON public.appointments (starts_at, status);
