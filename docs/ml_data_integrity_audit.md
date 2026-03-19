# ML Data Integrity Audit

## Current state

The repo now has the data foundation required to start ML safely, but it does not yet have a live trainer, validation loop, or retraining job.

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
| Automated ML integrity runner exists | No dedicated audit command currently verifies the full lifecycle dataset end to end | No live runner found in `src/` | MISSING | Add a repeatable integrity review command using the exporter |
| Model training pipeline exists | No trainer implementation in `src/` | No trainer code found; `model_runs` schema only | MISSING | Build baseline trainer |
| Walk-forward validation exists | No validation implementation in `src/` | No validator code found | MISSING | Build validation pipeline |
| Model governance and promotion rules exist | `model_runs` table can store metadata, but no governance logic exists | `src/doctrine_engine/db/models/learning.py` only | MISSING | Add promotion and rollback rules |

## Readiness judgment

- **Manual-trading lifecycle readiness:** strong
- **ML dataset readiness:** usable
- **ML system completeness:** incomplete

The data foundation is good enough to support a baseline model. The missing work is the actual learning, validation, and governance stack.
