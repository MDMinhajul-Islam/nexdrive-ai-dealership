"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from app.routes.retell import router as retell_router
from app.utils.tool_errors import ToolAPIError


app = FastAPI(
    title="NexDrive AI Dealership API",
    version="0.1.0",
    description="Backend API for NexDrive dealership workflows.",
)


@app.exception_handler(ToolAPIError)
async def tool_api_error_handler(request: Request, exc: ToolAPIError) -> JSONResponse:
    request.state.tool_error_code = exc.error_code
    request.state.error_code = exc.error_code
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.payload(),
        headers=dict(exc.headers or {}),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/tools/create-test-drive":
        request.state.tool_error_code = "INVALID_BOOKING_REQUEST"
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error_code": "INVALID_BOOKING_REQUEST",
                "retryable": False,
                "message": "The booking request contains missing or invalid information",
            },
        )
    if request.url.path == "/api/tools/resolve-customer":
        err_msg = str(exc)
        if "email format" in err_msg.lower() or "email" in err_msg.lower():
            request.state.tool_error_code = "INVALID_EMAIL"
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error_code": "INVALID_EMAIL",
                    "retryable": True,
                    "message": "The provided email address is invalid. Please ask the customer to repeat their email.",
                },
            )
        if "phone" in err_msg.lower():
            request.state.tool_error_code = "INVALID_PHONE"
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error_code": "INVALID_PHONE",
                    "retryable": True,
                    "message": "The provided phone number is invalid. Please ask the customer to repeat their phone number.",
                },
            )
    return await request_validation_exception_handler(request, exc)


app.include_router(health_router)
app.middleware("http")(audit_middleware)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in get_settings().cors_origins.split(",") if x.strip()],allow_credentials=False,allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"],allow_headers=["Content-Type","Authorization","X-Request-ID","X-Session-ID","Idempotency-Key"])
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(operations_router)
app.include_router(business_tools_router)
app.include_router(customer_tools_router)
app.include_router(vehicles_router)
app.include_router(inventory_tools_router)
app.include_router(retell_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": app.title, "docs": "/docs", "health": "/health"}
