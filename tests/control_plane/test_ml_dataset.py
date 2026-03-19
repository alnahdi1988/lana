from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import json
import uuid

from doctrine_engine.product.ml_dataset import DATASET_VERSION, LifecycleDatasetExporter


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.added = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement):
        return _Result(self.rows)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        return None

    def refresh(self, value):
        return None


def _row():
    signal_id = uuid.uuid4()
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    signal = SimpleNamespace(
        id=signal_id,
        symbol_id=symbol_id,
        signal_timestamp=ts,
        known_at=ts,
        signal=SimpleNamespace(value="LONG"),
        confidence=Decimal("0.7400"),
        grade=SimpleNamespace(value="B"),
        bias_htf=SimpleNamespace(value="BULLISH"),
        setup_state="BULLISH_RECLAIM",
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        event_risk_blocked=True,
        extensible_context={
            "market_regime": "CHOP",
            "sector_regime": "SECTOR_NEUTRAL",
            "event_risk_class": "NO_EVENT_RISK",
            "micro_state": "AVAILABLE_NOT_USED",
            "micro_present": True,
            "micro_trigger_state": "LTF_BULLISH_RECLAIM",
            "micro_used_for_confirmation": False,
            "alert_state": "SUPPRESSED",
            "suppression_reason": "GRADE_NOT_SENDABLE",
            "telegram_sendable": False,
            "run_id": "run-1",
        },
    )
    trade_plan = SimpleNamespace(
        entry_type=SimpleNamespace(value="AGGRESSIVE"),
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5000"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("11.2000"),
        tp2=Decimal("12.0000"),
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
    )
    outcome = SimpleNamespace(
        evaluation_status=SimpleNamespace(value="PENDING"),
        evaluation_start=ts,
        evaluation_end=None,
        tracked_until=None,
        bars_tracked=0,
        first_barrier=None,
        success_label=None,
        tp2_label=None,
        invalidated_first=None,
        mfe_pct=None,
        mae_pct=None,
        bars_to_tp1=None,
        extensible_context={
            "tracking_timeframe": "15M",
            "time_barrier_bars": 20,
            "entry_reference_mode": "ENTRY_ZONE_MIDPOINT",
        },
    )
    return signal, trade_plan, outcome, "TEST"


def test_export_rows_preserves_suppressed_setup_and_lifecycle_fields() -> None:
    session = _Session([_row()])
    exporter = LifecycleDatasetExporter(session_factory=lambda: session)

    rows = exporter.export_rows()

    assert len(rows) == 1
    row = rows[0]
    assert row["dataset_version"] == DATASET_VERSION
    assert row["ticker"] == "TEST"
    assert row["setup_state"] == "BULLISH_RECLAIM"
    assert row["event_risk_blocked"] is True
    assert row["alert_state"] == "SUPPRESSED"
    assert row["suppression_reason"] == "GRADE_NOT_SENDABLE"
    assert row["evaluation_status"] == "PENDING"
    assert row["signal_timestamp"] == "2026-03-11T10:15:00+00:00"
    assert row["known_at"] == "2026-03-11T10:15:00+00:00"
    assert row["entry_zone_low"] == "10.0000"
    assert row["tp1"] == "11.2000"


def test_export_json_writes_dataset_and_summary(tmp_path: Path) -> None:
    session = _Session([_row()])
    exporter = LifecycleDatasetExporter(session_factory=lambda: session)
    output_path = tmp_path / "dataset.json"

    summary = exporter.export_json(output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert summary.dataset_version == DATASET_VERSION
    assert summary.total_rows == 1
    assert summary.pending_rows == 1
    assert summary.finalized_rows == 0
