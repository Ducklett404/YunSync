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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    enable_demo_login: bool = True
    session_ttl_hours: int = Field(default=12, ge=1, le=72)

    database_url: str = "sqlite:///./backend/data/yunsync.db"
    redis_url: str = "redis://localhost:6379/0"

    use_mock_ai: bool = True
    use_local_storage: bool = True
    upload_storage_dir: str = "backend/data/uploads"
    ocr_timeout_seconds: float = Field(default=8.0, ge=0.1, le=60.0)
    ocr_max_attempts: int = Field(default=2, ge=1, le=4)
    huawei_region: str = "cn-north-4"
    huawei_project_id: str = ""
    huawei_access_key: str = ""
    huawei_secret_key: str = ""
    huawei_ocr_endpoint: str = ""
    huawei_maas_endpoint: str = ""
    huawei_maas_api_key: str = ""
    huawei_obs_bucket: str = ""

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

        if self.environment in {"staging", "production"}:
            unsafe_secrets = {"", "development-only", "replace-this-before-deployment"}
            if self.secret_key in unsafe_secrets or len(self.secret_key) < 24:
                raise ValueError("Staging/Production 必须配置至少 24 位的独立 SECRET_KEY")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Staging/Production 不允许使用 SQLite")
            if "*" in self.cors_origin_list:
                raise ValueError("Staging/Production 不允许使用通配 CORS 来源")
        if self.environment == "production" and self.enable_demo_login:
            raise ValueError("Production 必须关闭 ENABLE_DEMO_LOGIN")
        if self.environment == "production" and self.use_local_storage:
            raise ValueError("Production 必须关闭 USE_LOCAL_STORAGE 并配置受控对象存储")
        if self.environment == "production" and self.use_mock_ai:
            raise ValueError("Production 必须关闭 USE_MOCK_AI 并配置真实 AI/OCR 服务")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
