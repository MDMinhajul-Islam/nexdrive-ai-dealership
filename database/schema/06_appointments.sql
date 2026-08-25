-- NexDrive Motors appointment schema (PostgreSQL / Supabase).

CREATE TABLE IF NOT EXISTS public.appointments (
    appointment_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL UNIQUE REFERENCES public.leads(lead_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    vehicle_id TEXT NOT NULL REFERENCES public.vehicles(vehicle_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    salesperson_id TEXT NOT NULL REFERENCES public.salespeople(salesperson_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    appointment_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT appointments_id_format_chk CHECK (appointment_id ~ '^APT-[0-9]{6}$'),
    CONSTRAINT appointments_type_chk CHECK (appointment_type IN (
        'Test Drive', 'Virtual Consultation', 'Financing Consultation', 'Trade-In Appraisal'
    )),
    CONSTRAINT appointments_status_chk CHECK (status IN (
        'Requested', 'Confirmed', 'Completed', 'Cancelled', 'No Show', 'Rescheduled'
    )),
    CONSTRAINT appointments_created_by_chk CHECK (created_by IN (
        'Voice Agent', 'Website', 'Salesperson', 'Customer Service'
    )),
    CONSTRAINT appointments_salesperson_slot_uniq UNIQUE (salesperson_id, appointment_date, appointment_time)
);

CREATE INDEX IF NOT EXISTS idx_appointments_customer ON public.appointments (customer_id);
CREATE INDEX IF NOT EXISTS idx_appointments_vehicle ON public.appointments (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date_status ON public.appointments (appointment_date, status);
