"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.health import router as health_router
from app.routes.customer_tools import router as customer_tools_router
from app.routes.business_tools import router as business_tools_router
from app.routes.admin import router as admin_router
from app.utils.audit import audit_middleware
from app.utils.config import get_settings
from app.routes.inventory_tools import router as inventory_tools_router
from app.routes.vehicles import router as vehicles_router
from app.routes.public import router as public_router
from app.routes.operations import router as operations_router


app = FastAPI(
    title="NexDrive AI Dealership API",
    version="0.1.0",
    description="Backend API for NexDrive dealership workflows.",
)
app.include_router(health_router)
app.middleware("http")(audit_middleware)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in get_settings().cors_origins.split(",") if x.strip()],allow_credentials=False,allow_methods=["GET","POST","PATCH","OPTIONS"],allow_headers=["Content-Type","Authorization","X-Request-ID","Idempotency-Key"])
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(operations_router)
app.include_router(business_tools_router)
app.include_router(customer_tools_router)
app.include_router(vehicles_router)
app.include_router(inventory_tools_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": app.title, "docs": "/docs", "health": "/health"}
