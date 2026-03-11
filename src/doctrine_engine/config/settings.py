from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SDE_",
        extra="ignore",
    )

    app_name: str = "structure-doctrine-engine"
    env: str = "local"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/doctrine"
    )
    redis_url: str = "redis://localhost:6379/0"
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    alert_cooldown_minutes: int = 60
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
