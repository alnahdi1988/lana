import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class DoctrineSignalSettings(BaseModel):
    signal_version: str = "v1"
    long_confidence_threshold: Decimal = Decimal("0.70")
    fail_closed_event_risk: bool = False
    fail_closed_regime: bool = False
    htf_bearish_event_lookback_bars: int = 3
    mtf_invalidation_lookback_bars: int = 1
    ltf_structure_trigger_freshness_bars: int = 1
    micro_trigger_freshness_bars: int = 1
    grade_a_plus_threshold: Decimal = Decimal("0.90")
    grade_a_threshold: Decimal = Decimal("0.80")
    grade_b_threshold: Decimal = Decimal("0.70")
    htf_timeframe: str = "4H"
    mtf_timeframe: str = "1H"
    ltf_timeframe: str = "15M"
    micro_timeframe: str = "5M"
    htf_bullish_weight: Decimal = Decimal("0.20")
    mtf_weight_recontainment: Decimal = Decimal("0.20")
    mtf_weight_reclaim: Decimal = Decimal("0.20")
    mtf_weight_discount: Decimal = Decimal("0.16")
    mtf_weight_equilibrium: Decimal = Decimal("0.14")
    ltf_weight_trap_reverse: Decimal = Decimal("0.15")
    ltf_weight_fake_breakdown: Decimal = Decimal("0.14")
    ltf_weight_reclaim: Decimal = Decimal("0.12")
    ltf_weight_choch: Decimal = Decimal("0.10")
    ltf_weight_bos: Decimal = Decimal("0.08")
    cross_frame_alignment_bonus: Decimal = Decimal("0.10")
    discount_zone_bonus: Decimal = Decimal("0.05")
    equilibrium_zone_bonus: Decimal = Decimal("0.03")
    compression_bonus: Decimal = Decimal("0.03")
    displacement_bonus: Decimal = Decimal("0.02")
    regime_market_permission_strong_threshold: Decimal = Decimal("0.70")
    regime_sector_permission_strong_threshold: Decimal = Decimal("0.60")
    regime_permission_strong_bonus: Decimal = Decimal("0.05")
    regime_permission_supportive_bonus: Decimal = Decimal("0.02")
    sector_strength_bonus_strong: Decimal = Decimal("0.03")
    sector_strength_bonus_neutral: Decimal = Decimal("0.01")
    sector_strength_bonus_weak: Decimal = Decimal("0.00")
    sector_strength_bonus_unknown: Decimal = Decimal("0.00")
    max_event_risk_soft_penalty: Decimal = Decimal("0.10")


class DoctrineRankingSettings(BaseModel):
    config_version: str = "v1"
    top_threshold: Decimal = Decimal("0.85")
    high_threshold: Decimal = Decimal("0.75")
    medium_threshold: Decimal = Decimal("0.65")
    min_rr_for_positive_rank: Decimal = Decimal("1.20")
    strong_rr1_threshold: Decimal = Decimal("1.50")
    strong_rr2_threshold: Decimal = Decimal("2.50")
    min_risk_distance: Decimal = Decimal("0.05")
    grade_weight_a_plus: Decimal = Decimal("0.22")
    grade_weight_a: Decimal = Decimal("0.16")
    grade_weight_b: Decimal = Decimal("0.08")
    confidence_multiplier: Decimal = Decimal("0.30")
    setup_weight_recontainment: Decimal = Decimal("0.15")
    setup_weight_reclaim: Decimal = Decimal("0.12")
    setup_weight_discount: Decimal = Decimal("0.10")
    setup_weight_equilibrium: Decimal = Decimal("0.08")
    entry_weight_confirmation: Decimal = Decimal("0.08")
    entry_weight_base: Decimal = Decimal("0.05")
    entry_weight_aggressive: Decimal = Decimal("0.03")
    regime_bonus_bullish_trend: Decimal = Decimal("0.08")
    regime_bonus_weak_drift: Decimal = Decimal("0.04")
    regime_penalty_chop: Decimal = Decimal("0.04")
    regime_penalty_high_vol_expansion: Decimal = Decimal("0.08")
    sector_bonus_strong: Decimal = Decimal("0.06")
    sector_penalty_weak: Decimal = Decimal("0.05")
    market_permission_multiplier: Decimal = Decimal("0.10")
    sector_permission_multiplier: Decimal = Decimal("0.08")
    rr1_bonus_strong: Decimal = Decimal("0.10")
    rr1_bonus_positive: Decimal = Decimal("0.05")
    rr1_penalty_weak: Decimal = Decimal("0.08")
    rr2_bonus_strong: Decimal = Decimal("0.06")
    confirmation_entry_bonus: Decimal = Decimal("0.03")
    aggressive_entry_penalty: Decimal = Decimal("0.02")
    trail_structural_bonus: Decimal = Decimal("0.03")
    partial_coverage_penalty: Decimal = Decimal("0.03")


class DoctrineAlertSettings(BaseModel):
    sendable_grades: tuple[str, ...] = ("A+", "A")
    suppress_event_risk_blocked: bool = True


class DoctrineRunnerSettings(BaseModel):
    config_version: str = "v1"
    run_mode: str = "ONCE"
    fail_fast: bool = False
    continue_on_symbol_error: bool = True
    max_symbol_failures_before_abort: int = 25
    external_read_retry_attempts: int = 2
    external_read_retry_backoff_ms: int = 250
    require_micro_confirmation: bool = False
    enable_ranking: bool = True
    enable_alert_workflow: bool = True
    enable_snapshot_requests: bool = False
    htf_timeframe: str = "4H"
    mtf_timeframe: str = "1H"
    ltf_timeframe: str = "15M"
    micro_timeframe: str = "5M"


class DoctrineConfig(BaseModel):
    signal: DoctrineSignalSettings = Field(default_factory=DoctrineSignalSettings)
    ranking: DoctrineRankingSettings = Field(default_factory=DoctrineRankingSettings)
    alert: DoctrineAlertSettings = Field(default_factory=DoctrineAlertSettings)
    runner: DoctrineRunnerSettings = Field(default_factory=DoctrineRunnerSettings)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_prefix="SDE_",
        env_nested_delimiter="__",
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
    paper_trading_mode: bool = True
    auto_start_runtime: bool = False
    delayed_data_wording_mode: str = "standard"
    doctrine: DoctrineConfig = Field(default_factory=DoctrineConfig)

    @model_validator(mode="after")
    def _resolve_local_paths(self) -> "Settings":
        if self.operator_state_db_path != ":memory:":
            path = Path(self.operator_state_db_path)
            if not path.is_absolute():
                self.operator_state_db_path = str((_REPO_ROOT / path).resolve())
        return self

    def build_signal_engine_config(self):
        from doctrine_engine.engines.signal_engine import SignalEngineConfig

        signal = self.doctrine.signal
        runner = self.doctrine.runner
        return SignalEngineConfig(
            signal_version=signal.signal_version,
            long_confidence_threshold=signal.long_confidence_threshold,
            require_micro_confirmation=runner.require_micro_confirmation,
            micro_context_requested=(runner.require_micro_confirmation or runner.micro_timeframe is not None),
            fail_closed_event_risk=signal.fail_closed_event_risk,
            fail_closed_regime=signal.fail_closed_regime,
            htf_bearish_event_lookback_bars=signal.htf_bearish_event_lookback_bars,
            mtf_invalidation_lookback_bars=signal.mtf_invalidation_lookback_bars,
            ltf_structure_trigger_freshness_bars=signal.ltf_structure_trigger_freshness_bars,
            micro_trigger_freshness_bars=signal.micro_trigger_freshness_bars,
            grade_a_plus_threshold=signal.grade_a_plus_threshold,
            grade_a_threshold=signal.grade_a_threshold,
            grade_b_threshold=signal.grade_b_threshold,
            universe_min_price=self.universe_min_price,
            universe_max_price=self.universe_max_price,
            htf_timeframe=signal.htf_timeframe,
            mtf_timeframe=signal.mtf_timeframe,
            ltf_timeframe=signal.ltf_timeframe,
            micro_timeframe=signal.micro_timeframe,
            htf_bullish_weight=signal.htf_bullish_weight,
            mtf_weight_recontainment=signal.mtf_weight_recontainment,
            mtf_weight_reclaim=signal.mtf_weight_reclaim,
            mtf_weight_discount=signal.mtf_weight_discount,
            mtf_weight_equilibrium=signal.mtf_weight_equilibrium,
            ltf_weight_trap_reverse=signal.ltf_weight_trap_reverse,
            ltf_weight_fake_breakdown=signal.ltf_weight_fake_breakdown,
            ltf_weight_reclaim=signal.ltf_weight_reclaim,
            ltf_weight_choch=signal.ltf_weight_choch,
            ltf_weight_bos=signal.ltf_weight_bos,
            cross_frame_alignment_bonus=signal.cross_frame_alignment_bonus,
            discount_zone_bonus=signal.discount_zone_bonus,
            equilibrium_zone_bonus=signal.equilibrium_zone_bonus,
            compression_bonus=signal.compression_bonus,
            displacement_bonus=signal.displacement_bonus,
            regime_market_permission_strong_threshold=signal.regime_market_permission_strong_threshold,
            regime_sector_permission_strong_threshold=signal.regime_sector_permission_strong_threshold,
            regime_permission_strong_bonus=signal.regime_permission_strong_bonus,
            regime_permission_supportive_bonus=signal.regime_permission_supportive_bonus,
            sector_strength_bonus_strong=signal.sector_strength_bonus_strong,
            sector_strength_bonus_neutral=signal.sector_strength_bonus_neutral,
            sector_strength_bonus_weak=signal.sector_strength_bonus_weak,
            sector_strength_bonus_unknown=signal.sector_strength_bonus_unknown,
            max_event_risk_soft_penalty=signal.max_event_risk_soft_penalty,
        )

    def build_ranking_engine_config(self):
        from doctrine_engine.ranking.models import RankingEngineConfig

        ranking = self.doctrine.ranking
        return RankingEngineConfig(
            config_version=ranking.config_version,
            top_threshold=ranking.top_threshold,
            high_threshold=ranking.high_threshold,
            medium_threshold=ranking.medium_threshold,
            min_rr_for_positive_rank=ranking.min_rr_for_positive_rank,
            strong_rr1_threshold=ranking.strong_rr1_threshold,
            strong_rr2_threshold=ranking.strong_rr2_threshold,
            min_risk_distance=ranking.min_risk_distance,
            grade_weight_a_plus=ranking.grade_weight_a_plus,
            grade_weight_a=ranking.grade_weight_a,
            grade_weight_b=ranking.grade_weight_b,
            confidence_multiplier=ranking.confidence_multiplier,
            setup_weight_recontainment=ranking.setup_weight_recontainment,
            setup_weight_reclaim=ranking.setup_weight_reclaim,
            setup_weight_discount=ranking.setup_weight_discount,
            setup_weight_equilibrium=ranking.setup_weight_equilibrium,
            entry_weight_confirmation=ranking.entry_weight_confirmation,
            entry_weight_base=ranking.entry_weight_base,
            entry_weight_aggressive=ranking.entry_weight_aggressive,
            regime_bonus_bullish_trend=ranking.regime_bonus_bullish_trend,
            regime_bonus_weak_drift=ranking.regime_bonus_weak_drift,
            regime_penalty_chop=ranking.regime_penalty_chop,
            regime_penalty_high_vol_expansion=ranking.regime_penalty_high_vol_expansion,
            sector_bonus_strong=ranking.sector_bonus_strong,
            sector_penalty_weak=ranking.sector_penalty_weak,
            market_permission_multiplier=ranking.market_permission_multiplier,
            sector_permission_multiplier=ranking.sector_permission_multiplier,
            rr1_bonus_strong=ranking.rr1_bonus_strong,
            rr1_bonus_positive=ranking.rr1_bonus_positive,
            rr1_penalty_weak=ranking.rr1_penalty_weak,
            rr2_bonus_strong=ranking.rr2_bonus_strong,
            confirmation_entry_bonus=ranking.confirmation_entry_bonus,
            aggressive_entry_penalty=ranking.aggressive_entry_penalty,
            trail_structural_bonus=ranking.trail_structural_bonus,
            partial_coverage_penalty=ranking.partial_coverage_penalty,
        )

    def build_alert_workflow_config(self):
        from doctrine_engine.alerts.workflow import AlertWorkflowConfig

        return AlertWorkflowConfig(
            cooldown_minutes=self.alert_cooldown_minutes,
            sendable_grades=self.doctrine.alert.sendable_grades,
            suppress_event_risk_blocked=self.doctrine.alert.suppress_event_risk_blocked,
        )

    def build_runner_config(self):
        from doctrine_engine.runner.models import RunnerConfig, TimeframeConfig, UniverseSelectionConfig

        runner = self.doctrine.runner
        return RunnerConfig(
            config_version=runner.config_version,
            run_mode=runner.run_mode,
            fail_fast=runner.fail_fast,
            continue_on_symbol_error=runner.continue_on_symbol_error,
            max_symbol_failures_before_abort=runner.max_symbol_failures_before_abort,
            external_read_retry_attempts=runner.external_read_retry_attempts,
            external_read_retry_backoff_ms=runner.external_read_retry_backoff_ms,
            universe=UniverseSelectionConfig(max_symbols_per_run=self.polygon_universe_refresh_limit),
            timeframes=TimeframeConfig(
                htf=runner.htf_timeframe,
                mtf=runner.mtf_timeframe,
                ltf=runner.ltf_timeframe,
                micro=runner.micro_timeframe,
            ),
            require_micro_confirmation=runner.require_micro_confirmation,
            enable_ranking=runner.enable_ranking,
            enable_alert_workflow=runner.enable_alert_workflow,
            enable_snapshot_requests=runner.enable_snapshot_requests,
            alert_cooldown_minutes=self.alert_cooldown_minutes,
            signal_engine=self.build_signal_engine_config(),
            ranking_engine=self.build_ranking_engine_config(),
            alert_workflow=self.build_alert_workflow_config(),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    from doctrine_engine.product.operator_config import load_operator_settings_overrides

    settings = Settings()
    overrides = load_operator_settings_overrides()
    explicit_env = {key.upper() for key in os.environ}
    env_names = {
        "database_url": "SDE_DATABASE_URL",
        "polygon_api_key": "SDE_POLYGON_API_KEY",
        "telegram_enabled": "SDE_TELEGRAM_ENABLED",
        "telegram_bot_token": "SDE_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "SDE_TELEGRAM_CHAT_ID",
        "run_interval_seconds": "SDE_RUN_INTERVAL_SECONDS",
        "auto_start_runtime": "SDE_AUTO_START_RUNTIME",
        "delayed_data_wording_mode": "SDE_DELAYED_DATA_WORDING_MODE",
        "operator_state_db_path": "SDE_OPERATOR_STATE_DB_PATH",
        "paper_trading_mode": "SDE_PAPER_TRADING_MODE",
    }
    for field_name, env_name in env_names.items():
        if env_name in explicit_env:
            continue
        if field_name in overrides:
            setattr(settings, field_name, overrides[field_name])
    settings._resolve_local_paths()
    return settings
