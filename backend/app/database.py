"""Supabase client configuration.

The client is created lazily so the API and health endpoint can start before
local Supabase credentials have been configured.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.utils.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set in backend/.env"
        )
    return create_client(settings.supabase_url, settings.supabase_publishable_key)
