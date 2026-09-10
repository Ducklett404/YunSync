from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YunSync HealthLoop"
    environment: Literal["local", "development", "devspace", "staging", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "development-only"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "sqlite:///./backend/data/yunsync.db"
    redis_url: str = "redis://localhost:6379/0"

    use_mock_ai: bool = True
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
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
