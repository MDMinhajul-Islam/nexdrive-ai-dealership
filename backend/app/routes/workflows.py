"""Lead, booking, customer-history, and financing endpoints."""

from fastapi import APIRouter, Header, Response

from app.schemas.workflows import AppointmentInput, FinancingInput, LeadInput, LeadUpdate
from app.services.workflows import workflow_service

router = APIRouter(prefix="/api/v1", tags=["dealership workflows"])


@router.post("/leads", status_code=201)
def create_lead(payload: LeadInput, response: Response, idempotency_key: str | None = Header(None)) -> dict:
    result, replayed = workflow_service.create_lead(payload.model_dump(), idempotency_key)
    if replayed: response.status_code = 200; response.headers["Idempotent-Replayed"] = "true"
    return result


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: str, payload: LeadUpdate) -> dict:
    return workflow_service.update_lead(lead_id, payload.model_dump(exclude_unset=True))


@router.post("/appointments", status_code=201)
def create_appointment(payload: AppointmentInput, response: Response, idempotency_key: str | None = Header(None)) -> dict:
    result, replayed = workflow_service.create_appointment(payload.model_dump(), idempotency_key)
    if replayed: response.status_code = 200; response.headers["Idempotent-Replayed"] = "true"
    return result


@router.get("/customers/{customer_id}/history")
def customer_history(customer_id: str) -> dict:
    return workflow_service.history(customer_id)


@router.post("/financing/estimate")
def financing_estimate(payload: FinancingInput) -> dict:
    return workflow_service.financing(payload.model_dump())
