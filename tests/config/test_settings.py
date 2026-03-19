from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal
import uuid

from doctrine_engine.config.settings import Settings
from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.signal_engine import SignalEngine
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    SignalEngineInput,
    SignalEventRiskInput,
    SignalFrameInput,
    SignalRegimeInput,
    SignalSectorContextInput,
    StructureEngineResult,
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)


def _bar(symbol_id: uuid.UUID, timeframe: Timeframe, ts: datetime, close: str) -> EngineBar:
    close_price = Decimal(close)
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=15), close_price, close_price + Decimal("0.2"), close_price - Decimal("0.2"), close_price)


def _structure_result(bar: EngineBar) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=2), bar.bar_timestamp - timedelta(hours=1), Decimal("9.0"), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=1), bar.bar_timestamp - timedelta(minutes=30), Decimal("11.0"), 1),
            SwingPoint("LOW", bar.bar_timestamp - timedelta(minutes=20), bar.bar_timestamp - timedelta(minutes=10), Decimal("9.8"), 2),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(minutes=5), bar.bar_timestamp, Decimal("10.8"), 3),
        ],
        reference_levels=StructureReferenceLevels(Decimal("11.0"), bar.bar_timestamp - timedelta(hours=1), Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), Decimal("10.8"), bar.bar_timestamp - timedelta(minutes=5), None, None, None, None),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("9.8"),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
        active_range_high=Decimal("11.0"),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=[],
    )


def _zone_result(bar: EngineBar, zone_location: str = "DISCOUNT") -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("9.8"),
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
        active_swing_high=Decimal("11.0"),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        range_width=Decimal("1.2"),
        equilibrium=Decimal("10.4"),
        equilibrium_band_low=Decimal("10.34"),
        equilibrium_band_high=Decimal("10.46"),
        zone_location=zone_location,
        distance_from_equilibrium=Decimal("-0.2"),
        distance_from_equilibrium_pct_of_range=Decimal("-0.1667"),
    )


def _strong_pattern(bar: EngineBar) -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult(status="COMPRESSED", criteria_met=["RANGE_VS_ATR"], lookback_bars=5),
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.0"), bar.bar_timestamp - timedelta(minutes=15), Decimal("1.8"), Decimal("0.8")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), None, None, bar.bar_timestamp),
        bullish_fake_breakdown=LifecyclePatternResult("NONE", None, None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("ACTIVE", Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), "BULLISH_CHOCH", bar.bar_timestamp),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=15), Decimal("10.0"), bar.bar_timestamp - timedelta(minutes=5), Decimal("9.8"), Decimal("11.0")),
        events_on_bar=[],
        active_flags=["COMPRESSION", "BULLISH_DISPLACEMENT", "BULLISH_RECLAIM", "BULLISH_TRAP_REVERSE", "RECONTAINMENT_ACTIVE"],
    )


def _signal_input() -> SignalEngineInput:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=[],
        universe_known_at=htf_bar.known_at,
        htf=SignalFrameInput("4H", htf_bar, _structure_result(htf_bar), [_structure_result(htf_bar)], _zone_result(htf_bar, zone_location="DISCOUNT"), _strong_pattern(htf_bar)),
        mtf=SignalFrameInput("1H", mtf_bar, _structure_result(mtf_bar), [_structure_result(mtf_bar)], _zone_result(mtf_bar, zone_location="DISCOUNT"), _strong_pattern(mtf_bar)),
        ltf=SignalFrameInput("15M", ltf_bar, _structure_result(ltf_bar), [_structure_result(ltf_bar)], _zone_result(ltf_bar), _strong_pattern(ltf_bar)),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_bar.known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.02"), [], htf_bar.known_at),
        sector_context=SignalSectorContextInput("STRONG", None, [], htf_bar.known_at),
    )


def test_settings_use_repo_root_for_local_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    settings = Settings(operator_state_db_path=".doctrine/operations.db")

    expected = Path(__file__).resolve().parents[2] / ".doctrine" / "operations.db"
    assert Path(settings.operator_state_db_path) == expected.resolve()


def test_settings_env_file_is_repo_absolute():
    env_file = Settings.model_config.get("env_file")

    assert env_file is not None
    assert Path(str(env_file)).is_absolute()
    assert Path(str(env_file)).name == ".env"


def test_settings_built_signal_engine_uses_overridden_confidence_floor():
    signal_input = _signal_input()
    settings = Settings(doctrine={"signal": {"long_confidence_threshold": "0.82"}})

    result = SignalEngine(settings.build_signal_engine_config()).evaluate(signal_input)

    assert settings.build_signal_engine_config().long_confidence_threshold == Decimal("0.82")
    assert result.signal == "NONE"
