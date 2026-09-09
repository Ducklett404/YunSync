from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YunSync HealthLoop"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "development-only"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
