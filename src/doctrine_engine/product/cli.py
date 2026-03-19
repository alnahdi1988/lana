from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
import json

import uvicorn

from doctrine_engine.config.settings import get_settings
from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.diagnostics import SignalDiagnosticsService
from doctrine_engine.learning.predict import BaselineScorer
from doctrine_engine.learning.promote import ModelPromoter
from doctrine_engine.learning.reporting import BaselineRetrainer, ValidationReporter
from doctrine_engine.learning.registry import ModelRunRegistry
from doctrine_engine.learning.trace_backfill import SignalTraceBackfiller
from doctrine_engine.learning.train import BaselineTrainer
from doctrine_engine.learning.validate import BaselineValidator
from doctrine_engine.product.ml_dataset import LifecycleDatasetExporter
from doctrine_engine.product.service import DoctrineProductApp


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(prog="doctrine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("once")
    loop_parser = subparsers.add_parser("loop")
    loop_parser.add_argument("--interval-seconds", type=int, default=settings.run_interval_seconds)
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--host", default=settings.web_host)
    web_parser.add_argument("--port", type=int, default=settings.web_port)
    ml_parser = subparsers.add_parser("ml")
    ml_subparsers = ml_parser.add_subparsers(dest="ml_command", required=True)
    diagnose_parser = ml_subparsers.add_parser("diagnose-signals")
    diagnose_parser.add_argument("--days", type=int, default=7)
    diagnose_parser.add_argument("--json-output")
    backfill_parser = ml_subparsers.add_parser("backfill-trace-fields")
    backfill_parser.add_argument("--days", type=int, default=7)
    trace_parser = ml_subparsers.add_parser("trace-ticker")
    trace_parser.add_argument("--ticker", required=True)
    trace_parser.add_argument("--lookback-days", type=int, default=7)
    trace_parser.add_argument("--json-output")
    export_parser = ml_subparsers.add_parser("export-dataset")
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--limit", type=int)
    summary_parser = ml_subparsers.add_parser("dataset-summary")
    summary_parser.add_argument("--limit", type=int)
    train_parser = ml_subparsers.add_parser("train-baseline")
    train_parser.add_argument("--train-start", required=True)
    train_parser.add_argument("--train-end", required=True)
    train_parser.add_argument("--artifact-dir", default=".doctrine/models")
    validate_parser = ml_subparsers.add_parser("validate-baseline")
    validate_parser.add_argument("--train-start", required=True)
    validate_parser.add_argument("--train-end", required=True)
    validate_parser.add_argument("--validate-start", required=True)
    validate_parser.add_argument("--validate-end", required=True)
    validate_parser.add_argument("--artifact-dir", default=".doctrine/models")
    retrain_parser = ml_subparsers.add_parser("retrain-baseline")
    retrain_parser.add_argument("--train-start", required=True)
    retrain_parser.add_argument("--train-end", required=True)
    retrain_parser.add_argument("--validate-start", required=True)
    retrain_parser.add_argument("--validate-end", required=True)
    retrain_parser.add_argument("--artifact-dir", default=".doctrine/models")
    report_parser = ml_subparsers.add_parser("validation-report")
    report_parser.add_argument("--model-version", required=True)
    report_parser.add_argument("--output", required=True)
    compare_parser = ml_subparsers.add_parser("compare-models")
    compare_parser.add_argument("--limit", type=int, default=10)
    recommend_parser = ml_subparsers.add_parser("recommend-promotion")
    recommend_parser.add_argument("--model-version", required=True)
    score_parser = ml_subparsers.add_parser("score-latest")
    score_parser.add_argument("--limit", type=int, default=20)
    score_parser.add_argument("--model-version")
    promote_parser = ml_subparsers.add_parser("promote")
    promote_parser.add_argument("--model-version", required=True)
    status_parser = ml_subparsers.add_parser("model-status")
    status_parser.add_argument("--limit", type=int, default=10)
    subparsers.add_parser("launcher")
    subparsers.add_parser("worker-engine")
    subparsers.add_parser("worker-web")
    subparsers.add_parser("worker-once")
    args = parser.parse_args()

    app = DoctrineProductApp(settings=settings)
    if args.command == "once":
        result = app.run_once()
        logging.getLogger(__name__).info(
            "Run complete: status=%s total_symbols=%s rendered_alerts=%s telegram_sent=%s",
            result.runner_result.run_status,
            result.runner_result.total_symbols,
            result.runner_result.rendered_alerts,
            sum(1 for item in result.transport_results if item.transport_status == "SENT"),
        )
        return
    if args.command == "loop":
        app.run_forever(interval_seconds=args.interval_seconds)
        return
    if args.command == "ml":
        _run_ml_command(app, args)
        return
    if args.command == "launcher":
        from doctrine_engine.product.launcher import run_launcher

        run_launcher()
        return
    if args.command == "worker-engine":
        from doctrine_engine.product.control import run_engine_worker

        run_engine_worker()
        return
    if args.command == "worker-web":
        from doctrine_engine.product.control import run_web_worker

        run_web_worker()
        return
    if args.command == "worker-once":
        from doctrine_engine.product.control import run_once_worker

        run_once_worker()
        return
    uvicorn.run(app.create_operator_app(), host=args.host, port=args.port)


app = main


__all__ = ["app", "main"]


def _run_ml_command(app: DoctrineProductApp, args) -> None:
    exporter = LifecycleDatasetExporter(session_factory=app.session_factory)
    dataset = LifecycleLearningDataset(exporter=exporter)
    registry = ModelRunRegistry(session_factory=app.session_factory)
    if args.ml_command == "diagnose-signals":
        diagnostics = SignalDiagnosticsService(exporter=exporter)
        report = diagnostics.diagnose_signals(days=args.days)
        _emit_json(_to_jsonable(report))
        if args.json_output:
            diagnostics.write_report(report, args.json_output)
        return
    if args.ml_command == "backfill-trace-fields":
        backfiller = SignalTraceBackfiller(session_factory=app.session_factory)
        summary = backfiller.backfill_recent(days=args.days)
        _emit_json(_to_jsonable(summary))
        return
    if args.ml_command == "trace-ticker":
        diagnostics = SignalDiagnosticsService(exporter=exporter)
        report = diagnostics.trace_ticker(ticker=args.ticker, lookback_days=args.lookback_days)
        _emit_json(report)
        if args.json_output:
            diagnostics.write_report(report, args.json_output)
        return
    if args.ml_command == "export-dataset":
        summary = dataset.export_json(args.output, limit=args.limit)
        _emit_json(_to_jsonable(summary))
        return
    if args.ml_command == "dataset-summary":
        summary = dataset.summary(limit=args.limit)
        _emit_json(_to_jsonable(summary))
        return
    if args.ml_command == "train-baseline":
        trainer = BaselineTrainer(dataset=dataset, registry=registry)
        try:
            record = trainer.train(
                train_start=_parse_dt(args.train_start),
                train_end=_parse_dt(args.train_end),
                artifact_dir=args.artifact_dir,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json(_record_to_dict(record))
        return
    if args.ml_command == "validate-baseline":
        validator = BaselineValidator(dataset=dataset, registry=registry)
        try:
            record = validator.validate(
                train_start=_parse_dt(args.train_start),
                train_end=_parse_dt(args.train_end),
                validate_start=_parse_dt(args.validate_start),
                validate_end=_parse_dt(args.validate_end),
                artifact_dir=args.artifact_dir,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json(_record_to_dict(record))
        return
    if args.ml_command == "retrain-baseline":
        retrainer = BaselineRetrainer(validator=BaselineValidator(dataset=dataset, registry=registry))
        try:
            record = retrainer.retrain(
                train_start=_parse_dt(args.train_start),
                train_end=_parse_dt(args.train_end),
                validate_start=_parse_dt(args.validate_start),
                validate_end=_parse_dt(args.validate_end),
                artifact_dir=args.artifact_dir,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json(_record_to_dict(record))
        return
    if args.ml_command == "validation-report":
        reporter = ValidationReporter(registry=registry)
        try:
            output_path = reporter.write(model_version=args.model_version, output_path=args.output)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json({"model_version": args.model_version, "output": str(output_path)})
        return
    if args.ml_command == "compare-models":
        reporter = ValidationReporter(registry=registry)
        _emit_json(reporter.compare_models(limit=args.limit))
        return
    if args.ml_command == "recommend-promotion":
        reporter = ValidationReporter(registry=registry)
        try:
            payload = reporter.build(model_version=args.model_version)["recommendation"]
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json(payload)
        return
    if args.ml_command == "score-latest":
        scorer = BaselineScorer(dataset=dataset, registry=registry)
        _emit_json(scorer.score_latest(limit=args.limit, model_version=args.model_version))
        return
    if args.ml_command == "promote":
        promoter = ModelPromoter(registry=registry)
        try:
            result = promoter.promote(model_version=args.model_version)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        _emit_json(
            {
                "model_version": result.model_version,
                "status": result.status,
                "promoted": result.promoted,
                "promoted_at": result.promoted_at.isoformat() if result.promoted_at else None,
            }
        )
        return
    if args.ml_command == "model-status":
        promoter = ModelPromoter(registry=registry)
        _emit_json(promoter.status(limit=args.limit))
        return
    raise ValueError(f"Unsupported ml command: {args.ml_command}")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _record_to_dict(record) -> dict:
    payload = asdict(record)
    for key in ("training_window_start", "training_window_end", "validation_window_start", "validation_window_end"):
        if payload[key] is not None:
            payload[key] = payload[key].isoformat()
    return payload


def _to_jsonable(value):
    if is_dataclass(value):
        return asdict(value)
    return value


def _emit_json(payload) -> None:
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":  # pragma: no cover - direct module execution
    main()
