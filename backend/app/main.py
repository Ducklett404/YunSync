from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.controllers.api import api_router
from app.core.config import settings
from app.db.init_db import seed_db
from app.db.migrations import run_migrations
from app.db.session import SessionLocal
from app.schemas.common import HealthStatus


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    seed_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="云循个人健康行为优化平台 MVP API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthStatus, tags=["system"])
def healthz():
    return HealthStatus(status="ok", service=settings.app_name, environment=settings.environment)


@app.get("/readyz", response_model=HealthStatus, tags=["system"])
def readyz():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return HealthStatus(status="ready", service=settings.app_name, environment=settings.environment)


app.include_router(api_router, prefix=settings.api_v1_prefix)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    frontend_root = FRONTEND_DIST.resolve()
    app.mount("/assets", StaticFiles(directory=frontend_root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        candidate = (frontend_root / full_path).resolve()
        if full_path and candidate.is_relative_to(frontend_root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_root / "index.html")
