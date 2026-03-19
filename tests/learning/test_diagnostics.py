from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from doctrine_engine.db.models.signals import Signal
from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.diagnostics import SignalDiagnosticsService
from doctrine_engine.learning.trace_backfill import SignalTraceBackfiller


class _Exporter:
    def __init__(self, rows):
        self.rows = rows

    def export_rows(self, limit=None, newest_first=False):
        rows = list(reversed(self.rows)) if newest_first else list(self.rows)
        if limit is None:
            return rows
        return rows[:limit]


def _row(
    *,
    ticker: str,
    setup_state: str,
    grade: str,
    confidence: str,
    known_at: datetime,
    candidate_mtf_states: list[str],
    internal_mtf_state: str,
    success_label: bool | None = None,
):
    signal_id = uuid.uuid4()
    return {
        "signal_id": str(signal_id),
        "ticker": ticker,
        "signal_timestamp": known_at.isoformat(),
        "known_at": known_at.isoformat(),
        "signal": "LONG",
        "confidence": confidence,
        "grade": grade,
        "bias_htf": "BULLISH",
        "setup_state": setup_state,
        "reason_codes": ["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        "internal_mtf_state": internal_mtf_state,
        "candidate_mtf_states": candidate_mtf_states,
        "ltf_trigger_state": "LTF_BULLISH_RECLAIM",
        "candidate_ltf_trigger_states": ["LTF_BULLISH_RECLAIM", "LTF_BULLISH_BOS"],
        "cross_frame_aligned": True,
        "hard_gates": {"confidence_threshold": float(confidence) >= 0.70},
        "confidence_components": {"htf_bias": "0.2000", "mtf_state": "0.2000"},
        "market_regime": "CHOP",
        "sector_regime": "SECTOR_NEUTRAL",
        "event_risk_class": "NO_EVENT_RISK",
        "micro_state": "AVAILABLE_NOT_USED",
        "micro_present": True,
        "micro_used_for_confirmation": False,
        "event_risk_blocked": False,
        "telegram_sendable": grade in {"A", "A+"},
        "alert_state": "SUPPRESSED" if grade == "B" else "NEW",
        "suppression_reason": "GRADE_NOT_SENDABLE" if grade == "B" else None,
        "entry_type": "AGGRESSIVE",
        "entry_zone_low": "10.0000",
        "entry_zone_high": "10.5000",
        "confirmation_level": "10.8000",
        "invalidation_level": "9.8000",
        "tp1": "11.2000",
        "tp2": "12.0000",
        "bars_tracked": 5,
        "evaluation_status": "FINALIZED" if success_label is not None else "PENDING",
        "success_label": success_label,
        "tp2_label": False if success_label is not None else None,
        "invalidated_first": False if success_label is not None else None,
        "mfe_pct": "4.1000" if success_label is not None else None,
        "mae_pct": "1.1000" if success_label is not None else None,
    }


def test_signal_diagnostics_reports_setup_distribution_and_shadowing() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        _row(
            ticker="VG",
            setup_state="BULLISH_RECLAIM",
            grade="B",
            confidence="0.7300",
            known_at=now - timedelta(hours=1),
            candidate_mtf_states=["DISCOUNT_RESPONSE", "BULLISH_RECLAIM"],
            internal_mtf_state="DISCOUNT_RESPONSE",
            success_label=True,
        ),
        _row(
            ticker="ONDS",
            setup_state="BULLISH_RECLAIM",
            grade="B",
            confidence="0.7200",
            known_at=now - timedelta(hours=2),
            candidate_mtf_states=["BULLISH_RECLAIM"],
            internal_mtf_state="BULLISH_RECLAIM",
            success_label=False,
        ),
    ]
    service = SignalDiagnosticsService(exporter=_Exporter(rows))

    report = service.diagnose_signals(days=1)

    assert report.rows_analyzed == 2
    assert report.setup_distribution[0] == {"value": "BULLISH_RECLAIM", "count": 2}
    assert report.candidate_shadowing["overlap_rows"] == 1
    assert report.confidence_ceiling["rows_below_a"] == 2


def test_trace_ticker_returns_full_latest_path() -> None:
    now = datetime.now(timezone.utc)
    row = _row(
        ticker="VG",
        setup_state="BULLISH_RECLAIM",
        grade="B",
        confidence="0.7300",
        known_at=now - timedelta(hours=1),
        candidate_mtf_states=["DISCOUNT_RESPONSE", "BULLISH_RECLAIM"],
        internal_mtf_state="DISCOUNT_RESPONSE",
    )
    service = SignalDiagnosticsService(exporter=_Exporter([row]))

    result = service.trace_ticker(ticker="VG", lookback_days=1)

    assert result["ticker"] == "VG"
    assert result["rows_found"] == 1
    assert result["candidate_mtf_states"] == ["DISCOUNT_RESPONSE", "BULLISH_RECLAIM"]
    assert "higher_mtf_state" in result["confidence_review"]["missing_boosts"]


def test_learning_dataset_summary_counts_pending_and_finalized() -> None:
    now = datetime.now(timezone.utc)
    exporter = _Exporter(
        [
            _row(
                ticker="VG",
                setup_state="BULLISH_RECLAIM",
                grade="B",
                confidence="0.7300",
                known_at=now - timedelta(hours=1),
                candidate_mtf_states=["BULLISH_RECLAIM"],
                internal_mtf_state="BULLISH_RECLAIM",
                success_label=True,
            ),
            _row(
                ticker="ONDS",
                setup_state="DISCOUNT_RESPONSE",
                grade="A",
                confidence="0.8100",
                known_at=now - timedelta(hours=2),
                candidate_mtf_states=["DISCOUNT_RESPONSE", "BULLISH_RECLAIM"],
                internal_mtf_state="DISCOUNT_RESPONSE",
                success_label=None,
            ),
        ]
    )
    dataset = LifecycleLearningDataset(exporter=exporter)

    summary = dataset.summary()

    assert summary.total_rows == 2
    assert summary.finalized_rows == 1
    assert summary.pending_rows == 1
    assert summary.labeled_rows == 1


def test_trace_backfill_populates_missing_candidates_and_components() -> None:
    known_at = datetime.now(timezone.utc)
    signal = Signal(
        id=uuid.uuid4(),
        symbol_id=uuid.uuid4(),
        universe_snapshot_id=None,
        signal_timestamp=known_at,
        known_at=known_at,
        htf_bar_timestamp=known_at,
        mtf_bar_timestamp=known_at,
        ltf_bar_timestamp=known_at,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.7000"),
        grade="B",
        bias_htf="BULLISH",
        setup_state="BULLISH_RECLAIM",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={
            "internal_mtf_state": "BULLISH_RECLAIM",
            "ltf_trigger_state": "LTF_BULLISH_RECLAIM",
            "cross_frame_aligned": True,
            "regime_snapshot": {"allows_longs": True},
            "sector_snapshot": {"sector_strength": "STRONG"},
            "event_risk_snapshot": {"blocked": False},
        },
    )
    backfiller = SignalTraceBackfiller(session_factory=lambda: None)  # type: ignore[arg-type]

    changed = backfiller._backfill_signal(signal)

    assert changed is True
    assert signal.extensible_context["candidate_mtf_states"] == ["BULLISH_RECLAIM"]
    assert signal.extensible_context["candidate_ltf_trigger_states"] == ["LTF_BULLISH_RECLAIM"]
    assert signal.extensible_context["confidence_components"]["htf_bias"] == "0.20"
    assert signal.extensible_context["trace_backfilled"] is True
