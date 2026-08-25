"""Supabase reads used by customer-history and scheduling tools."""

from datetime import date
from typing import Any, Protocol


class CustomerToolsRepositoryError(RuntimeError):
    pass


class CustomerToolsRepository(Protocol):
    def customer_history(self, customer_id: str) -> dict[str, Any] | None: ...
    def salespeople(self, salesperson_id: str | None = None) -> list[dict[str, Any]]: ...
    def appointments_between(self, start: date, end: date) -> list[dict[str, Any]]: ...


class SupabaseCustomerToolsRepository:
    def __init__(self, client: Any):
        self.client = client

    def customer_history(self, customer_id: str) -> dict[str, Any] | None:
        try:
            customer = self.client.table("customers").select("*").eq("customer_id", customer_id).limit(1).execute()
            if not customer.data:
                return None
            leads = self.client.table("leads").select("*").eq("customer_id", customer_id).order("created_at", desc=True).execute()
            appointments = self.client.table("appointments").select("*").eq("customer_id", customer_id).order("appointment_date", desc=True).execute()
            return {"customer": customer.data[0], "leads": leads.data or [], "appointments": appointments.data or []}
        except Exception as exc:
            raise CustomerToolsRepositoryError("Customer history lookup failed") from exc

    def salespeople(self, salesperson_id: str | None = None) -> list[dict[str, Any]]:
        try:
            query = self.client.table("salespeople").select("salesperson_id,name,working_days,shift_start,shift_end,active").eq("active", True)
            if salesperson_id:
                query = query.eq("salesperson_id", salesperson_id)
            return query.order("salesperson_id").execute().data or []
        except Exception as exc:
            raise CustomerToolsRepositoryError("Salesperson schedule lookup failed") from exc

    def appointments_between(self, start: date, end: date) -> list[dict[str, Any]]:
        try:
            return (
                self.client.table("appointments")
                .select("salesperson_id,appointment_date,appointment_time,status")
                .gte("appointment_date", start.isoformat()).lte("appointment_date", end.isoformat())
                .in_("status", ["Requested", "Confirmed", "Rescheduled"])
                .execute().data or []
            )
        except Exception as exc:
            raise CustomerToolsRepositoryError("Appointment schedule lookup failed") from exc
