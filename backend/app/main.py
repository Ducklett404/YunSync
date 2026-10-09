from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from . import __version__
from .cache import ResilientCache
from .config import Settings
from .database import ContentRepository, Database, DatabaseUnavailable, seed_demo_content
from .maas import MaaSClient
from .natural import NaturalRecommendationService
from .schemas import NaturalRecommendationRequest, PantryRecommendationRequest, TodayRecommendationRequest
from .services import YunSyncService
from .weather import WeatherClient


logger = logging.getLogger("yunsync.api")


def _log(event: str, **fields: Any) -> None:
    # Only operational metadata belongs here. Never add request bodies or credentials.
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def create_app(
    settings: Settings | None = None,
    *,
    redis_client: Redis | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    database = Database(resolved_settings)
    cache = ResilientCache(resolved_settings, redis_client=redis_client)
    repository = ContentRepository(database, resolved_settings.allow_demo_content)
    weather = WeatherClient(resolved_settings, cache)
    service = YunSyncService(resolved_settings, repository, cache, weather)
    maas = MaaSClient(resolved_settings, cache)
    natural = NaturalRecommendationService(repository, service, maas)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            if resolved_settings.app_env != "production":
                database.create_schema()
            if resolved_settings.seed_demo_content:
                if not resolved_settings.seed_path.exists():
                    raise RuntimeError("configured demo seed file does not exist")
                seeded = seed_demo_content(database, resolved_settings.seed_path)
                _log("demo_content_seeded", **seeded)
        except SQLAlchemyError as exc:
            # Keep /health available so an RDS outage is observable; APIs return 503.
            _log("database_startup_degraded", reason=exc.__class__.__name__)
        yield

    app = FastAPI(
        title="YunSync Cloud API",
        description="Traceable wellness recipe recommendations with controlled M13 MaaS assistance.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.cache = cache
    app.state.repository = repository
    app.state.weather = weather
    app.state.service = service
    app.state.maas = maas
    app.state.natural = natural

    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
        )

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        client_host = request.client.host if request.client else "unknown"
        identity = hashlib.sha256(client_host.encode("utf-8")).hexdigest()[:16]
        allowed, rate_backend, rate_degraded = await run_in_threadpool(cache.allow, identity)
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limit_exceeded",
                    "message": "请求过于频繁，请稍后重试。",
                    "requestId": request_id,
                },
            )
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-YunSync-RateLimit-Backend"] = rate_backend
        _log(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            rate_limit_degraded=rate_degraded,
        )
        return response

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable_handler(request: Request, _: DatabaseUnavailable):
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        _log("database_unavailable", request_id=request_id, path=request.url.path)
        return JSONResponse(
            status_code=503,
            content={
                "code": "database_unavailable",
                "message": "食谱数据服务暂不可用，未返回推荐结果。",
                "degraded": ["database"],
                "requestId": request_id,
                "results": [],
            },
        )

    @app.get("/health")
    def health():
        database_ok, database_error = database.health()
        cache_health = cache.health()
        database_status = "ok" if database_ok else "unavailable"
        if database_ok and resolved_settings.database_kind != "postgresql":
            database_status = "degraded"
        weather_status = "configured" if resolved_settings.weather_api_url else "degraded"
        status = "ok"
        if (
            database_status != "ok"
            or cache_health["status"] != "ok"
            or weather_status != "configured"
            or maas.status() != "configured"
            or not resolved_settings.production_safe
        ):
            status = "degraded"
        return {
            "status": status,
            "version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {
                "database": {
                    "status": database_status,
                    "kind": resolved_settings.database_kind,
                    **({"reason": database_error} if database_error else {}),
                },
                "cache": cache_health,
                "weather": {
                    "status": weather_status,
                    "provider": resolved_settings.weather_provider,
                },
                "maas": {"status": maas.status()},
            },
        }

    @app.get("/v1/context/today")
    def context_today(
        city: str = Query(min_length=1, max_length=40),
        date_value: date | None = Query(default=None, alias="date"),
    ):
        return service.context_today(city.strip(), date_value or date.today())

    @app.post("/v1/recommendations/today")
    def recommendations_today(payload: TodayRecommendationRequest):
        return service.recommend_today(payload)

    @app.post("/v1/recommendations/pantry")
    def recommendations_pantry(payload: PantryRecommendationRequest):
        return service.recommend_pantry(payload)

    @app.post("/v1/recommendations/natural")
    def recommendations_natural(payload: NaturalRecommendationRequest):
        return natural.recommend(payload)

    @app.get("/v1/recipes/{recipe_id}")
    def recipe_detail(recipe_id: str):
        if not recipe_id or len(recipe_id) > 80 or not all(
            character.isalnum() or character in {"-", "_"} for character in recipe_id
        ):
            raise HTTPException(status_code=400, detail="invalid recipe id")
        recipe, cache_status, cache_degraded = service.recipe(recipe_id)
        if recipe is None:
            raise HTTPException(status_code=404, detail="recipe not found")
        return {
            "recipe": recipe,
            "cache": {
                "status": cache_status,
                "backend": "memory" if cache_degraded else "redis",
            },
            "degraded": ["cache"] if cache_degraded else [],
        }

    return app


app = create_app()
