# Client demo scenarios

The automated catalog is `backend/tests/e2e_scenarios.json` (24 scenarios). Demo sequence:

1. Ask for a used AWD SUV under $30,000 with Apple CarPlay.
2. Compare up to three returned records and ask for details on one.
3. Recheck availability, capture the customer lead after confirmation, and show the Supabase lead.
4. Discover a slot, confirm the exact date/time, book it, then show the Supabase appointment.
5. Retry the booking to demonstrate idempotency.
6. Request a 60-month financing estimate and read the lender-approval disclaimer.
7. Open the dashboard to show traceable inventory, lead, appointment and customer history outcomes.
