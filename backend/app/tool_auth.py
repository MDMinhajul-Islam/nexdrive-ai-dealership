"""Authentication and identity binding for Retell tool requests."""

import logging
import secrets

from fastapi import Request, Security, status
from fastapi.security import APIKeyHeader

from app.utils.config import get_settings
from app.utils.tool_errors import ToolAPIError

logger = logging.getLogger("nexdrive.security")
tool_key_header = APIKeyHeader(name="X-Retell-Tool-Key", auto_error=False)


def require_retell_tool_auth(
    request: Request,
    supplied_key: str | None = Security(tool_key_header),
) -> None:
    """Require the server-to-server key configured in Retell and the backend."""
    configured_key = get_settings().retell_tool_api_key
    if not configured_key:
        logger.error("tool_auth_rejected path=%s reason=server_not_configured", request.url.path)
        raise ToolAPIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TOOL_AUTH_UNAVAILABLE",
            False,
            "Tool authentication is temporarily unavailable",
        )
    if not supplied_key or not secrets.compare_digest(supplied_key, configured_key):
        logger.warning("tool_auth_rejected path=%s reason=invalid_credentials", request.url.path)
        raise ToolAPIError(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            False,
            "Retell tool authentication required",
        )


def require_verified_customer_identity(
    requested_customer_id: str,
    verified_customer_id: str | None,
) -> None:
    """Bind history access to the customer identity verified by the trusted caller."""
    if not verified_customer_id or not secrets.compare_digest(
        requested_customer_id, verified_customer_id
    ):
        logger.warning("customer_history_rejected reason=identity_not_verified")
        raise ToolAPIError(
            status.HTTP_403_FORBIDDEN,
            "CUSTOMER_IDENTITY_NOT_VERIFIED",
            False,
            "Customer identity verification is required for history access",
        )
