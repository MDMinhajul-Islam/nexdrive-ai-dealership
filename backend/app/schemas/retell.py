"""Request and response contracts for the Retell Web SDK bridge."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetellWebCallRequest(BaseModel):
    """Trusted website inputs used to create a Retell web call."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^CUST-[0-9]{6}$")
    assigned_salesperson: str = Field(pattern=r"^SP-[0-9]{3}$")


class RetellWebCallResponse(BaseModel):
    """Minimal Retell Web SDK bootstrap data returned to the frontend."""

    success: Literal[True] = True
    access_token: str
    call_id: str
