from app.cache import MemoryTTLStore


def test_fallback_caps_values_and_reclaims_expired_entries():
    clock = [0.0]
    cache = MemoryTTLStore(now=lambda: clock[0], max_values=2)
    cache.set("recent", "one", 60)
    cache.set("old", "two", 60)
    assert cache.get("recent") == "one"

    cache.set("new", "three", 5)
    cache.set("oversize", "多" * MemoryTTLStore.MAX_VALUE_BYTES, 60)
    assert cache.get("old") is None
    assert cache.get("oversize") is None

    clock[0] = 11
    assert cache.get("recent") == "one"
    assert "new" not in cache._values


def test_fallback_never_evicts_an_active_rate_limit_window_at_capacity():
    clock = [0.0]
    cache = MemoryTTLStore(now=lambda: clock[0], max_counters=2)
    assert cache.allow("first", 1, 60)
    assert cache.allow("second", 1, 60)
    for i in range(100):
        assert not cache.allow(f"new-{i}", 1, 60)
    assert not cache.allow("first", 1, 60)

    clock[0] = 61
    assert cache.allow("new-client", 1, 60)
    assert len(cache._counters) == 1
