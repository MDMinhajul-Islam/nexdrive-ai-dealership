"""Voice-agent operational outcomes missing from the initial tool set."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.database import get_supabase
from app.schemas.operations import ConversationOutcomeRequest, EscalationRequest, TradeInCaptureRequest
from app.services.business_tools import _next_id

router = APIRouter(prefix="/api/tools", tags=["Business Tools"])


@router.post("/capture-trade-in")
def capture_trade_in(body: TradeInCaptureRequest, db: Client = Depends(get_supabase)):
    try:
        existing = db.table("trade_ins").select("*").eq("lead_id", body.lead_id).limit(1).execute().data
        age = max(0, 2024 - body.year)
        factor = {"Excellent": 1.05, "Good": .92, "Fair": .76, "Poor": .58}[body.condition]
        estimate = max(1500, min(100000, round((42000 - age * 1900 - body.mileage * .08) * factor)))
        payload = body.model_dump() | {"estimated_value": estimate, "notes": "Synthetic preliminary estimate only; final value requires an in-person appraisal.", "updated_at": datetime.now(timezone.utc).isoformat()}
        if existing:
            record = db.table("trade_ins").update(payload).eq("lead_id", body.lead_id).execute().data[0]
            created = False
        else:
            # trade-in IDs use five digits, unlike the generic six-digit helper.
            generic_id = _next_id(db, "trade_ins", "trade_in_id", "TRD")
            payload["trade_in_id"] = f"TRD-{int(generic_id.split('-')[1]):05d}"
            record = db.table("trade_ins").insert(payload).execute().data[0]
            created = True
        return {"success": True, "source": "database", "created": created, "trade_in": record, "disclaimer": record["notes"]}
    except Exception: raise HTTPException(503, "Trade-in capture failed; no appraisal was recorded") from None


@router.post("/escalate-to-human")
def escalate(body: EscalationRequest, db: Client = Depends(get_supabase)):
    try:
        session = db.table("conversation_sessions").select("session_id").eq("session_id", body.session_id).limit(1).execute().data
        if not session:
            now = datetime.now(timezone.utc).isoformat()
            db.table("conversation_sessions").insert({"session_id": body.session_id, "channel": "Phone", "status": "Escalated", "outcome": "Escalated", "customer_id": body.customer_id, "summary": body.summary, "started_at": now, "ended_at": now}).execute()
        existing = db.table("escalation_events").select("*").eq("session_id", body.session_id).eq("resolved", False).limit(1).execute().data
        if existing: return {"success": True, "source": "database", "created": False, "escalation": existing[0]}
        payload = body.model_dump() | {"escalation_id": _next_id(db, "escalation_events", "escalation_id", "ESC"), "resolved": False}
        record = db.table("escalation_events").insert(payload).execute().data[0]
        return {"success": True, "source": "database", "created": True, "escalation": record}
    except Exception: raise HTTPException(503, "Escalation could not be recorded; advise the caller to contact the dealership directly") from None


@router.post("/record-conversation-outcome")
def record_outcome(body: ConversationOutcomeRequest, db: Client = Depends(get_supabase)):
    try:
        payload = body.model_dump(mode="json") | {"ended_at": datetime.now(timezone.utc).isoformat()}
        existing = db.table("conversation_sessions").select("session_id").eq("session_id", body.session_id).limit(1).execute().data
        query = db.table("conversation_sessions").update(payload).eq("session_id", body.session_id) if existing else db.table("conversation_sessions").insert(payload)
        record = query.execute().data[0]
        return {"success": True, "source": "database", "created": not bool(existing), "session": record}
    except Exception: raise HTTPException(503, "Conversation outcome was not recorded") from None
