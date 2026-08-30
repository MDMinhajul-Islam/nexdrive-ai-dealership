"""Supabase-authenticated admin boundary.

Development keeps authentication optional so tests and local CSV workflows remain
simple. Production should set ADMIN_AUTH_REQUIRED=true and ADMIN_EMAILS.
"""

from typing import Any

import httpx
from fastapi import Header, HTTPException

from app.utils.config import get_settings


def require_admin(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.admin_auth_required:
        return {"email": "local-admin@nexdrive.demo", "role": "admin", "mode": "development"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            timeout=8,
        )
        response.raise_for_status()
        user = response.json()
    except Exception:
        raise HTTPException(401, "Invalid or expired admin session") from None
    allowed = {email.strip().lower() for email in settings.admin_emails.split(",") if email.strip()}
    email = str(user.get("email", "")).lower()
    if not allowed or email not in allowed:
        raise HTTPException(403, "This account is not authorized for NexDrive administration")
    return {"id": user.get("id"), "email": email, "role": "admin"}
