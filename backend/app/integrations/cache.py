from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


@dataclass(frozen=True)
class CacheHealth:
    backend: str
    degraded: bool


@dataclass
class _MemoryEntry:
    value: Any
    expires_at: float


class OptionalCache:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.enabled = settings.cache_enabled if enabled is None else enabled
        self._clock = clock
        self._memory: dict[str, _MemoryEntry] = {}
        self._lock = threading.Lock()
        self._client = client
        if self.enabled and self._client is None:
            self._client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.cache_connect_timeout_seconds,
                socket_timeout=settings.cache_socket_timeout_seconds,
                health_check_interval=30,
            )

    def make_key(self, *parts: str) -> str:
        return ":".join((settings.cache_namespace, *parts))

    def get_json(self, key: str) -> Any | None:
        if self.enabled and self._client is not None:
            try:
                value = self._client.get(key)
                if value is not None:
                    return json.loads(value)
            except (RedisError, json.JSONDecodeError, TypeError):
                pass
        return self._memory_get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or settings.cache_ttl_seconds
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        redis_saved = False
        if self.enabled and self._client is not None:
            try:
                self._client.setex(key, ttl, serialized)
                redis_saved = True
            except RedisError:
                pass
        if not redis_saved:
            with self._lock:
                self._memory[key] = _MemoryEntry(
                    value=value,
                    expires_at=self._clock() + ttl,
                )

    def delete(self, key: str) -> None:
        if self.enabled and self._client is not None:
            try:
                self._client.delete(key)
            except RedisError:
                pass
        with self._lock:
            self._memory.pop(key, None)

    def health(self) -> CacheHealth:
        if not self.enabled:
            return CacheHealth(backend="disabled", degraded=False)
        if self._client is not None:
            try:
                if self._client.ping():
                    return CacheHealth(backend="redis", degraded=False)
            except RedisError:
                pass
        return CacheHealth(backend="memory_fallback", degraded=True)

    def _memory_get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._memory.get(key)
            if entry is None:
                return None
            if entry.expires_at <= self._clock():
                self._memory.pop(key, None)
                return None
            return entry.value


cache = OptionalCache()
