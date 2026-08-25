"""System endpoint schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["connected"] = "connected"
    source: Literal["supabase"] = "supabase"
