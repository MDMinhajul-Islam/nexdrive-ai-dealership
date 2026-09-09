-- Atomic Retell write operations. Run after 01-11.

BEGIN;

-- Cancelled/completed appointments do not occupy a slot. Active slots remain
-- protected by a database uniqueness guarantee during concurrent requests.
ALTER TABLE public.appointments
    DROP CONSTRAINT IF EXISTS appointments_salesperson_slot_uniq;

CREATE UNIQUE INDEX IF NOT EXISTS appointments_active_salesperson_slot_uniq
    ON public.appointments (salesperson_id, appointment_date, appointment_time)
    WHERE status IN ('Requested', 'Confirmed', 'Rescheduled');


CREATE OR REPLACE FUNCTION public.upsert_lead_atomic(p_request JSONB)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_customer_id TEXT := p_request->>'customer_id';
    v_vehicle_id TEXT := p_request->>'vehicle_interest';
    v_salesperson_id TEXT := p_request->>'assigned_salesperson';
    v_lead public.leads%ROWTYPE;
    v_lead_id TEXT;
BEGIN
    IF v_customer_id IS NULL OR v_customer_id !~ '^CUST-[0-9]{6}$' THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_CUSTOMER_ID', 'message', 'Customer ID is invalid');
    END IF;
    IF v_salesperson_id IS NULL OR v_salesperson_id !~ '^SP-[0-9]{3}$' THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_SALESPERSON_ID', 'message', 'Salesperson ID is invalid');
    END IF;
    IF v_vehicle_id IS NOT NULL AND v_vehicle_id !~ '^VEH-[0-9]{6}$' THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_VEHICLE_ID', 'message', 'Vehicle ID is invalid');
    END IF;

    PERFORM 1 FROM public.customers WHERE customer_id = v_customer_id FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'CUSTOMER_NOT_FOUND', 'message', 'Customer not found');
    END IF;
    IF v_vehicle_id IS NOT NULL THEN
        PERFORM 1 FROM public.vehicles WHERE vehicle_id = v_vehicle_id FOR SHARE;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('success', false, 'error_code', 'VEHICLE_NOT_FOUND', 'message', 'Vehicle not found');
        END IF;
    END IF;
    PERFORM 1 FROM public.salespeople
        WHERE salesperson_id = v_salesperson_id AND active = true FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'SALESPERSON_NOT_FOUND', 'message', 'Salesperson is unavailable');
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('nexdrive:lead:' || v_customer_id, 0));
    SELECT * INTO v_lead
    FROM public.leads
    WHERE customer_id = v_customer_id AND lead_status NOT IN ('Won', 'Lost')
    ORDER BY updated_at DESC
    LIMIT 1
    FOR UPDATE;

    IF FOUND THEN
        UPDATE public.leads
        SET source = CASE WHEN p_request ? 'source' THEN p_request->>'source' ELSE source END,
            budget = (p_request->>'budget')::INTEGER,
            vehicle_interest = CASE WHEN p_request ? 'vehicle_interest' THEN v_vehicle_id ELSE vehicle_interest END,
            purchase_timeline = p_request->>'purchase_timeline',
            financing_needed = (p_request->>'financing_needed')::BOOLEAN,
            trade_in = (p_request->>'trade_in')::BOOLEAN,
            lead_score = (p_request->>'lead_score')::SMALLINT,
            lead_temperature = p_request->>'lead_temperature',
            assigned_salesperson = v_salesperson_id,
            notes = CASE
                WHEN NULLIF(BTRIM(p_request->>'notes'), '') IS NULL THEN notes
                ELSE p_request->>'notes'
            END,
            next_followup_date = CURRENT_DATE,
            updated_at = NOW()
        WHERE lead_id = v_lead.lead_id
        RETURNING * INTO v_lead;
        RETURN jsonb_build_object('success', true, 'created', false, 'lead', to_jsonb(v_lead));
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('nexdrive:lead-id', 0));
    SELECT 'LEAD-' || LPAD((COALESCE(MAX(SUBSTRING(lead_id FROM 6)::INTEGER), 0) + 1)::TEXT, 6, '0')
    INTO v_lead_id FROM public.leads;

    INSERT INTO public.leads (
        lead_id, customer_id, source, created_at, lead_status, budget,
        vehicle_interest, purchase_timeline, financing_needed, trade_in,
        lead_score, lead_temperature, assigned_salesperson,
        next_followup_date, notes, updated_at
    ) VALUES (
        v_lead_id, v_customer_id, COALESCE(p_request->>'source', 'Inbound Call'),
        NOW(), 'New', (p_request->>'budget')::INTEGER, v_vehicle_id,
        p_request->>'purchase_timeline', (p_request->>'financing_needed')::BOOLEAN,
        (p_request->>'trade_in')::BOOLEAN, (p_request->>'lead_score')::SMALLINT,
        p_request->>'lead_temperature', v_salesperson_id, CURRENT_DATE,
        COALESCE(p_request->>'notes', ''), NOW()
    ) RETURNING * INTO v_lead;
    RETURN jsonb_build_object('success', true, 'created', true, 'lead', to_jsonb(v_lead));
END;
$$;


CREATE OR REPLACE FUNCTION public.create_test_drive_atomic(p_request JSONB)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_lead_id TEXT := p_request->>'lead_id';
    v_customer_id TEXT := p_request->>'customer_id';
    v_vehicle_id TEXT := p_request->>'vehicle_id';
    v_salesperson_id TEXT := p_request->>'salesperson_id';
    v_date DATE;
    v_time TIME;
    v_lead public.leads%ROWTYPE;
    v_vehicle public.vehicles%ROWTYPE;
    v_person public.salespeople%ROWTYPE;
    v_existing public.appointments%ROWTYPE;
    v_created public.appointments%ROWTYPE;
    v_appointment_id TEXT;
    v_constraint TEXT;
BEGIN
    IF v_lead_id IS NULL OR v_lead_id !~ '^LEAD-[0-9]{6}$'
       OR v_customer_id IS NULL OR v_customer_id !~ '^CUST-[0-9]{6}$'
       OR v_vehicle_id IS NULL OR v_vehicle_id !~ '^VEH-[0-9]{6}$'
       OR v_salesperson_id IS NULL OR v_salesperson_id !~ '^SP-[0-9]{3}$' THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_BOOKING_REFERENCE', 'message', 'One or more booking IDs are invalid');
    END IF;

    BEGIN
        v_date := (p_request->>'appointment_date')::DATE;
        v_time := (p_request->>'appointment_time')::TIME;
    EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_APPOINTMENT_TIME', 'message', 'Appointment date or time is invalid');
    END;
    IF v_date IS NULL OR v_time IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_APPOINTMENT_TIME', 'message', 'Appointment date and time are required');
    END IF;
    IF v_date IS NULL OR v_time IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_APPOINTMENT_TIME', 'message', 'Appointment date and time are required');
    END IF;
    IF v_date < CURRENT_DATE THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'PAST_APPOINTMENT_DATE', 'message', 'Appointment date cannot be in the past');
    END IF;
    IF EXTRACT(MINUTE FROM v_time)::INTEGER NOT IN (0, 30)
       OR EXTRACT(SECOND FROM v_time) <> 0 THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'INVALID_APPOINTMENT_TIME', 'message', 'Appointment time must use a 30-minute increment');
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('nexdrive:appointment:lead:' || v_lead_id, 0));
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'nexdrive:appointment:slot:' || v_salesperson_id || ':' || v_date::TEXT || ':' || v_time::TEXT,
        0
    ));

    SELECT * INTO v_existing FROM public.appointments
    WHERE lead_id = v_lead_id LIMIT 1 FOR UPDATE;
    IF FOUND THEN
        IF v_existing.appointment_type = 'Test Drive'
           AND v_existing.status IN ('Requested', 'Confirmed', 'Rescheduled')
           AND v_existing.appointment_date >= CURRENT_DATE
           AND v_existing.customer_id = v_customer_id
           AND v_existing.vehicle_id = v_vehicle_id
           AND v_existing.salesperson_id = v_salesperson_id
           AND v_existing.appointment_date = v_date
           AND v_existing.appointment_time = v_time THEN
            RETURN jsonb_build_object('success', true, 'created', false, 'appointment', to_jsonb(v_existing));
        END IF;
        RETURN jsonb_build_object(
            'success', false,
            'error_code', 'EXISTING_APPOINTMENT_CONFLICT',
            'message', 'This lead already has a different appointment',
            'existing_appointment', to_jsonb(v_existing)
        );
    END IF;

    SELECT * INTO v_lead FROM public.leads WHERE lead_id = v_lead_id FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'LEAD_NOT_FOUND', 'message', 'Lead not found');
    END IF;
    IF v_lead.customer_id <> v_customer_id THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'LEAD_CUSTOMER_MISMATCH', 'message', 'Lead does not belong to customer');
    END IF;
    PERFORM 1 FROM public.customers WHERE customer_id = v_customer_id FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'CUSTOMER_NOT_FOUND', 'message', 'Customer not found');
    END IF;
    SELECT * INTO v_vehicle FROM public.vehicles WHERE vehicle_id = v_vehicle_id FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'VEHICLE_NOT_FOUND', 'message', 'Vehicle not found');
    END IF;
    IF v_vehicle.vehicle_status NOT IN ('Available', 'Demo Vehicle')
       OR NOT v_vehicle.test_drive_available THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'VEHICLE_NOT_AVAILABLE_FOR_TEST_DRIVE', 'message', 'This vehicle is not currently available for a test drive');
    END IF;
    SELECT * INTO v_person FROM public.salespeople
    WHERE salesperson_id = v_salesperson_id FOR SHARE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'SALESPERSON_NOT_FOUND', 'message', 'Salesperson not found');
    END IF;
    IF NOT v_person.active THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'SALESPERSON_UNAVAILABLE', 'message', 'Salesperson is unavailable');
    END IF;
    IF NOT (TO_CHAR(v_date, 'FMDay') = ANY(v_person.working_days))
       OR NOT (v_person.shift_start <= v_time AND v_time < v_person.shift_end) THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'OUTSIDE_SALESPERSON_SHIFT', 'message', 'Requested time is outside the salesperson shift');
    END IF;
    PERFORM 1 FROM public.appointments
    WHERE salesperson_id = v_salesperson_id
      AND appointment_date = v_date
      AND appointment_time = v_time
      AND status IN ('Requested', 'Confirmed', 'Rescheduled')
    LIMIT 1 FOR UPDATE;
    IF FOUND THEN
        RETURN jsonb_build_object('success', false, 'error_code', 'APPOINTMENT_SLOT_UNAVAILABLE', 'message', 'The requested appointment time is no longer available');
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('nexdrive:appointment-id', 0));
    SELECT 'APT-' || LPAD((COALESCE(MAX(SUBSTRING(appointment_id FROM 5)::INTEGER), 0) + 1)::TEXT, 6, '0')
    INTO v_appointment_id FROM public.appointments;
    BEGIN
        INSERT INTO public.appointments (
            appointment_id, lead_id, customer_id, vehicle_id, salesperson_id,
            appointment_date, appointment_time, appointment_type, status,
            created_by, notes, created_at, updated_at
        ) VALUES (
            v_appointment_id, v_lead_id, v_customer_id, v_vehicle_id,
            v_salesperson_id, v_date, v_time, 'Test Drive', 'Confirmed',
            'Voice Agent', COALESCE(p_request->>'notes', ''), NOW(), NOW()
        ) RETURNING * INTO v_created;
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'appointments_active_salesperson_slot_uniq' THEN
            RETURN jsonb_build_object('success', false, 'error_code', 'APPOINTMENT_SLOT_UNAVAILABLE', 'message', 'The requested appointment time is no longer available');
        END IF;
        RETURN jsonb_build_object('success', false, 'error_code', 'EXISTING_APPOINTMENT_CONFLICT', 'message', 'This lead already has a different appointment');
    END;
    RETURN jsonb_build_object('success', true, 'created', true, 'appointment', to_jsonb(v_created));
END;
$$;

REVOKE ALL ON FUNCTION public.upsert_lead_atomic(JSONB) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.create_test_drive_atomic(JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.upsert_lead_atomic(JSONB) TO service_role;
GRANT EXECUTE ON FUNCTION public.create_test_drive_atomic(JSONB) TO service_role;

COMMIT;
