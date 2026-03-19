# ML Operations Runbook

## Scope

This runbook describes the intended operating sequence for Doctrine ML once the trainer and validator exist.

## Required sequence

1. Export lifecycle dataset from qualifying setups.
2. Run baseline training for a fixed training window.
3. Run walk-forward validation on the next unseen window.
4. Record the model run with metrics and artifact path.
5. Promote only if the validation gate passes.
6. Keep the previous promoted model available for rollback.

## Current repo status

- Step 1 is available through the lifecycle dataset exporter.
- Steps 2 through 6 are not yet implemented in live code.

## Go-live rule

Do not claim a live ML retraining system until the trainer, validator, and promotion logic are implemented and test-backed.
