"""FastAPI application entry point."""

import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.routes.health import router as health_router
from app.routes.workflows import router as workflows_router


app = FastAPI(
    title="NexDrive AI Dealership API",
    version="0.1.0",
    description="Backend API for NexDrive dealership workflows.",
)
app.include_router(health_router)
app.include_router(workflows_router)

logger = logging.getLogger("nexdrive.requests")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_complete method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
                request.method, request.url.path, response.status_code,
                (time.perf_counter() - started) * 1000, request_id)
    return response


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": app.title, "docs": "/docs", "health": "/health"}
