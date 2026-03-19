# ML Operations Runbook

## Scope

This runbook describes the current operating sequence for the first live Doctrine ML slice.

## Required sequence

1. Review lifecycle coverage with `doctrine ml dataset-summary`.
2. Export dataset if needed with `doctrine ml export-dataset --output ...`.
3. Run baseline training for a fixed training window with `doctrine ml train-baseline`.
4. Run walk-forward validation on the next unseen window with `doctrine ml validate-baseline`.
5. Promote only a validated model version with `doctrine ml promote --model-version ...`.
6. Retrain and validate a fresh lineage with `doctrine ml retrain-baseline`.
7. Generate a stored report with `doctrine ml validation-report --model-version ... --output ...`.
8. Review current and recent versions with `doctrine ml compare-models` and `doctrine ml model-status`.
9. Read a recommendation with `doctrine ml recommend-promotion --model-version ...`.

## Current repo status

- Steps 1 through 9 are implemented for the baseline manual-governed ML path.
- Rollback remains manual by design in v1.
- If `score-latest` encounters an incompatible legacy artifact, it now rejects that artifact explicitly and uses the newest compatible validated/trained model instead.

## Go-live rule

Do not claim ML overrides doctrine. The live contract remains: doctrine produces valid setups, ML ranks and governs valid setups, and promotion/rollback stay operator-controlled in v1.
Do not claim full ML closure until the currently promoted live model passes the recommendation gate in the current runtime.
