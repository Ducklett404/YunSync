import json

from redis.exceptions import RedisError

from app.integrations.cache import OptionalCache


class WorkingRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, _ttl: int, value: str):
        self.values[key] = value

    def delete(self, key: str):
        self.values.pop(key, None)

    def ping(self):
        return True


class FailingRedis:
    def get(self, _key: str):
        raise RedisError("synthetic outage")

    def setex(self, _key: str, _ttl: int, _value: str):
        raise RedisError("synthetic outage")

    def delete(self, _key: str):
        raise RedisError("synthetic outage")

    def ping(self):
        raise RedisError("synthetic outage")


def test_enabled_cache_uses_redis_and_namespaced_json():
    redis = WorkingRedis()
    cache = OptionalCache(enabled=True, client=redis)
    key = cache.make_key("action", "one")

    cache.set_json(key, {"title": "合成行动"}, ttl_seconds=60)

    assert key == "yunsync:action:one"
    assert json.loads(redis.values[key]) == {"title": "合成行动"}
    assert cache.get_json(key) == {"title": "合成行动"}
    assert cache.health().backend == "redis"
    assert cache.health().degraded is False


def test_redis_outage_falls_back_to_expiring_memory_without_failing():
    now = [100.0]
    cache = OptionalCache(enabled=True, client=FailingRedis(), clock=lambda: now[0])
    key = cache.make_key("action", "fallback")

    cache.set_json(key, {"safe": True}, ttl_seconds=10)
    assert cache.get_json(key) == {"safe": True}
    assert cache.health().backend == "memory_fallback"
    assert cache.health().degraded is True

    now[0] = 111.0
    assert cache.get_json(key) is None


def test_disabled_cache_uses_local_ttl_store_and_reports_not_degraded():
    cache = OptionalCache(enabled=False, clock=lambda: 20.0)
    key = cache.make_key("local", "value")

    cache.set_json(key, [1, 2, 3], ttl_seconds=30)

    assert cache.get_json(key) == [1, 2, 3]
    assert cache.health().backend == "disabled"
    assert cache.health().degraded is False
