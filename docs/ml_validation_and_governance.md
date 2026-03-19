# ML Validation and Governance

## Purpose

Define the non-negotiable controls for promoting ML in Doctrine Engine.

## Required controls

- Walk-forward validation on unseen history
- Explicit validation window recorded per model run
- Promotion criteria based on measured validation results
- Rollback criteria when a promoted model underperforms
- Model version traceability in persistence
- Feature-set version traceability in persistence

## Current repo status

- `model_runs` schema can store version, windows, metrics, params, and promotion flags.
- No live validator, promoter, or rollback logic exists.

## Required completion

- Validation command or service produces a repeatable metrics pack.
- Promotion rules are encoded, not manual folklore.
- Ranking can identify which model version produced a score.
- Docs and runtime surfaces do not claim live ML promotion until the validator exists.
