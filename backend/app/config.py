from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or "")
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _boolean(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, repr=False)
class Settings:
    app_env: str
    database_url: str
    redis_url: str | None
    weather_api_url: str | None
    weather_api_key: str | None
    weather_provider: str
    weather_timeout_seconds: float
    maas_api_url: str | None
    maas_api_key: str | None
    maas_model: str | None
    maas_timeout_seconds: float
    maas_retries: int
    maas_cache_ttl_seconds: int
    maas_circuit_failures: int
    maas_circuit_seconds: int
    cache_version: str
    recommendation_ttl_seconds: int
    weather_ttl_seconds: int
    negative_ttl_seconds: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    allow_demo_content: bool
    seed_demo_content: bool
    seed_path: Path
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = environ if environ is not None else os.environ
        default_db = (BACKEND_ROOT / "data" / "yunsync-m12.db").as_posix()
        origins = tuple(
            item.strip()
            for item in env.get("YUNSYNC_CORS_ORIGINS", "http://localhost:5173").split(",")
            if item.strip()
        )
        return cls(
            app_env=env.get("YUNSYNC_APP_ENV", "development").strip(),
            database_url=env.get(
                "YUNSYNC_DATABASE_URL",
                f"sqlite+pysqlite:///{default_db}",
            ).strip(),
            redis_url=(env.get("YUNSYNC_REDIS_URL") or "").strip() or None,
            weather_api_url=(env.get("YUNSYNC_WEATHER_API_URL") or "").strip() or None,
            weather_api_key=(env.get("YUNSYNC_WEATHER_API_KEY") or "").strip() or None,
            weather_provider=env.get("YUNSYNC_WEATHER_PROVIDER", "configured-weather-service").strip(),
            weather_timeout_seconds=float(env.get("YUNSYNC_WEATHER_TIMEOUT_SECONDS", "3.5")),
            maas_api_url=(env.get("YUNSYNC_MAAS_API_URL") or "").strip() or None,
            maas_api_key=(env.get("YUNSYNC_MAAS_API_KEY") or "").strip() or None,
            maas_model=(env.get("YUNSYNC_MAAS_MODEL") or "").strip() or None,
            maas_timeout_seconds=float(env.get("YUNSYNC_MAAS_TIMEOUT_SECONDS", "4")),
            maas_retries=max(0, min(2, int(env.get("YUNSYNC_MAAS_RETRIES", "1")))),
            maas_cache_ttl_seconds=_positive_int(env.get("YUNSYNC_MAAS_CACHE_TTL_SECONDS"), 600),
            maas_circuit_failures=_positive_int(env.get("YUNSYNC_MAAS_CIRCUIT_FAILURES"), 3),
            maas_circuit_seconds=_positive_int(env.get("YUNSYNC_MAAS_CIRCUIT_SECONDS"), 60),
            cache_version=env.get("YUNSYNC_CACHE_VERSION", "m12-v1").strip(),
            recommendation_ttl_seconds=_positive_int(
                env.get("YUNSYNC_RECOMMENDATION_TTL_SECONDS"), 900
            ),
            weather_ttl_seconds=_positive_int(env.get("YUNSYNC_WEATHER_TTL_SECONDS"), 1800),
            negative_ttl_seconds=_positive_int(env.get("YUNSYNC_NEGATIVE_TTL_SECONDS"), 60),
            rate_limit_requests=_positive_int(env.get("YUNSYNC_RATE_LIMIT_REQUESTS"), 60),
            rate_limit_window_seconds=_positive_int(
                env.get("YUNSYNC_RATE_LIMIT_WINDOW_SECONDS"), 60
            ),
            allow_demo_content=_boolean(env.get("YUNSYNC_ALLOW_DEMO_CONTENT"), True),
            seed_demo_content=_boolean(env.get("YUNSYNC_SEED_DEMO_CONTENT"), True),
            seed_path=Path(
                env.get(
                    "YUNSYNC_SEED_PATH",
                    str(BACKEND_ROOT / "seeds" / "m12-demo-content.json"),
                )
            ),
            cors_origins=origins,
        )

    @property
    def database_kind(self) -> str:
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        if self.database_url.startswith("sqlite"):
            return "sqlite"
        return "other"

    @property
    def production_safe(self) -> bool:
        if self.app_env != "production":
            return True
        return self.database_kind == "postgresql" and bool(self.redis_url)
