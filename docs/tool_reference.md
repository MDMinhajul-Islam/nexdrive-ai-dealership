# Tool reference

| Tool | Purpose | Write/confirmation |
|---|---|---|
| search_inventory | Filter real available inventory | Read |
| get_vehicle_details | Full vehicle and features | Read |
| check_vehicle_availability | Current eligibility | Read |
| get_customer_history | Related CRM history | Read; verify identity |
| get_test_drive_slots | Schedule minus occupied slots | Read |
| create_or_update_lead | Score and persist active lead | Write; explicit confirmation |
| create_test_drive | Recheck and confirm appointment | Write; explicit confirmation |
| estimate_financing | Rule-backed payment estimate | Read; speak disclaimer |
| capture_trade_in | Persist synthetic trade details and preliminary estimate | Write; explicit confirmation and appraisal disclaimer |
| escalate_to_human | Create a traceable open escalation | Write; customer request or policy trigger |
| record_conversation_outcome | Reconcile the call with lead/booking state | Idempotent write before call end |

Admin inventory, lead and appointment routes are separate from Retell tools.
They require a valid Supabase user token and an email included in
`ADMIN_EMAILS` when production authentication is enabled.
