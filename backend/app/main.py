"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.customer_tools import router as customer_tools_router
from app.routes.inventory_tools import router as inventory_tools_router
from app.routes.vehicles import router as vehicles_router


app = FastAPI(
    title="NexDrive AI Dealership API",
    version="0.1.0",
    description="Backend API for NexDrive dealership workflows.",
)
app.include_router(health_router)
app.include_router(customer_tools_router)
app.include_router(vehicles_router)
app.include_router(inventory_tools_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": app.title, "docs": "/docs", "health": "/health"}
