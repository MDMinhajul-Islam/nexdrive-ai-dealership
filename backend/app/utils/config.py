"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "NexDrive API"
    app_env: str = "development"
    supabase_url: str = ""
    # Public/client-safe key used for requests subject to Supabase RLS policies.
    supabase_publishable_key: str = ""
    # Backend-only privileged key; never return this from an API response.
    supabase_secret_key: str = ""
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
