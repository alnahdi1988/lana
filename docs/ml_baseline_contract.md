# ML Baseline Contract

## Purpose

Define the minimum acceptable first ML implementation for Doctrine Engine.

## Required behavior

- Input data comes only from lifecycle-tracked qualifying setups.
- The baseline model ranks doctrine-valid setups; it does not generate new signals.
- The baseline must record:
  - model name
  - model version
  - feature set version
  - training window
  - validation window
  - metrics
  - artifact location

## Required inputs

- Signal fields from `signals`
- Trade geometry from `trade_plans`
- Outcome labels from `outcomes`
- Operator/lifecycle context preserved in `extensible_context`

## Current repo status

- Dataset export foundation exists.
- `lifecycle_v1` includes the governance feature `event_risk_blocked`.
- `model_runs` persistence exists with one canonical row per `(model_name, model_version)`.
- Baseline trainer, validator, retrainer, scorer, reporting, recommendation, comparison, and manual promotion commands now exist in `src/doctrine_engine/learning/` and `src/doctrine_engine/product/cli.py`.
- Scoring rejects incompatible artifacts explicitly and requires retrain in the current runtime when sklearn/joblib versions do not match.

## Acceptance for completion

- A repeatable training command produces an artifact and a `model_runs` row.
- A repeatable validation command produces a metrics pack and a validated `model_runs` row.
- A repeatable retraining command produces a fresh artifact lineage and validated canonical row.
- Validation reporting and promotion recommendation can be generated from stored model metadata.
- A manual promotion command can promote only a validated model version.
- The training record is attributable to a concrete feature set version and time window.
- The output can be consumed by ranking without changing the deterministic doctrine signal path.

Completion of the baseline contract does not by itself imply that the currently promoted live model satisfies governance quality gates.
