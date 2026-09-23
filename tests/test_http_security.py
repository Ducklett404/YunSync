from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import observability
from app.core.config import settings
from app.core.http_security import SlidingWindowRateLimiter
from app.core.observability import JsonFormatter, request_context_middleware
from app.integrations.huawei.obs import LocalPrivateStorageClient, ObjectStorageError


def test_sliding_window_rate_limiter_recovers_after_window():
    now = [100.0]
    limiter = SlidingWindowRateLimiter(
        limit=2,
        window_seconds=10,
        max_clients=5,
        clock=lambda: now[0],
    )

    assert limiter.check("client-a").allowed is True
    assert limiter.check("client-a").allowed is True
    blocked = limiter.check("client-a")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds == 10

    now[0] = 111.0
    assert limiter.check("client-a").allowed is True


def test_request_middleware_adds_security_headers_and_rate_limits(monkeypatch):
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, max_clients=5)
    monkeypatch.setattr(observability, "rate_limiter", limiter)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    test_app = FastAPI()
    test_app.middleware("http")(request_context_middleware)

    @test_app.get("/api/v1/ping")
    def ping():
        return {"status": "ok"}

    client = TestClient(test_app)
    first = client.get("/api/v1/ping")
    blocked = client.get("/api/v1/ping")

    assert first.status_code == 200
    assert first.headers["X-Content-Type-Options"] == "nosniff"
    assert first.headers["X-Frame-Options"] == "DENY"
    assert first.headers["Cache-Control"] == "no-store"
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.json()["detail"] == "请求过于频繁，请稍后重试"


def test_https_requirement_exempts_health_probes(monkeypatch):
    monkeypatch.setattr(settings, "force_https", True)
    test_app = FastAPI()
    test_app.middleware("http")(request_context_middleware)

    @test_app.get("/api/v1/ping")
    def ping():
        return {"status": "ok"}

    @test_app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    client = TestClient(test_app)
    assert client.get("/api/v1/ping").status_code == 400
    assert client.get("/healthz").status_code == 200


def test_private_storage_rejects_path_traversal(tmp_path):
    client = LocalPrivateStorageClient(tmp_path / "uploads")

    try:
        client.read_private("../../outside.txt")
    except ObjectStorageError as exc:
        assert str(exc) == "报告源文件不可用"
    else:
        raise AssertionError("path traversal should be rejected")


def test_json_logs_drop_headers_credentials_and_health_payloads():
    record = observability.logging.LogRecord(
        name="yunsync.api",
        level=observability.logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "safe-request"
    record.method = "POST"
    record.path = "/api/v1/reports/analyze"
    record.status_code = 200
    record.authorization = "Bearer must-not-log"
    record.huawei_secret_key = "must-not-log-secret"
    record.health_payload = {"diagnosis": "must-not-log-health"}

    rendered = JsonFormatter().format(record)

    assert "safe-request" in rendered
    assert "must-not-log" not in rendered
    assert "diagnosis" not in rendered
