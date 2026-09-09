import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class OptionalCache:
    def __init__(self) -> None:
        self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        self._memory: dict[str, Any] = {}

    def get_json(self, key: str) -> Any | None:
        try:
            value = self._client.get(key)
            return json.loads(value) if value else None
        except RedisError:
            return self._memory.get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False, default=str))
        except RedisError:
            self._memory[key] = value


cache = OptionalCache()

