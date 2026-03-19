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

- `model_runs` stores version, windows, metrics, params, and promotion flags.
- `doctrine ml validate-baseline` now records a chronological validation metrics pack.
- `doctrine ml promote` now enforces manual promotion of validated model versions only.
- `doctrine ml retrain-baseline`, `validation-report`, `compare-models`, and `recommend-promotion` now complete the CLI-first governance path.
- Rollback remains manual by design in v1: promote a prior validated/promoted version explicitly.

## Required completion

- Validation command or service produces a repeatable metrics pack.
- Promotion rules are encoded, not manual folklore.
- Ranking can identify which model version produced a score.
- Dashboard/runtime surfaces expose the promoted model version and latest validation truth without implying ML overrides doctrine.
