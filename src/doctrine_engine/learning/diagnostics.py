from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json

from doctrine_engine.learning.schemas import FEATURE_SET_VERSION
from doctrine_engine.product.ml_dataset import LifecycleDatasetExporter


@dataclass(frozen=True, slots=True)
class SignalDiagnosisReport:
    generated_at: str
    dataset_version: str
    days: int
    rows_analyzed: int
    setup_distribution: list[dict[str, Any]]
    grade_distribution: list[dict[str, Any]]
    ticker_distribution: list[dict[str, Any]]
    candidate_shadowing: dict[str, Any]
    confidence_ceiling: dict[str, Any]
    headline: str


class SignalDiagnosticsService:
    def __init__(self, *, exporter: LifecycleDatasetExporter) -> None:
        self.exporter = exporter

    def diagnose_signals(self, *, days: int) -> SignalDiagnosisReport:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = [row for row in self.exporter.export_rows() if _dt(row["known_at"]) >= cutoff]
        setup_distribution = _counter_rows(row["setup_state"] for row in rows)
        grade_distribution = _counter_rows(row["grade"] for row in rows)
        ticker_distribution = _counter_rows(row["ticker"] for row in rows)
        confidence_ceiling = self._confidence_ceiling(rows)
        dominant_setup = setup_distribution[0]["value"] if setup_distribution else "NONE"
        average_confidence = confidence_ceiling["average_confidence"]
        headline = (
            f"Recent signals cluster in {dominant_setup} with average confidence {average_confidence:.4f}."
            if rows
            else "No recent lifecycle rows available."
        )
        return SignalDiagnosisReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=FEATURE_SET_VERSION,
            days=days,
            rows_analyzed=len(rows),
            setup_distribution=setup_distribution,
            grade_distribution=grade_distribution,
            ticker_distribution=ticker_distribution,
            candidate_shadowing=self._candidate_shadowing(rows),
            confidence_ceiling=confidence_ceiling,
            headline=headline,
        )

    def trace_ticker(self, *, ticker: str, lookback_days: int) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        rows = [
            row
            for row in self.exporter.export_rows()
            if row["ticker"] == ticker and _dt(row["known_at"]) >= cutoff
        ]
        if not rows:
            return {
                "ticker": ticker,
                "lookback_days": lookback_days,
                "rows_found": 0,
                "message": "No lifecycle rows found for ticker.",
            }
        latest = rows[-1]
        return {
            "ticker": ticker,
            "lookback_days": lookback_days,
            "rows_found": len(rows),
            "signal_timestamp": latest["signal_timestamp"],
            "known_at": latest["known_at"],
            "signal": latest["signal"],
            "grade": latest["grade"],
            "confidence": latest["confidence"],
            "setup_state": latest["setup_state"],
            "internal_mtf_state": latest.get("internal_mtf_state"),
            "candidate_mtf_states": list(latest.get("candidate_mtf_states") or []),
            "ltf_trigger_state": latest.get("ltf_trigger_state"),
            "candidate_ltf_trigger_states": list(latest.get("candidate_ltf_trigger_states") or []),
            "reason_codes": list(latest.get("reason_codes") or []),
            "hard_gates": dict(latest.get("hard_gates") or {}),
            "alert_state": latest.get("alert_state"),
            "suppression_reason": latest.get("suppression_reason"),
            "telegram_sendable": latest.get("telegram_sendable"),
            "outcome_status": latest.get("evaluation_status"),
            "confidence_review": self._confidence_row(latest),
        }

    def write_report(self, payload: dict[str, Any] | SignalDiagnosisReport, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = asdict(payload) if isinstance(payload, SignalDiagnosisReport) else payload
        path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        return path

    def _candidate_shadowing(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        overlapping = [row for row in rows if len(row.get("candidate_mtf_states") or []) > 1]
        reclaim_shadowed = [
            row for row in overlapping
            if row.get("setup_state") == "BULLISH_RECLAIM"
            and any(state != "BULLISH_RECLAIM" for state in row.get("candidate_mtf_states") or [])
        ]
        return {
            "overlap_rows": len(overlapping),
            "reclaim_rows_with_alternate_candidates": len(reclaim_shadowed),
            "top_overlap_patterns": _counter_rows(
                " > ".join(row.get("candidate_mtf_states") or ["NONE"])
                for row in overlapping
            ),
        }

    def _confidence_ceiling(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "average_confidence": 0.0,
                "max_confidence": 0.0,
                "rows_reaching_a": 0,
                "rows_reaching_a_plus": 0,
                "rows_below_a": 0,
                "average_gap_to_a": 0.0,
                "average_gap_to_a_plus": 0.0,
                "common_missing_boosts": [],
            }
        confidences = [float(row["confidence"]) for row in rows]
        missing_boosts = Counter()
        for row in rows:
            review = self._confidence_row(row)
            missing_boosts.update(review["missing_boosts"])
        return {
            "average_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "rows_reaching_a": sum(1 for value in confidences if value >= 0.80),
            "rows_reaching_a_plus": sum(1 for value in confidences if value >= 0.90),
            "rows_below_a": sum(1 for value in confidences if value < 0.80),
            "average_gap_to_a": sum(max(0.0, 0.80 - value) for value in confidences) / len(confidences),
            "average_gap_to_a_plus": sum(max(0.0, 0.90 - value) for value in confidences) / len(confidences),
            "common_missing_boosts": [
                {"value": value, "count": count}
                for value, count in missing_boosts.most_common(5)
            ],
        }

    def _confidence_row(self, row: dict[str, Any]) -> dict[str, Any]:
        components = dict(row.get("confidence_components") or {})
        numeric_components = {key: float(value) for key, value in components.items()} if components else {}
        missing_boosts: list[str] = []
        if row.get("setup_state") != "RECONTAINMENT_CONFIRMED":
            missing_boosts.append("higher_mtf_state")
        if row.get("ltf_trigger_state") not in {"TRAP_REVERSE_BULLISH", "FAKE_BREAKDOWN_REVERSAL"}:
            missing_boosts.append("stronger_ltf_trigger")
        if not row.get("cross_frame_aligned"):
            missing_boosts.append("cross_frame_alignment")
        if (row.get("market_regime") or "") not in {"BULLISH_TREND", "WEAK_DRIFT"}:
            missing_boosts.append("supportive_market_regime")
        if row.get("sector_regime") != "SECTOR_STRONG":
            missing_boosts.append("strong_sector_regime")
        if not components:
            missing_boosts.append("exact_confidence_components_not_persisted")
        return {
            "components": numeric_components,
            "gap_to_a": max(0.0, 0.80 - float(row["confidence"])),
            "gap_to_a_plus": max(0.0, 0.90 - float(row["confidence"])),
            "missing_boosts": missing_boosts,
        }


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _counter_rows(values) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in Counter(values).most_common()]


__all__ = ["SignalDiagnosisReport", "SignalDiagnosticsService"]
