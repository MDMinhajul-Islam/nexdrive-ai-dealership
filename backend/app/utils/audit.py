"""PII-safe structured request logging."""

import json
import logging
import time
import uuid
from fastapi import Request

audit_logger = logging.getLogger("nexdrive.audit")
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)


async def audit_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    audit_logger.info(json.dumps({
        "event": "api_request", "request_id": request_id, "method": request.method,
        "path": request.url.path, "status": response.status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }))
    response.headers["X-Request-ID"] = request_id
    return response
