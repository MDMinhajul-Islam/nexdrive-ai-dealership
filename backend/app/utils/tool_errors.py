"""Safe, machine-readable errors for Retell-facing tool endpoints."""

from dataclasses import dataclass


@dataclass(slots=True)
class ToolAPIError(Exception):
    status_code: int
    error_code: str
    retryable: bool
    message: str

    def payload(self) -> dict[str, str | bool]:
        return {
            "success": False,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "message": self.message,
        }
