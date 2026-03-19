from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import uuid

import joblib
import pytest

from doctrine_engine.learning.artifact import load_compatible_artifact
from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.features import build_learning_example
from doctrine_engine.learning.predict import BaselineScorer
from doctrine_engine.learning.promote import ModelPromoter
from doctrine_engine.learning.reporting import BaselineRetrainer, ValidationReporter, recommend_from_run
from doctrine_engine.learning.train import BaselineTrainer
from doctrine_engine.learning.validate import BaselineValidator


class _Exporter:
    def __init__(self, rows):
        self.rows = rows

    def export_rows(self, limit=None, newest_first=False):
        rows = list(reversed(self.rows)) if newest_first else list(self.rows)
        if limit is None:
            return rows
        return rows[:limit]


@dataclass
class _Run:
    model_name: str
    feature_set_version: str
    model_version: str
    status: str
    promoted: bool
    promoted_at: datetime | None
    artifact_uri: str | None
    training_window_start: datetime | None
    training_window_end: datetime | None
    validation_window_start: datetime | None
    validation_window_end: datetime | None
    metrics: dict
    params: dict
    notes: str | None
    created_at: datetime


class _Registry:
    def __init__(self) -> None:
        self.rows: list[_Run] = []

    def upsert(self, **kwargs):
        kwargs.setdefault("promoted", False)
        kwargs.setdefault("notes", None)
        kwargs.setdefault("model_name", "baseline_empirical_ranker")
        row = self.get(kwargs["model_version"])
        if row is None:
            row = _Run(created_at=datetime.now(timezone.utc), promoted_at=None, **kwargs)
            self.rows.append(row)
            return row
        row.feature_set_version = kwargs["feature_set_version"]
        row.status = kwargs["status"]
        row.promoted = kwargs["promoted"] or row.promoted
        row.promoted_at = kwargs.get("promoted_at") or row.promoted_at
        row.artifact_uri = kwargs["artifact_uri"] or row.artifact_uri
        row.training_window_start = kwargs["training_window_start"] or row.training_window_start
        row.training_window_end = kwargs["training_window_end"] or row.training_window_end
        row.validation_window_start = kwargs["validation_window_start"] or row.validation_window_start
        row.validation_window_end = kwargs["validation_window_end"] or row.validation_window_end
        row.metrics = {**row.metrics, **kwargs["metrics"]}
        row.params = {**row.params, **kwargs["params"]}
        row.notes = kwargs["notes"] or row.notes
        return row

    def get(self, model_version: str):
        for row in self.rows:
            if row.model_version == model_version:
                return row
        return None

    def latest(self):
        return self.rows[-1] if self.rows else None

    def latest_promoted(self):
        promoted = [row for row in self.rows if row.promoted]
        return promoted[-1] if promoted else None

    def find_by_training_window(self, *, training_window_start, training_window_end):
        for row in reversed(self.rows):
            if row.training_window_start == training_window_start and row.training_window_end == training_window_end:
                return row
        return None

    def recent(self, limit: int = 10):
        return list(reversed(self.rows[-limit:]))

    def promote(self, model_version: str):
        row = self.get(model_version)
        if row is None:
            raise ValueError("Unknown model version")
        if row.status not in {"VALIDATED", "PROMOTED"}:
            raise ValueError("Model version must be VALIDATED before promotion.")
        for item in self.rows:
            if item.promoted and item.model_version != model_version:
                item.promoted = False
                if item.status == "PROMOTED":
                    item.status = "VALIDATED"
        row.promoted = True
        row.promoted_at = datetime.now(timezone.utc)
        row.status = "PROMOTED"
        return row


def _row(index: int, *, success_label: bool | None) -> dict:
    ts = datetime(2026, 3, 10, 10, tzinfo=timezone.utc) + timedelta(hours=index)
    signal_id = uuid.uuid4()
    return {
        "signal_id": str(signal_id),
        "ticker": f"T{index}",
        "signal_timestamp": ts.isoformat(),
        "known_at": ts.isoformat(),
        "signal": "LONG",
        "confidence": "0.8200" if success_label else "0.7300",
        "grade": "A" if success_label else "B",
        "bias_htf": "BULLISH",
        "setup_state": "DISCOUNT_RESPONSE" if success_label else "BULLISH_RECLAIM",
        "reason_codes": ["PRICE_RANGE_VALID"],
        "market_regime": "BULLISH_TREND" if success_label else "CHOP",
        "sector_regime": "SECTOR_STRONG" if success_label else "SECTOR_NEUTRAL",
        "event_risk_class": "NO_EVENT_RISK",
        "micro_state": "AVAILABLE_NOT_USED",
        "micro_present": True,
        "micro_used_for_confirmation": False,
        "event_risk_blocked": False,
        "telegram_sendable": success_label is True,
        "alert_state": "NEW" if success_label else "SUPPRESSED",
        "entry_type": "BASE" if success_label else "AGGRESSIVE",
        "entry_zone_low": "10.0000",
        "entry_zone_high": "10.5000",
        "confirmation_level": "10.8000",
        "invalidation_level": "9.8000",
        "tp1": "11.2000",
        "tp2": "12.0000",
        "bars_tracked": 6,
        "evaluation_status": "FINALIZED" if success_label is not None else "PENDING",
        "success_label": success_label,
        "tp2_label": success_label,
        "invalidated_first": False if success_label is not None else None,
        "mfe_pct": "5.0000" if success_label is not None else None,
        "mae_pct": "1.0000" if success_label is not None else None,
    }


def test_build_learning_example_excludes_free_form_reason_codes() -> None:
    example = build_learning_example(_row(0, success_label=True))
    assert "reason_codes" not in example.features
    assert example.features["setup_state"] == "DISCOUNT_RESPONSE"
    assert example.features["telegram_sendable"] is True
    assert example.features["event_risk_blocked"] is False


def test_baseline_trainer_fails_with_insufficient_labels(tmp_path: Path) -> None:
    dataset = LifecycleLearningDataset(exporter=_Exporter([_row(index, success_label=bool(index % 2)) for index in range(4)]))
    trainer = BaselineTrainer(dataset=dataset, registry=_Registry())

    with pytest.raises(ValueError, match="requires at least 10 finalized labeled rows"):
        trainer.train(
            train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
            train_end=datetime(2026, 3, 11, tzinfo=timezone.utc),
            artifact_dir=tmp_path,
        )


def test_baseline_training_validation_and_promotion_flow(tmp_path: Path) -> None:
    rows = [_row(index, success_label=bool(index % 2)) for index in range(18)]
    dataset = LifecycleLearningDataset(exporter=_Exporter(rows))
    registry = _Registry()

    trainer = BaselineTrainer(dataset=dataset, registry=registry)
    trained = trainer.train(
        train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        train_end=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
        artifact_dir=tmp_path,
    )

    assert Path(trained.artifact_uri).exists()
    assert registry.rows[0].status == "TRAINED"

    validator = BaselineValidator(dataset=dataset, registry=registry)
    validated = validator.validate(
        train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        train_end=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
        validate_start=datetime(2026, 3, 10, 21, tzinfo=timezone.utc),
        validate_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
        artifact_dir=tmp_path,
    )

    assert validated.metrics["validation_row_count"] > 0
    assert len(registry.rows) == 1
    assert registry.rows[0].status == "VALIDATED"

    promoter = ModelPromoter(registry=registry)
    promoted = promoter.promote(model_version=validated.model_version)
    assert promoted.status == "PROMOTED"
    assert promoter.status(limit=1)[0]["promoted"] is True


def test_retraining_report_and_recommendation_flow(tmp_path: Path) -> None:
    rows = [_row(index, success_label=bool(index % 2)) for index in range(18)]
    dataset = LifecycleLearningDataset(exporter=_Exporter(rows))
    registry = _Registry()
    validator = BaselineValidator(dataset=dataset, registry=registry)
    retrainer = BaselineRetrainer(validator=validator)

    record = retrainer.retrain(
        train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        train_end=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
        validate_start=datetime(2026, 3, 10, 21, tzinfo=timezone.utc),
        validate_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
        artifact_dir=tmp_path,
    )

    reporter = ValidationReporter(registry=registry)
    report = reporter.build(model_version=record.model_version)
    output_path = tmp_path / "validation-report.json"
    written = reporter.write(model_version=record.model_version, output_path=output_path)

    assert written == output_path
    assert json.loads(output_path.read_text(encoding="utf-8"))["model_version"] == record.model_version
    assert report["metrics"]["validation_row_count"] > 0
    assert report["recommendation"]["recommendation"] in {"RECOMMEND_PROMOTE", "RECOMMEND_REJECT"}
    assert reporter.compare_models(limit=1)[0]["model_version"] == record.model_version


def test_recommendation_rejects_single_class_validation() -> None:
    row = _Run(
        model_name="baseline_empirical_ranker",
        feature_set_version="lifecycle_v1",
        model_version="v-single-class",
        status="VALIDATED",
        promoted=False,
        promoted_at=None,
        artifact_uri="artifact.joblib",
        training_window_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        training_window_end=datetime(2026, 3, 11, tzinfo=timezone.utc),
        validation_window_start=datetime(2026, 3, 11, tzinfo=timezone.utc),
        validation_window_end=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metrics={
            "validation_row_count": 12,
            "base_rate": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "brier_score": 0.01,
            "roc_auc": None,
            "score_band_expectancy": [{"band": "0.00-0.33", "count": 12}],
            "train_positive_count": 5,
            "train_negative_count": 7,
        },
        params={},
        notes=None,
        created_at=datetime.now(timezone.utc),
    )

    recommendation = recommend_from_run(row)

    assert recommendation.recommendation == "RECOMMEND_REJECT"
    assert "VALIDATION_SINGLE_CLASS" in recommendation.reasons


def test_promoting_new_version_demotes_previous_promoted_version() -> None:
    registry = _Registry()
    first = registry.upsert(
        model_version="v1",
        feature_set_version="lifecycle_v1",
        status="VALIDATED",
        training_window_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        training_window_end=datetime(2026, 3, 11, tzinfo=timezone.utc),
        validation_window_start=datetime(2026, 3, 11, tzinfo=timezone.utc),
        validation_window_end=datetime(2026, 3, 12, tzinfo=timezone.utc),
        artifact_uri="v1.joblib",
        metrics={"validation_row_count": 10},
        params={},
    )
    second = registry.upsert(
        model_version="v2",
        feature_set_version="lifecycle_v1",
        status="VALIDATED",
        training_window_start=datetime(2026, 3, 11, tzinfo=timezone.utc),
        training_window_end=datetime(2026, 3, 12, tzinfo=timezone.utc),
        validation_window_start=datetime(2026, 3, 12, tzinfo=timezone.utc),
        validation_window_end=datetime(2026, 3, 13, tzinfo=timezone.utc),
        artifact_uri="v2.joblib",
        metrics={"validation_row_count": 12},
        params={},
    )
    promoter = ModelPromoter(registry=registry)

    promoter.promote(model_version=first.model_version)
    promoted_second = promoter.promote(model_version=second.model_version)

    assert promoted_second.model_version == "v2"
    assert registry.get("v2").promoted is True
    assert registry.get("v1").promoted is False
    assert registry.get("v1").status == "VALIDATED"


def test_validator_rejects_overlapping_or_reversed_windows(tmp_path: Path) -> None:
    rows = [_row(index, success_label=bool(index % 2)) for index in range(18)]
    dataset = LifecycleLearningDataset(exporter=_Exporter(rows))
    registry = _Registry()
    validator = BaselineValidator(dataset=dataset, registry=registry)

    with pytest.raises(ValueError, match="validate_start > train_end"):
        validator.validate(
            train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
            train_end=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
            validate_start=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
            validate_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
            artifact_dir=tmp_path,
        )

    with pytest.raises(ValueError, match="validate_end > validate_start"):
        validator.validate(
            train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
            train_end=datetime(2026, 3, 10, 20, tzinfo=timezone.utc),
            validate_start=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
            validate_end=datetime(2026, 3, 11, 5, tzinfo=timezone.utc),
            artifact_dir=tmp_path,
        )


def test_load_compatible_artifact_rejects_version_mismatch(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bad-model.joblib"
    joblib.dump(
        {
            "pipeline": object(),
            "feature_columns": [],
            "model_name": "baseline_empirical_ranker",
            "model_version": "bad",
            "feature_set_version": "lifecycle_v1",
            "sklearn_version": "0.0-test",
            "joblib_version": joblib.__version__,
        },
        artifact_path,
    )

    with pytest.raises(ValueError, match="Retrain the model in the current environment"):
        load_compatible_artifact(artifact_path)


def test_score_latest_falls_back_to_newest_compatible_model(tmp_path: Path) -> None:
    rows = [_row(index, success_label=bool(index % 2)) for index in range(18)]
    dataset = LifecycleLearningDataset(exporter=_Exporter(rows))
    registry = _Registry()
    trainer = BaselineTrainer(dataset=dataset, registry=registry)
    compatible = trainer.train(
        train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        train_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
        artifact_dir=tmp_path,
    )
    registry.upsert(
        model_version="legacy-promoted",
        feature_set_version="lifecycle_v1",
        status="PROMOTED",
        training_window_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        training_window_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
        validation_window_start=datetime(2026, 3, 11, 7, tzinfo=timezone.utc),
        validation_window_end=datetime(2026, 3, 11, 12, tzinfo=timezone.utc),
        artifact_uri=str((tmp_path / "legacy.joblib").resolve()),
        metrics={"validation_row_count": 10},
        params={},
        promoted=True,
    )
    joblib.dump(
        {
            "pipeline": object(),
            "feature_columns": [],
            "model_name": "baseline_empirical_ranker",
            "model_version": "legacy-promoted",
            "feature_set_version": "lifecycle_v1",
            "sklearn_version": "0.0-test",
            "joblib_version": joblib.__version__,
        },
        tmp_path / "legacy.joblib",
    )

    scorer = BaselineScorer(dataset=dataset, registry=registry)
    scored = scorer.score_latest(limit=3)

    assert all(row["model_version"] == compatible.model_version for row in scored)


def test_score_latest_uses_most_recent_rows(tmp_path: Path) -> None:
    rows = [_row(index, success_label=bool(index % 2)) for index in range(18)]
    dataset = LifecycleLearningDataset(exporter=_Exporter(rows))
    registry = _Registry()
    trainer = BaselineTrainer(dataset=dataset, registry=registry)
    record = trainer.train(
        train_start=datetime(2026, 3, 10, tzinfo=timezone.utc),
        train_end=datetime(2026, 3, 11, 6, tzinfo=timezone.utc),
        artifact_dir=tmp_path,
    )

    scorer = BaselineScorer(dataset=dataset, registry=registry)
    scored = scorer.score_latest(limit=3, model_version=record.model_version)

    expected_ids = {rows[-1]["signal_id"], rows[-2]["signal_id"], rows[-3]["signal_id"]}
    assert {row["signal_id"] for row in scored} == expected_ids
