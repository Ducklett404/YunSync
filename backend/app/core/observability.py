import json
import logging
import re
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.http_security import (
    apply_security_headers,
    rate_limit_key,
    rate_limiter,
)
from app.core.monitoring import monitoring_registry, normalized_route


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
LOG_RECORD_FIELDS = ("request_id", "method", "path", "status_code", "duration_ms", "error_type")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in LOG_RECORD_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("yunsync.api")
    logger.setLevel(settings.log_level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


logger = configure_logging()


def resolve_request_id(candidate: str | None) -> str:
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


async def request_context_middleware(request: Request, call_next):
    request_id = resolve_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    started_at = perf_counter()

    rate_decision = None
    error_type = None
    try:
        if (
            settings.force_https
            and request.url.scheme != "https"
            and request.url.path not in {"/healthz", "/readyz"}
        ):
            response = JSONResponse(
                status_code=400,
                content={"detail": "该环境只允许通过 HTTPS 访问", "request_id": request_id},
            )
        elif settings.rate_limit_enabled and request.url.path.startswith(
            settings.api_v1_prefix
        ):
            rate_decision = rate_limiter.check(rate_limit_key(request))
            if rate_decision.allowed:
                response = await call_next(request)
            else:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后重试", "request_id": request_id},
                    headers={"Retry-After": str(rate_decision.retry_after_seconds)},
                )
        else:
            response = await call_next(request)
    except Exception as exc:
        error_type = type(exc).__name__
        response = JSONResponse(
            status_code=500,
            content={"detail": "服务暂时不可用", "request_id": request_id},
        )

    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    route = normalized_route(request)
    if settings.monitoring_enabled:
        monitoring_registry.record(
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_ms=duration_ms,
            slow_threshold_ms=settings.slow_request_threshold_ms,
        )
    response.headers["X-Request-ID"] = request_id
    if rate_decision is not None:
        response.headers["X-RateLimit-Limit"] = str(rate_decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(rate_decision.remaining)
    apply_security_headers(request, response)

    log_context = {
        "request_id": request_id,
        "method": request.method,
        "path": route,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }
    if error_type is not None or response.status_code >= 500:
        if error_type is not None:
            log_context["error_type"] = error_type
        logger.error("request_failed", extra=log_context)
    elif response.status_code == 429:
        logger.warning("request_rate_limited", extra=log_context)
    elif duration_ms >= settings.slow_request_threshold_ms:
        logger.warning("request_slow", extra=log_context)
    else:
        logger.info("request_completed", extra=log_context)
    return response
