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
- `model_runs` persistence exists.
- Baseline trainer implementation does **not** exist yet.

## Acceptance for completion

- A repeatable training command produces an artifact and a `model_runs` row.
- The training record is attributable to a concrete feature set version and time window.
- The output can be consumed by ranking without changing the deterministic doctrine signal path.
