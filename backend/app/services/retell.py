"""Secure server-side Retell web-call creation."""

import logging
from datetime import date

import httpx

from app.schemas.retell import RetellWebCallRequest, RetellWebCallResponse
from app.utils.config import Settings, get_settings


RETELL_WEB_CALL_URL = "https://api.retellai.com/v2/create-web-call"
RETELL_REQUEST_TIMEOUT_SECONDS = 10.0
MAX_UPSTREAM_DIAGNOSTIC_LENGTH = 200

logger = logging.getLogger(__name__)


class RetellConfigurationError(RuntimeError):
    """Required server-side Retell configuration is missing."""


class RetellUpstreamRequestError(RuntimeError):
    """Retell rejected an otherwise valid backend request."""

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class RetellUnavailableError(RuntimeError):
    """Retell could not be reached or returned a server-side failure."""

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class RetellInvalidResponseError(RuntimeError):
    """Retell returned a response that cannot safely bootstrap the SDK."""


def _safe_diagnostic_value(value: object, api_key: str) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    text = " ".join(str(value).split())[:MAX_UPSTREAM_DIAGNOSTIC_LENGTH]
    if not text:
        return None
    if api_key and api_key in text:
        text = text.replace(api_key, "[redacted]")
    lowered = text.lower()
    if any(marker in lowered for marker in (
        "access_token", "authorization", "bearer ", "retell_api_key"
    )):
        return "[redacted]"
    return text


def _safe_upstream_diagnostics(
    response: httpx.Response, api_key: str
) -> tuple[str | None, str | None]:
    try:
        payload = response.json()
    except ValueError:
        return None, None
    if not isinstance(payload, dict):
        return None, None

    error = payload.get("error")
    nested_error = error if isinstance(error, dict) else {}
    message = (
        payload.get("message")
        or payload.get("error_message")
        or nested_error.get("message")
        or (error if isinstance(error, str) else None)
    )
    code = (
        payload.get("code")
        or payload.get("error_code")
        or nested_error.get("code")
    )
    return (
        _safe_diagnostic_value(message, api_key),
        _safe_diagnostic_value(code, api_key),
    )


def _log_upstream_failure(response: httpx.Response, api_key: str) -> None:
    message, code = _safe_upstream_diagnostics(response, api_key)
    logger.warning(
        "Retell create-web-call upstream failure status=%s code=%s message=%s",
        response.status_code,
        code or "unavailable",
        message or "unavailable",
    )


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

    if not 200 <= response.status_code < 300:
        _log_upstream_failure(response, resolved_settings.retell_api_key)
        if 400 <= response.status_code < 500:
            raise RetellUpstreamRequestError(
                "Retell rejected the web call request", response.status_code
            )
        if response.status_code >= 500:
            raise RetellUnavailableError(
                "Retell service returned an error", response.status_code
            )
        raise RetellUpstreamRequestError(
            "Retell returned an unexpected status", response.status_code
        )

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
