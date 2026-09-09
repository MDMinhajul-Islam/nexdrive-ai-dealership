"""Bounded in-process abuse protection for Retell web-call creation."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import Request, status

from app.utils.config import get_settings
from app.utils.tool_errors import ToolAPIError

logger = logging.getLogger("nexdrive.security")
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
MAX_TRACKED_IDENTIFIERS = 10_000


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class SlidingWindowRateLimiter:
    """Thread-safe limiter with bounded, expiring identifier storage."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(kind: str, identifier: str) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return f"{kind}:{digest}"

    def check(
        self,
        *,
        ip_address: str,
        session_id: str | None,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - window_seconds
        keys_and_limits = [
            (self._key("ip", ip_address), limit * 10 if session_id else limit)
        ]
        if session_id:
            keys_and_limits.append((self._key("session", session_id), limit))

        with self._lock:
            if len(self._requests) >= MAX_TRACKED_IDENTIFIERS:
                self._requests = {
                    key: timestamps
                    for key, timestamps in self._requests.items()
                    if timestamps and timestamps[-1] > cutoff
                }
                new_key_count = sum(
                    key not in self._requests for key, _ in keys_and_limits
                )
                if len(self._requests) + new_key_count > MAX_TRACKED_IDENTIFIERS:
                    return RateLimitDecision(False, window_seconds)

            retry_after = 0
            for key, key_limit in keys_and_limits:
                timestamps = self._requests.setdefault(key, deque())
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if len(timestamps) >= key_limit:
                    retry_after = max(
                        retry_after,
                        max(1, math.ceil(window_seconds - (now - timestamps[0]))),
                    )

            if retry_after:
                return RateLimitDecision(False, retry_after)
            for key, _ in keys_and_limits:
                self._requests[key].append(now)
            return RateLimitDecision(True)

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


web_call_rate_limiter = SlidingWindowRateLimiter()


def _safe_session_identifier(request: Request) -> str | None:
    candidate = request.headers.get("X-Session-ID") or request.cookies.get("session_id")
    if candidate and SESSION_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def enforce_web_call_rate_limit(request: Request) -> None:
    settings = get_settings()
    ip_address = request.client.host if request.client else "unknown"
    decision = web_call_rate_limiter.check(
        ip_address=ip_address,
        session_id=_safe_session_identifier(request),
        limit=settings.retell_web_call_rate_limit_requests,
        window_seconds=settings.retell_web_call_rate_limit_window_seconds,
    )
    if decision.allowed:
        return

    request.state.error_code = "RATE_LIMITED"
    logger.warning(json.dumps({
        "event": "retell_web_call_rate_limited",
        "path": request.url.path,
        "retry_after": decision.retry_after,
        "error_code": "RATE_LIMITED",
    }))
    raise ToolAPIError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "RATE_LIMITED",
        True,
        "Too many requests. Please try again later.",
        headers={"Retry-After": str(decision.retry_after)},
    )
