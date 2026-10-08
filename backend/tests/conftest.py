from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.config import Settings
from app.database import seed_demo_content
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = Settings.from_env({})
    values = {
        "app_env": "test",
        "database_url": f"sqlite+pysqlite:///{(tmp_path / 'test.db').as_posix()}",
        "redis_url": None,
        "weather_api_url": None,
        "allow_demo_content": True,
        "seed_demo_content": True,
        "seed_path": BACKEND_ROOT / "seeds" / "m12-demo-content.json",
        "rate_limit_requests": 1000,
        "recommendation_ttl_seconds": 60,
    }
    values.update(overrides)
    return replace(base, **values)


@pytest.fixture
def app_client(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.database.create_schema()
    seed_demo_content(app.state.database, app.state.settings.seed_path)
    yield app
    app.state.database.engine.dispose()
