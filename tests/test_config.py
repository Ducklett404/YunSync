from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.observability import resolve_request_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_local_configuration_accepts_mock_and_sqlite():
    settings = Settings(_env_file=None, environment="local", secret_key="development-only")

    assert settings.use_mock_ai is True
    assert settings.database_url.startswith("sqlite")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"secret_key": "development-only"}, "SECRET_KEY"),
        ({"secret_key": "replace-this-before-deployment"}, "SECRET_KEY"),
        ({"secret_key": "a" * 24, "database_url": "sqlite:///unsafe.db"}, "SQLite"),
        (
            {
                "secret_key": "a" * 24,
                "database_url": "postgresql+psycopg://user:pass@db/yunsync",
                "cors_origins": "*",
            },
            "CORS",
        ),
    ],
)
def test_staging_rejects_unsafe_configuration(overrides, message):
    values = {
        "_env_file": None,
        "environment": "staging",
        "database_url": "postgresql+psycopg://user:pass@db/yunsync",
        **overrides,
    }

    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_request_id_accepts_safe_value_and_replaces_log_injection():
    assert resolve_request_id("demo-request_01") == "demo-request_01"
    generated = resolve_request_id("bad\nrequest")
    assert len(generated) == 32
    assert generated.isalnum()


@pytest.mark.parametrize(
    ("template_name", "environment"),
    [
        (".env.local.example", "local"),
        (".env.devspace.example", "devspace"),
    ],
)
def test_nonproduction_environment_templates_load(template_name, environment):
    settings = Settings(_env_file=PROJECT_ROOT / template_name)

    assert settings.environment == environment
    assert settings.use_mock_ai is True


def test_staging_template_refuses_to_start_until_secret_is_replaced():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=PROJECT_ROOT / ".env.staging.example")
