"""Supabase client configuration.

The client is created lazily so the API and health endpoint can start before
local Supabase credentials have been configured.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.utils.config import get_settings


class SupabaseConfigurationError(RuntimeError):
    """Raised when required Supabase environment variables are missing."""


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_PUBLISHABLE_KEY": settings.supabase_publishable_key,
        "SUPABASE_SECRET_KEY": settings.supabase_secret_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SupabaseConfigurationError(
            f"Missing required Supabase configuration: {', '.join(missing)}"
        )

    # Trusted backend operations use the privileged key. This client must never
    # be returned through an API response or imported by frontend code.
    return create_client(settings.supabase_url, settings.supabase_secret_key)
