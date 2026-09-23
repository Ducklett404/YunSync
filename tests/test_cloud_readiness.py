import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.cloud_readiness import build_cloud_readiness
from app.core.config import Settings
from scripts.postgres_ops import (
    backup_command,
    parse_postgres_target,
    postgres_environment,
    restore_command,
    validate_restore_confirmation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        secret_key="a-production-secret-key-value",
        database_url=(
            "postgresql+psycopg://cloud_user:synthetic_password@rds.internal:5432/"
            "yunsync?sslmode=require"
        ),
        cors_origins="https://app.example.com",
        enable_demo_login=False,
        seed_demo_data=False,
        run_migrations_on_startup=False,
        cache_enabled=True,
        redis_url="rediss://dcs.internal:6379/0",
        use_local_storage=False,
        use_mock_ai=False,
        huawei_project_id="synthetic-project-id",
        huawei_credential_mode="instance_metadata",
        huawei_obs_endpoint="https://obs.example.com",
        huawei_obs_bucket="synthetic-private-bucket",
        huawei_ocr_endpoint="https://ocr.example.com",
        huawei_maas_endpoint="https://maas.example.com",
        huawei_maas_api_key="synthetic-api-key",
        huawei_maas_model="synthetic-model",
        allowed_hosts="app.example.com",
        forwarded_allow_ips="10.0.0.8",
        force_https=True,
        expose_api_docs=False,
        rate_limit_enabled=True,
    )


def test_cloud_preflight_reports_local_mode_as_incomplete_without_secrets():
    report = build_cloud_readiness(Settings(_env_file=None, environment="local"))
    serialized = json.dumps(report)

    assert report["ready"] is False
    assert report["configuration_summary"]["database_driver"] == "sqlite"
    assert "development-only" not in serialized
    assert "redis://localhost" not in serialized


def test_cloud_preflight_requires_live_acceptance_even_with_implemented_adapters():
    report = build_cloud_readiness(_production_settings())

    checks = {item["code"]: item["passed"] for item in report["checks"]}

    assert report["ready"] is False
    assert report["version"] == "cloud-preflight-v4"
    assert checks["obs_private_storage"] is True
    assert checks["real_ai_configuration"] is True
    assert checks["startup_migrations_disabled"] is True
    assert checks["obs_adapter_implemented"] is True
    assert checks["ocr_adapter_implemented"] is True
    assert checks["maas_adapter_implemented"] is True
    assert checks["provider_live_acceptance"] is False
    assert report["configuration_summary"]["credential_mode"] == "instance_metadata"
    assert report["configuration_summary"]["https_required"] is True
    assert report["configuration_summary"]["startup_migrations_enabled"] is False
    assert "synthetic_password" not in json.dumps(report)


def test_cloud_preflight_accepts_redacted_live_validation_references():
    settings = _production_settings()
    settings.huawei_obs_validation_ref = "OBS-ACCEPT-20260923"
    settings.huawei_ocr_validation_ref = "OCR-ACCEPT-20260923"
    settings.huawei_maas_validation_ref = "MAAS-ACCEPT-20260923"

    report = build_cloud_readiness(settings)

    assert report["ready"] is True
    checks = {item["code"]: item["passed"] for item in report["checks"]}
    assert checks["provider_live_acceptance"] is True
    assert report["configuration_summary"]["obs_live_acceptance_recorded"] is True
    assert "OBS-ACCEPT-20260923" not in json.dumps(report)


@pytest.mark.parametrize("placeholder", ["CHANGE_ME", "replace_this", "pending", "short"])
def test_cloud_preflight_rejects_placeholder_validation_references(placeholder):
    settings = _production_settings()
    settings.huawei_obs_validation_ref = placeholder
    settings.huawei_ocr_validation_ref = "OCR-ACCEPT-20260923"
    settings.huawei_maas_validation_ref = "MAAS-ACCEPT-20260923"

    report = build_cloud_readiness(settings)

    checks = {item["code"]: item["passed"] for item in report["checks"]}
    assert checks["provider_live_acceptance"] is False


def test_postgres_operations_keep_credentials_out_of_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "must-not-reach-child")
    target = parse_postgres_target(
        "postgresql+psycopg://cloud_user:secret_value@rds.internal:5433/yunsync"
        "?sslmode=require"
    )
    environment = postgres_environment(target)
    backup = backup_command(tmp_path / "backup.dump")
    restore = restore_command(tmp_path / "backup.dump", target.database)

    assert target.port == 5433
    assert environment["PGPASSWORD"] == "secret_value"
    assert environment["PGSSLMODE"] == "require"
    assert "DATABASE_URL" not in environment
    assert "secret_value" not in " ".join(backup + restore)
    assert "--clean" in restore


def test_restore_requires_exact_database_confirmation():
    target = parse_postgres_target(
        "postgresql+psycopg://cloud_user:secret@rds.internal/yunsync"
    )

    with pytest.raises(ValueError, match="完全一致"):
        validate_restore_confirmation(target, "other_database")
    validate_restore_confirmation(target, "yunsync")


def test_postgresql_offline_migration_script_generates_from_empty_database():
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql+psycopg://synthetic:never-connect@rds.invalid/yunsync"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "CREATE TABLE experiments" in completed.stdout
    assert "uq_experiments_active_user" in completed.stdout
    assert "never-connect" not in completed.stdout
