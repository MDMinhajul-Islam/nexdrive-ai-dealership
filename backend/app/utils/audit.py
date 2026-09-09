"""PII-safe structured request logging."""

import json
import logging
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


async def audit_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    event = {
        "event": "api_request", "request_id": request_id, "method": request.method,
        "path": request.url.path, "status": response.status_code,
        "received_at": received_at, "duration_ms": duration_ms,
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
    audit_logger.info(json.dumps(event))
    response.headers["X-Request-ID"] = request_id
    return response
