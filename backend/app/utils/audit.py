"""PII-safe structured request logging."""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from fastapi import Request

audit_logger = logging.getLogger("nexdrive.audit")
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)
SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _safe_correlation_id(value: str | None) -> str | None:
    if value and SAFE_CORRELATION_ID.fullmatch(value):
        return value
    return None


async def audit_middleware(request: Request, call_next):
    request_id = _safe_correlation_id(request.headers.get("X-Request-ID"))
    request_id = request_id or str(uuid.uuid4())
    request.state.request_id = request_id
    received_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_logger.error(json.dumps({
            "event": "api_request_failed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "received_at": received_at,
            "duration_ms": duration_ms,
            "success": False,
            "error_code": "UNEXPECTED_ERROR",
        }))
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    completed_at = datetime.now(timezone.utc).isoformat()
    event = {
        "event": "api_request", "request_id": request_id, "method": request.method,
        "path": request.url.path, "status": response.status_code,
        "received_at": received_at, "completed_at": completed_at,
        "duration_ms": duration_ms,
    }
    if request.url.path.startswith("/api/tools/"):
        tool_name = request.url.path.removeprefix("/api/tools/").split("/", 1)[0]
        event.update({
            "event": "retell_tool_request",
            "tool_name": tool_name.replace("-", "_"),
            "success": response.status_code < 400,
            "error_code": getattr(
                request.state,
                "tool_error_code",
                None if response.status_code < 400 else f"HTTP_{response.status_code}",
            ),
        })
        retell_call_id = _safe_correlation_id(
            request.headers.get("X-Retell-Call-ID")
        )
        if retell_call_id:
            event["retell_call_id"] = retell_call_id
    elif request.url.path == "/api/retell/create-web-call":
        event.update({
            "event": "retell_web_call_request",
            "success": response.status_code < 400,
            "error_code": getattr(
                request.state,
                "error_code",
                None if response.status_code < 400 else f"HTTP_{response.status_code}",
            ),
        })
        retell_call_id = _safe_correlation_id(
            getattr(request.state, "retell_call_id", None)
        )
        if retell_call_id:
            event["retell_call_id"] = retell_call_id
    audit_logger.info(json.dumps(event))
    response.headers["X-Request-ID"] = request_id
    return response
