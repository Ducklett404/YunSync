from contextlib import asynccontextmanager
from pathlib import Path
import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.controllers.api import api_router
from app.core.config import settings
from app.core.observability import request_context_middleware
from app.core.monitoring import monitoring_registry
from app.db.init_db import seed_db
from app.db.migrations import run_migrations
from app.db.session import SessionLocal
from app.integrations.cache import cache
from app.schemas.common import HealthStatus


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.run_migrations_on_startup:
        run_migrations()
    if settings.seed_demo_data:
        seed_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="云循个人健康行为优化平台 MVP API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.middleware("http")(request_context_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
    max_age=600,
)


@app.get("/healthz", response_model=HealthStatus, tags=["system"])
def healthz():
    return HealthStatus(status="ok", service=settings.app_name, environment=settings.environment)


@app.get("/readyz", response_model=HealthStatus, tags=["system"])
def readyz():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    cache_health = cache.health()
    return HealthStatus(
        status="ready",
        service=settings.app_name,
        environment=settings.environment,
        dependencies={"database": "ready", "cache": cache_health.backend},
        degraded=cache_health.degraded,
    )


@app.get("/internal/metrics", include_in_schema=False)
def metrics(x_monitoring_token: str | None = Header(default=None)):
    if not settings.monitoring_enabled:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not x_monitoring_token or not secrets.compare_digest(
        x_monitoring_token, settings.monitoring_token
    ):
        raise HTTPException(status_code=403, detail="监控凭据无效")
    return Response(
        content=monitoring_registry.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    frontend_root = FRONTEND_DIST.resolve()
    api_route_root = settings.api_v1_prefix.strip("/")
    app.mount("/assets", StaticFiles(directory=frontend_root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if full_path == api_route_root or full_path.startswith(f"{api_route_root}/"):
            raise HTTPException(status_code=404, detail="API 路由不存在")
        candidate = (frontend_root / full_path).resolve()
        if full_path and candidate.is_relative_to(frontend_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_root / "index.html")
