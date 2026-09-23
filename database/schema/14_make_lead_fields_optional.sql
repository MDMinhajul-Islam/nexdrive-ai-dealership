-- Migration: Make specific lead fields optional for new Retell flow
BEGIN;

ALTER TABLE public.leads
    ALTER COLUMN budget DROP NOT NULL,
    ALTER COLUMN purchase_timeline DROP NOT NULL,
    ALTER COLUMN financing_needed DROP NOT NULL,
    ALTER COLUMN trade_in DROP NOT NULL,
    ALTER COLUMN assigned_salesperson DROP NOT NULL;

COMMIT;

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
    IF v_salesperson_id IS NOT NULL AND v_salesperson_id !~ '^SP-[0-9]{3}$' THEN
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
    IF v_salesperson_id IS NOT NULL THEN
        PERFORM 1 FROM public.salespeople
            WHERE salesperson_id = v_salesperson_id AND active = true FOR SHARE;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('success', false, 'error_code', 'SALESPERSON_NOT_FOUND', 'message', 'Salesperson is unavailable');
        END IF;
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
            budget = CASE WHEN p_request ? 'budget' THEN (p_request->>'budget')::INTEGER ELSE budget END,
            vehicle_interest = CASE WHEN p_request ? 'vehicle_interest' THEN v_vehicle_id ELSE vehicle_interest END,
            purchase_timeline = CASE WHEN p_request ? 'purchase_timeline' THEN p_request->>'purchase_timeline' ELSE purchase_timeline END,
            financing_needed = CASE WHEN p_request ? 'financing_needed' THEN (p_request->>'financing_needed')::BOOLEAN ELSE financing_needed END,
            trade_in = CASE WHEN p_request ? 'trade_in' THEN (p_request->>'trade_in')::BOOLEAN ELSE trade_in END,
            lead_score = CASE WHEN p_request ? 'lead_score' THEN (p_request->>'lead_score')::SMALLINT ELSE lead_score END,
            lead_temperature = CASE WHEN p_request ? 'lead_temperature' THEN p_request->>'lead_temperature' ELSE lead_temperature END,
            assigned_salesperson = CASE WHEN p_request ? 'assigned_salesperson' THEN v_salesperson_id ELSE assigned_salesperson END,
            notes = CASE WHEN p_request ? 'notes' THEN p_request->>'notes' ELSE notes END,
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

