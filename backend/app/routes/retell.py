"""Frontend-safe Retell Web SDK endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.retell import RetellWebCallRequest, RetellWebCallResponse
from app.services.retell import (
    RetellConfigurationError,
    RetellInvalidResponseError,
    RetellUnavailableError,
    RetellUpstreamRequestError,
    create_web_call,
)


router = APIRouter(prefix="/api/retell", tags=["Retell"])


@router.post("/create-web-call", response_model=RetellWebCallResponse)
async def create_retell_web_call(
    request: RetellWebCallRequest,
) -> RetellWebCallResponse:
    """Create a temporary web-call token using server-owned credentials."""

    try:
        return await create_web_call(request)
    except RetellConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retell service is not configured",
        ) from None
    except RetellUpstreamRequestError as exc:
        detail = {"message": "Retell rejected the web call request."}
        if exc.upstream_status is not None:
            detail["upstream_status"] = exc.upstream_status
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from None
    except RetellUnavailableError as exc:
        detail: str | dict[str, str | int] = "Retell service unavailable"
        if exc.upstream_status is not None:
            detail = {
                "message": "Retell service unavailable.",
                "upstream_status": exc.upstream_status,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        ) from None
    except RetellInvalidResponseError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Retell returned an invalid response",
        ) from None
