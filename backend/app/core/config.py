from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YunSync HealthLoop"
    environment: Literal["local", "development", "devspace", "staging", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "development-only"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    forwarded_allow_ips: str = "127.0.0.1"
    force_https: bool = False
    expose_api_docs: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    slow_request_threshold_ms: int = Field(default=500, ge=50, le=10000)
    rate_limit_enabled: bool = False
    rate_limit_requests: int = Field(default=120, ge=10, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_max_clients: int = Field(default=10000, ge=100, le=100000)
    monitoring_enabled: bool = False
    monitoring_token: str = ""
    enable_demo_login: bool = True
    seed_demo_data: bool = True
    run_migrations_on_startup: bool = True
    session_ttl_hours: int = Field(default=12, ge=1, le=72)

    database_url: str = "sqlite:///./backend/data/yunsync.db"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=7200)
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = False
    cache_namespace: str = Field(default="yunsync", pattern=r"^[a-z0-9][a-z0-9_-]{1,31}$")
    cache_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    cache_connect_timeout_seconds: float = Field(default=0.3, ge=0.05, le=5.0)
    cache_socket_timeout_seconds: float = Field(default=0.5, ge=0.05, le=5.0)

    use_mock_ai: bool = True
    use_local_storage: bool = True
    upload_storage_dir: str = "backend/data/uploads"
    ocr_timeout_seconds: float = Field(default=8.0, ge=0.1, le=60.0)
    ocr_max_attempts: int = Field(default=2, ge=1, le=4)
    ocr_pdf_max_pages: int = Field(default=10, ge=1, le=20)
    maas_timeout_seconds: float = Field(default=8.0, ge=0.1, le=60.0)
    maas_max_tokens: int = Field(default=320, ge=64, le=1024)
    huawei_region: str = "cn-north-4"
    huawei_credential_mode: Literal["environment", "instance_metadata"] = "environment"
    huawei_project_id: str = ""
    huawei_access_key: str = ""
    huawei_secret_key: str = ""
    huawei_ocr_endpoint: str = ""
    huawei_maas_endpoint: str = ""
    huawei_maas_api_key: str = ""
    huawei_maas_model: str = ""
    huawei_obs_endpoint: str = ""
    huawei_obs_bucket: str = ""
    huawei_obs_validation_ref: str = ""
    huawei_ocr_validation_ref: str = ""
    huawei_maas_validation_ref: str = ""
    release_image_ref: str = ""
    backup_restore_validation_ref: str = ""
    https_validation_ref: str = ""
    alerting_validation_ref: str = ""
    professional_review_validation_ref: str = ""
    user_test_validation_ref: str = ""
    customer_acceptance_validation_ref: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Settings:
        if not self.api_v1_prefix.startswith("/"):
            raise ValueError("API_V1_PREFIX 必须以 / 开头")

        if self.cache_enabled and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("启用缓存时 REDIS_URL 必须使用 redis:// 或 rediss://")

        if self.environment in {"staging", "production"}:
            unsafe_secrets = {"", "development-only", "replace-this-before-deployment"}
            if self.secret_key in unsafe_secrets or len(self.secret_key) < 24:
                raise ValueError("Staging/Production 必须配置至少 24 位的独立 SECRET_KEY")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Staging/Production 不允许使用 SQLite")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Staging/Production 必须使用 PostgreSQL psycopg 驱动")
            if "*" in self.cors_origin_list:
                raise ValueError("Staging/Production 不允许使用通配 CORS 来源")
            if not self.allowed_host_list or "*" in self.allowed_host_list:
                raise ValueError("Staging/Production 必须限制 ALLOWED_HOSTS")
        if self.environment == "production" and self.enable_demo_login:
            raise ValueError("Production 必须关闭 ENABLE_DEMO_LOGIN")
        if self.environment == "production" and self.use_local_storage:
            raise ValueError("Production 必须关闭 USE_LOCAL_STORAGE 并配置受控对象存储")
        if self.environment == "production" and self.use_mock_ai:
            raise ValueError("Production 必须关闭 USE_MOCK_AI 并配置真实 AI/OCR 服务")
        if self.environment == "production" and self.seed_demo_data:
            raise ValueError("Production 必须关闭 SEED_DEMO_DATA")
        if self.environment == "production" and self.run_migrations_on_startup:
            raise ValueError("Production 必须关闭 RUN_MIGRATIONS_ON_STARTUP 并使用独立迁移任务")
        if self.environment == "production" and not self.force_https:
            raise ValueError("Production 必须启用 FORCE_HTTPS")
        if self.environment == "production" and self.expose_api_docs:
            raise ValueError("Production 必须关闭 EXPOSE_API_DOCS")
        if self.environment == "production" and not self.rate_limit_enabled:
            raise ValueError("Production 必须启用 RATE_LIMIT_ENABLED")
        if self.environment == "production" and not self.monitoring_enabled:
            raise ValueError("Production 必须启用 MONITORING_ENABLED")
        if self.environment == "production" and (
            len(self.monitoring_token) < 24 or self._is_placeholder(self.monitoring_token)
        ):
            raise ValueError("Production 必须配置至少 24 位的独立 MONITORING_TOKEN")
        if self.environment == "production" and any(
            host.lower() in {"localhost", "127.0.0.1", "::1"}
            or self._is_placeholder(host)
            for host in self.allowed_host_list
        ):
            raise ValueError("Production 的 ALLOWED_HOSTS 必须使用正式服务域名")
        if self.environment == "production" and (
            "*" in self.forwarded_allow_ip_list
            or not self.forwarded_allow_ip_list
        ):
            raise ValueError("Production 必须限制 FORWARDED_ALLOW_IPS")

        if self.environment in {"staging", "production"}:
            if self.cache_enabled and self._is_placeholder_url(self.redis_url):
                raise ValueError("启用云缓存时 REDIS_URL 不能指向本机或占位地址")
            if not self.use_local_storage:
                required_obs = {
                    "HUAWEI_OBS_ENDPOINT": self.huawei_obs_endpoint,
                    "HUAWEI_OBS_BUCKET": self.huawei_obs_bucket,
                }
                missing_obs = [
                    name for name, value in required_obs.items() if self._is_placeholder(value)
                ]
                if missing_obs:
                    raise ValueError(f"真实 OBS 模式缺少配置：{', '.join(missing_obs)}")
            if not self.use_mock_ai:
                required_ai = {
                    "HUAWEI_OCR_ENDPOINT": self.huawei_ocr_endpoint,
                    "HUAWEI_MAAS_ENDPOINT": self.huawei_maas_endpoint,
                    "HUAWEI_MAAS_API_KEY": self.huawei_maas_api_key,
                    "HUAWEI_MAAS_MODEL": self.huawei_maas_model,
                }
                missing_ai = [
                    name for name, value in required_ai.items() if self._is_placeholder(value)
                ]
                if missing_ai:
                    raise ValueError(f"真实 AI 模式缺少配置：{', '.join(missing_ai)}")
            endpoints = {
                "HUAWEI_OBS_ENDPOINT": self.huawei_obs_endpoint if not self.use_local_storage else "",
                "HUAWEI_OCR_ENDPOINT": self.huawei_ocr_endpoint if not self.use_mock_ai else "",
                "HUAWEI_MAAS_ENDPOINT": self.huawei_maas_endpoint if not self.use_mock_ai else "",
            }
            insecure_endpoints = [
                name
                for name, value in endpoints.items()
                if value and not value.lower().startswith("https://")
            ]
            if insecure_endpoints:
                raise ValueError(
                    f"云服务端点必须使用 HTTPS：{', '.join(insecure_endpoints)}"
                )
            uses_huawei_services = not self.use_local_storage or not self.use_mock_ai
            if uses_huawei_services and self._is_placeholder(self.huawei_project_id):
                raise ValueError("启用华为云服务时必须配置 HUAWEI_PROJECT_ID")
            if uses_huawei_services and self.huawei_credential_mode == "environment":
                if self._is_placeholder(self.huawei_access_key) or self._is_placeholder(
                    self.huawei_secret_key
                ):
                    raise ValueError("environment 凭据模式必须注入 HUAWEI_ACCESS_KEY/SECRET_KEY")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def forwarded_allow_ip_list(self) -> list[str]:
        return [value.strip() for value in self.forwarded_allow_ips.split(",") if value.strip()]

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        normalized = value.strip().lower()
        return not normalized or "change_me" in normalized or normalized.startswith("replace-")

    @classmethod
    def _is_placeholder_url(cls, value: str) -> bool:
        normalized = value.lower()
        return cls._is_placeholder(value) or "localhost" in normalized or "127.0.0.1" in normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
