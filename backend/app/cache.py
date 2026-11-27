from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from redis import Redis
from redis.exceptions import RedisError

from .config import Settings


@dataclass
class CacheRead:
    value: Any | None
    hit: bool
    backend: str
    degraded: bool


class MemoryTTLStore:
    MAX_VALUE_BYTES = 64 * 1024
    CLEANUP_INTERVAL = 10

    def __init__(
        self,
        now: Callable[[], float] | None = None,
        *,
        max_values: int = 256,
        max_counters: int = 4096,
    ):
        self._now = now or time.monotonic
        self._max_values = max_values
        self._max_counters = max_counters
        self._next_cleanup = float("-inf")
        self._values: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._counters: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def _expire_entries(self, now: float) -> None:
        if now >= self._next_cleanup:
            for store in (self._values, self._counters):
                for key in [key for key, entry in store.items() if entry[0] <= now]:
                    del store[key]
            self._next_cleanup = now + self.CLEANUP_INTERVAL

    def get(self, key: str) -> str | None:
        with self._lock:
            now = self._now()
            self._expire_entries(now)
            record = self._values.get(key)
            if not record:
                return None
            expires_at, value = record
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            self._values.move_to_end(key)
            return value.decode("utf-8")

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        encoded = value.encode("utf-8")
        with self._lock:
            now = self._now()
            self._expire_entries(now)
            self._values.pop(key, None)
            if self._max_values <= 0 or len(encoded) > self.MAX_VALUE_BYTES:
                return
            if len(self._values) >= self._max_values:
                self._values.popitem(last=False)
            self._values[key] = (now + ttl_seconds, encoded)

    def delete(self, key: str) -> None:
        with self._lock:
            self._values.pop(key, None)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        with self._lock:
            now = self._now()
            self._expire_entries(now)
            existing = self._counters.get(key)
            if existing is None and len(self._counters) >= self._max_counters:
                # An active window must not be evicted to admit a new client.
                return False
            expires_at, count = existing or (now + window_seconds, 0)
            if expires_at <= now:
                expires_at, count = now + window_seconds, 0
            if count >= limit:
                return False
            self._counters[key] = (expires_at, count + 1)
            return True


class ResilientCache:
    """DCS Redis adapter with an in-process TTL fallback.

    Redis failures never manufacture a successful dependency state. Calls may use the
    bounded memory fallback, and every response can expose that degraded condition.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        redis_client: Redis | None = None,
        memory: MemoryTTLStore | None = None,
    ):
        self.settings = settings
        self.memory = memory or MemoryTTLStore()
        self.redis = redis_client
        if self.redis is None and settings.redis_url:
            self.redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                health_check_interval=30,
            )
        self.last_error: str | None = None

    def key(self, namespace: str, digest: str) -> str:
        return f"yunsync:{self.settings.cache_version}:{namespace}:{digest}"

    def get_json(self, key: str) -> CacheRead:
        if self.redis is not None:
            try:
                value = self.redis.get(key)
                self.last_error = None
                if value is not None:
                    return CacheRead(json.loads(value), True, "redis", False)
                return CacheRead(None, False, "redis", False)
            except (RedisError, ValueError, TypeError) as exc:
                self.last_error = exc.__class__.__name__
        value = self.memory.get(key)
        return CacheRead(
            json.loads(value) if value is not None else None,
            value is not None,
            "memory",
            True,
        )

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> tuple[str, bool]:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if self.redis is not None:
            try:
                self.redis.setex(key, ttl_seconds, serialized)
                self.last_error = None
                return "redis", False
            except RedisError as exc:
                self.last_error = exc.__class__.__name__
        self.memory.set(key, serialized, ttl_seconds)
        return "memory", True

    def delete(self, key: str) -> None:
        if self.redis is not None:
            try:
                self.redis.delete(key)
                self.last_error = None
            except RedisError as exc:
                self.last_error = exc.__class__.__name__
        self.memory.delete(key)

    def allow(self, identity: str) -> tuple[bool, str, bool]:
        key = self.key("rate", identity)
        if self.redis is not None:
            try:
                count = self.redis.incr(key)
                if count == 1:
                    self.redis.expire(key, self.settings.rate_limit_window_seconds)
                self.last_error = None
                return count <= self.settings.rate_limit_requests, "redis", False
            except RedisError as exc:
                self.last_error = exc.__class__.__name__
        allowed = self.memory.allow(
            key,
            self.settings.rate_limit_requests,
            self.settings.rate_limit_window_seconds,
        )
        return allowed, "memory", True

    def health(self) -> dict[str, Any]:
        if self.redis is None:
            return {
                "status": "degraded",
                "backend": "memory",
                "reason": "redis_not_configured",
            }
        try:
            self.redis.ping()
            self.last_error = None
            return {"status": "ok", "backend": "redis"}
        except RedisError as exc:
            self.last_error = exc.__class__.__name__
            return {
                "status": "degraded",
                "backend": "memory",
                "reason": "redis_unavailable",
            }
