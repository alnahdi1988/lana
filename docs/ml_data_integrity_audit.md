# ML Data Integrity Audit

## Current state

The repo now has the data foundation and the first live ML slice required to train, validate, and promote a baseline ranking model safely.

## Integrity rows

| Requirement | Current truth | Proof | Status | Gap |
|---|---|---|---|---|
| Every qualifying setup creates `Signal` | Implemented in doctrine lifecycle store | `src/doctrine_engine/product/doctrine_tracking.py`, `tests/product/test_doctrine_tracking.py` | DONE | None |
| Every qualifying setup creates `TradePlan` | Implemented in doctrine lifecycle store | Same as above | DONE | None |
| Every qualifying setup creates `Outcome` | Implemented and backfilled when missing | Same as above | DONE | None |
| Suppressed qualifying setups remain in lifecycle history | Implemented and test-backed | `tests/product/test_doctrine_tracking.py`, `tests/product/test_service.py` | DONE | None |
| Duplicate lifecycle rows are blocked | Unique signal constraint plus app-level dedup by `(symbol_id, signal_timestamp)` | `src/doctrine_engine/db/models/signals.py`, `src/doctrine_engine/product/doctrine_tracking.py` | DONE | None |
| Point-in-time timestamps are preserved | Dataset export and lifecycle rows include `signal_timestamp`, `known_at`, trade-plan timestamps, and tracking timestamps | `src/doctrine_engine/product/ml_dataset.py`, delayed-data tests | DONE | None |
| Feature/label export exists | New lifecycle dataset exporter produces joined signal/trade-plan/outcome rows with operator and lifecycle fields | `src/doctrine_engine/product/ml_dataset.py`, `tests/control_plane/test_ml_dataset.py` | DONE | None |
| Automated ML integrity runner exists | Dataset integrity and coverage are now available through `doctrine ml dataset-summary` and deterministic learning export | `src/doctrine_engine/learning/dataset.py`, `src/doctrine_engine/product/cli.py` | DONE | None |
| Model training pipeline exists | Baseline trainer writes artifacts and `model_runs` records | `src/doctrine_engine/learning/train.py`, `src/doctrine_engine/learning/registry.py` | DONE | None |
| Walk-forward validation exists | Validation command trains chronologically, validates on the next window, and records metrics | `src/doctrine_engine/learning/validate.py`, `src/doctrine_engine/product/cli.py` | DONE | None |
| Model governance and promotion rules exist | Manual promotion uses validated `model_runs` rows and demotes prior promoted versions | `src/doctrine_engine/learning/promote.py`, `src/doctrine_engine/learning/registry.py` | DONE | None |

## Readiness judgment

- **Manual-trading lifecycle readiness:** strong
- **ML dataset readiness:** usable
- **ML system completeness:** baseline training, validation, retraining, reporting, comparison, recommendation, and manual promotion are live

The data foundation is live and operating as the basis for the current baseline model workflow. Further ML work is now refinement, not missing platform plumbing.
