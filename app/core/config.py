from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVENT_ENGINE_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./events.db"
    webhook_secrets: dict[str, SecretStr] = Field(default_factory=dict)
    delivery_signing_secret: SecretStr | None = None
    github_token: SecretStr | None = None
    max_event_bytes: int = Field(default=262144, ge=1024, le=10485760)
    delivery_lease_seconds: int = Field(default=60, ge=15, le=3600)
    delivery_max_attempts: int = Field(default=5, ge=1, le=20)
    retry_base_seconds: int = Field(default=5, ge=1, le=3600)
    retry_max_seconds: int = Field(default=900, ge=1, le=86400)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    recovery_interval_seconds: float = Field(default=15, ge=1, le=3600)
    process_metrics_port: int = Field(default=9100, ge=1024, le=65535)


@lru_cache
def get_settings() -> Settings:
    return Settings()
