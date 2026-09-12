from __future__ import annotations

from typing import Any

from sqlalchemy.engine import make_url

from app.core.config import Settings


CLOUD_PREFLIGHT_VERSION = "cloud-preflight-v2"


def build_cloud_readiness(settings: Settings) -> dict[str, Any]:
    database = make_url(settings.database_url)
    redis_host = _url_host(settings.redis_url)
    uses_environment_credentials = settings.huawei_credential_mode == "environment"
    checks = [
        _check(
            "cloud_environment",
            settings.environment in {"staging", "production"},
            "运行环境必须明确为 staging 或 production。",
        ),
        _check(
            "rds_postgresql",
            database.drivername == "postgresql+psycopg"
            and bool(database.host)
            and not _is_local_or_placeholder(database.host or ""),
            "DATABASE_URL 必须使用非本机 PostgreSQL psycopg 目标。",
        ),
        _check(
            "dcs_redis",
            settings.cache_enabled
            and settings.redis_url.startswith(("redis://", "rediss://"))
            and bool(redis_host)
            and not _is_local_or_placeholder(redis_host),
            "必须显式启用缓存并指向非本机 Redis/DCS。",
        ),
        _check(
            "iam_identity",
            bool(settings.huawei_project_id)
            and (
                settings.huawei_credential_mode == "instance_metadata"
                or (
                    uses_environment_credentials
                    and bool(settings.huawei_access_key)
                    and bool(settings.huawei_secret_key)
                )
            ),
            "需要项目 ID，并使用实例身份或部署平台注入的 AK/SK。",
        ),
        _check(
            "obs_private_storage",
            not settings.use_local_storage and bool(settings.huawei_obs_bucket),
            "云环境必须关闭本地文件存储并配置私有 OBS 桶。",
        ),
        _check(
            "real_ai_adapters",
            not settings.use_mock_ai
            and bool(settings.huawei_ocr_endpoint)
            and bool(settings.huawei_maas_endpoint)
            and bool(settings.huawei_maas_api_key),
            "真实联调必须关闭 Mock 并注入 OCR/MaaS 端点和 MaaS 密钥。",
        ),
        _check(
            "production_demo_controls",
            settings.environment != "production"
            or (not settings.enable_demo_login and not settings.seed_demo_data),
            "Production 必须关闭演示登录和演示种子。",
        ),
        _check(
            "http_hardening",
            settings.force_https
            and not settings.expose_api_docs
            and settings.rate_limit_enabled
            and bool(settings.allowed_host_list)
            and "*" not in settings.allowed_host_list
            and all(
                not _is_local_or_placeholder(host)
                for host in settings.allowed_host_list
            )
            and bool(settings.forwarded_allow_ip_list)
            and "*" not in settings.forwarded_allow_ip_list,
            "云端必须启用 HTTPS 与限流、关闭 API 文档并限制主机和可信代理。",
        ),
    ]
    return {
        "version": CLOUD_PREFLIGHT_VERSION,
        "environment": settings.environment,
        "ready": all(item["passed"] for item in checks),
        "checks": checks,
        "configuration_summary": {
            "database_driver": database.drivername,
            "database_host_configured": bool(database.host),
            "cache_enabled": settings.cache_enabled,
            "cache_tls_requested": settings.redis_url.startswith("rediss://"),
            "credential_mode": settings.huawei_credential_mode,
            "static_credentials_present": bool(
                settings.huawei_access_key and settings.huawei_secret_key
            ),
            "local_storage_enabled": settings.use_local_storage,
            "mock_ai_enabled": settings.use_mock_ai,
            "demo_login_enabled": settings.enable_demo_login,
            "demo_seed_enabled": settings.seed_demo_data,
            "https_required": settings.force_https,
            "api_docs_exposed": settings.expose_api_docs,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "allowed_hosts_configured": bool(settings.allowed_host_list),
            "forwarded_proxy_allowlist_configured": bool(
                settings.forwarded_allow_ip_list
            ),
        },
    }


def _check(code: str, passed: bool, guidance: str) -> dict[str, str | bool]:
    return {"code": code, "passed": passed, "guidance": guidance}


def _url_host(value: str) -> str:
    try:
        return make_url(value).host or ""
    except Exception:
        return ""


def _is_local_or_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized in {"localhost", "127.0.0.1", "::1"}
        or "change_me" in normalized
    )
