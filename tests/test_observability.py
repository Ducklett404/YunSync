import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.observability import JsonFormatter, request_context_middleware


def test_json_formatter_emits_structured_request_context():
    record = logging.LogRecord(
        name="yunsync.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-01"
    record.method = "GET"
    record.path = "/healthz"
    record.status_code = 200
    record.duration_ms = 1.25

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "req-01"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 1.25


def test_unhandled_exception_returns_safe_payload_and_request_id():
    test_app = FastAPI()
    test_app.middleware("http")(request_context_middleware)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://client.example"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("sensitive internal message")

    response = TestClient(test_app, raise_server_exceptions=False).get(
        "/boom",
        headers={"X-Request-ID": "failure-01", "Origin": "https://client.example"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failure-01"
    assert response.headers["Access-Control-Allow-Origin"] == "https://client.example"
    assert response.json() == {"detail": "服务暂时不可用", "request_id": "failure-01"}
    assert "sensitive internal message" not in response.text
