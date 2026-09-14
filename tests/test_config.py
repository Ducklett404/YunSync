from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.observability import resolve_request_id
from app.db.session import build_engine_options


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


def test_production_refuses_demo_login():
    with pytest.raises(ValidationError, match="ENABLE_DEMO_LOGIN"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-secret-key-value",
            database_url="postgresql+psycopg://user:pass@db/yunsync",
            cors_origins="https://app.example.com",
            enable_demo_login=True,
            run_migrations_on_startup=False,
        )


def test_production_refuses_local_upload_storage():
    with pytest.raises(ValidationError, match="USE_LOCAL_STORAGE"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-secret-key-value",
            database_url="postgresql+psycopg://user:pass@db/yunsync",
            cors_origins="https://app.example.com",
            enable_demo_login=False,
            run_migrations_on_startup=False,
            use_local_storage=True,
            use_mock_ai=False,
        )


def test_production_refuses_mock_ocr():
    with pytest.raises(ValidationError, match="USE_MOCK_AI"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-secret-key-value",
            database_url="postgresql+psycopg://user:pass@db/yunsync",
            cors_origins="https://app.example.com",
            enable_demo_login=False,
            run_migrations_on_startup=False,
            use_local_storage=False,
            use_mock_ai=True,
        )


def test_staging_requires_psycopg_driver_and_nonlocal_cache():
    with pytest.raises(ValidationError, match="psycopg"):
        Settings(
            _env_file=None,
            environment="staging",
            secret_key="a-staging-secret-key-value",
            database_url="postgresql://user:pass@db/yunsync",
            cors_origins="https://staging.example.com",
        )

    with pytest.raises(ValidationError, match="REDIS_URL"):
        Settings(
            _env_file=None,
            environment="staging",
            secret_key="a-staging-secret-key-value",
            database_url="postgresql+psycopg://user:pass@db/yunsync",
            cors_origins="https://staging.example.com",
            cache_enabled=True,
            redis_url="redis://localhost:6379/0",
        )


def test_production_refuses_demo_seed_data():
    with pytest.raises(ValidationError, match="SEED_DEMO_DATA"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-secret-key-value",
            database_url="postgresql+psycopg://user:pass@db/yunsync",
            cors_origins="https://app.example.com",
            enable_demo_login=False,
            run_migrations_on_startup=False,
            use_local_storage=False,
            use_mock_ai=False,
            seed_demo_data=True,
        )


def test_production_cloud_configuration_accepts_instance_metadata_credentials():
    settings = Settings(
        _env_file=None,
        environment="production",
        secret_key="a-production-secret-key-value",
        database_url="postgresql+psycopg://user:pass@rds.internal/yunsync",
        cors_origins="https://app.example.com",
        allowed_hosts="app.example.com",
        enable_demo_login=False,
        seed_demo_data=False,
        run_migrations_on_startup=False,
        use_local_storage=False,
        use_mock_ai=False,
        cache_enabled=True,
        redis_url="rediss://dcs.internal:6379/0",
        huawei_project_id="synthetic-project-id",
        huawei_credential_mode="instance_metadata",
        huawei_obs_bucket="synthetic-private-bucket",
        huawei_ocr_endpoint="https://ocr.example.com",
        huawei_maas_endpoint="https://maas.example.com",
        huawei_maas_api_key="synthetic-api-key",
        force_https=True,
        expose_api_docs=False,
        rate_limit_enabled=True,
        forwarded_allow_ips="10.0.0.8",
    )

    assert settings.huawei_credential_mode == "instance_metadata"
    assert settings.seed_demo_data is False
    assert settings.force_https is True
    assert settings.expose_api_docs is False
    assert settings.rate_limit_enabled is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"force_https": False}, "HTTPS"),
        ({"expose_api_docs": True}, "API_DOCS"),
        ({"rate_limit_enabled": False}, "RATE_LIMIT"),
        ({"forwarded_allow_ips": "*"}, "FORWARDED_ALLOW_IPS"),
        ({"allowed_hosts": "localhost"}, "正式服务域名"),
    ],
)
def test_production_rejects_missing_http_hardening(overrides, message):
    values = {
        "_env_file": None,
        "environment": "production",
        "secret_key": "a-production-secret-key-value",
        "database_url": "postgresql+psycopg://user:pass@rds.internal/yunsync",
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "app.example.com",
        "enable_demo_login": False,
        "seed_demo_data": False,
        "run_migrations_on_startup": False,
        "use_local_storage": False,
        "use_mock_ai": False,
        "cache_enabled": True,
        "redis_url": "rediss://dcs.internal:6379/0",
        "huawei_project_id": "synthetic-project-id",
        "huawei_credential_mode": "instance_metadata",
        "huawei_obs_bucket": "synthetic-private-bucket",
        "huawei_ocr_endpoint": "https://ocr.example.com",
        "huawei_maas_endpoint": "https://maas.example.com",
        "huawei_maas_api_key": "synthetic-api-key",
        "force_https": True,
        "expose_api_docs": False,
        "rate_limit_enabled": True,
        "forwarded_allow_ips": "10.0.0.8",
        **overrides,
    }

    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_production_refuses_application_startup_migrations():
    with pytest.raises(ValidationError, match="RUN_MIGRATIONS_ON_STARTUP"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-production-secret-key-value",
            database_url="postgresql+psycopg://user:pass@rds.internal/yunsync",
            cors_origins="https://app.example.com",
            allowed_hosts="app.example.com",
            enable_demo_login=False,
            seed_demo_data=False,
            run_migrations_on_startup=True,
            use_local_storage=False,
            use_mock_ai=False,
            cache_enabled=True,
            redis_url="rediss://dcs.internal:6379/0",
            huawei_project_id="synthetic-project-id",
            huawei_credential_mode="instance_metadata",
            huawei_obs_bucket="synthetic-private-bucket",
            huawei_ocr_endpoint="https://ocr.example.com",
            huawei_maas_endpoint="https://maas.example.com",
            huawei_maas_api_key="synthetic-api-key",
            force_https=True,
            expose_api_docs=False,
            rate_limit_enabled=True,
            forwarded_allow_ips="10.0.0.8",
        )


def test_database_engine_options_bound_postgres_pool_and_keep_sqlite_safe():
    sqlite_options = build_engine_options("sqlite:///test.db")
    postgres_options = build_engine_options(
        "postgresql+psycopg://user:pass@rds.internal/yunsync"
    )

    assert sqlite_options["connect_args"] == {"check_same_thread": False}
    assert "pool_size" not in sqlite_options
    assert postgres_options == {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 10,
        "pool_recycle": 1800,
    }
