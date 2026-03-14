from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
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
    polygon_api_key: str | None = None
    polygon_base_url: str = "https://api.polygon.io"
    polygon_timeout_seconds: int = 20
    polygon_universe_refresh_limit: int = 200
    polygon_intraday_lookback_days: int = 30
    polygon_daily_lookback_days: int = 90
    polygon_news_lookback_hours: int = 72
    polygon_news_limit: int = 25
    universe_min_price: Decimal = Decimal("5")
    universe_max_price: Decimal = Decimal("50")
    universe_min_avg_volume_20d: Decimal = Decimal("500000")
    universe_min_avg_dollar_volume_20d: Decimal = Decimal("5000000")
    phase2_history_window_bars: int = 20
    operator_state_db_path: str = ".doctrine/operations.db"
    run_interval_seconds: int = 900
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    halt_status_mode: str = "fail_open"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _resolve_local_paths(self) -> "Settings":
        if self.operator_state_db_path != ":memory:":
            path = Path(self.operator_state_db_path)
            if not path.is_absolute():
                self.operator_state_db_path = str((_REPO_ROOT / path).resolve())
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
