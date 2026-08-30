"""Secure server-side Retell web-call creation."""

from datetime import date

import httpx

from app.schemas.retell import RetellWebCallRequest, RetellWebCallResponse
from app.utils.config import Settings, get_settings


RETELL_WEB_CALL_URL = "https://api.retellai.com/v2/create-web-call"
RETELL_REQUEST_TIMEOUT_SECONDS = 10.0


class RetellConfigurationError(RuntimeError):
    """Required server-side Retell configuration is missing."""


class RetellUpstreamRequestError(RuntimeError):
    """Retell rejected an otherwise valid backend request."""


class RetellUnavailableError(RuntimeError):
    """Retell could not be reached or returned a server-side failure."""


class RetellInvalidResponseError(RuntimeError):
    """Retell returned a response that cannot safely bootstrap the SDK."""


async def create_web_call(
    request: RetellWebCallRequest,
    *,
    settings: Settings | None = None,
    current_date: date | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RetellWebCallResponse:
    """Create a Retell web call without exposing trusted configuration."""

    resolved_settings = settings or get_settings()
    if not resolved_settings.retell_api_key.strip():
        raise RetellConfigurationError("RETELL_API_KEY is not configured")
    if not resolved_settings.retell_agent_id.strip():
        raise RetellConfigurationError("RETELL_AGENT_ID is not configured")

    payload = {
        "agent_id": resolved_settings.retell_agent_id,
        "retell_llm_dynamic_variables": {
            "customer_id": request.customer_id,
            "assigned_salesperson": request.assigned_salesperson,
            "current_date": (current_date or date.today()).isoformat(),
        },
    }
    headers = {
        "Authorization": f"Bearer {resolved_settings.retell_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=RETELL_REQUEST_TIMEOUT_SECONDS,
            transport=transport,
        ) as client:
            response = await client.post(
                RETELL_WEB_CALL_URL,
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException:
        raise RetellUnavailableError("Retell request timed out") from None
    except httpx.RequestError:
        raise RetellUnavailableError("Retell network request failed") from None

    if 400 <= response.status_code < 500:
        raise RetellUpstreamRequestError("Retell rejected the web call request")
    if response.status_code >= 500:
        raise RetellUnavailableError("Retell service returned an error")

    try:
        response_data = response.json()
    except ValueError:
        raise RetellInvalidResponseError("Retell returned invalid JSON") from None
    if not isinstance(response_data, dict):
        raise RetellInvalidResponseError("Retell returned invalid JSON")

    access_token = response_data.get("access_token")
    call_id = response_data.get("call_id")
    if not isinstance(access_token, str) or not access_token:
        raise RetellInvalidResponseError("Retell response omitted access_token")
    if not isinstance(call_id, str) or not call_id:
        raise RetellInvalidResponseError("Retell response omitted call_id")

    return RetellWebCallResponse(access_token=access_token, call_id=call_id)
