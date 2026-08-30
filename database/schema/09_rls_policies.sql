-- NexDrive API security boundary. Run after 01-08.
-- Public clients receive no direct table access; the trusted backend uses service_role.
DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'vehicles','features','vehicle_features','customers','salespeople',
    'leads','appointments','trade_ins','financing_options'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', table_name);
  END LOOP;
END $$;

-- service_role bypasses RLS in Supabase. Never expose its key to browsers or Retell.
