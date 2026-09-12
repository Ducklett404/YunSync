from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import Request
from starlette.responses import Response

from app.core.config import settings


CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "connect-src 'self'",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "img-src 'self' data:",
        "object-src 'none'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
    )
)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Process-local guard; a gateway or DCS-backed limiter is still required at scale."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        max_clients: int,
        clock: Callable[[], float] = monotonic,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._clock = clock
        self._buckets: dict[str, deque[float]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            if key not in self._buckets and len(self._buckets) >= self.max_clients:
                oldest_key = min(self._last_seen, key=self._last_seen.get)
                self._buckets.pop(oldest_key, None)
                self._last_seen.pop(oldest_key, None)

            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            allowed = len(bucket) < self.limit
            if allowed:
                bucket.append(now)
            self._last_seen[key] = now

            remaining = max(self.limit - len(bucket), 0)
            retry_after = (
                max(ceil(self.window_seconds - (now - bucket[0])), 1)
                if bucket
                else self.window_seconds
            )
            return RateLimitDecision(
                allowed=allowed,
                limit=self.limit,
                remaining=remaining,
                retry_after_seconds=retry_after,
            )

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._last_seen.clear()


rate_limiter = SlidingWindowRateLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    max_clients=settings.rate_limit_max_clients,
)


def rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:api"


def apply_security_headers(request: Request, response: Response) -> None:
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.url.path.startswith(settings.api_v1_prefix):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
