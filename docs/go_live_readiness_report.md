# Go-Live Readiness Report

## Current judgment

- **Manual-trading operator system:** ready, subject to normal regression discipline
- **Full discussion-defined normalized required scope:** not yet clean enough to claim complete

## What is live

- Doctrine signal and trade-plan pipeline
- Launcher and dashboard operator flow
- Telegram sendability workflow
- Suppressed setup review surfaces
- Lifecycle tracking and outcome progression
- ML dataset export foundation
- Baseline ML training, validation, retraining, scoring, reporting, recommendation, comparison, and manual promotion
- Operator-facing ML status on the dashboard/settings surfaces

## Current ML governance gap

- The currently promoted model `976501d665bd` is still `RECOMMEND_REJECT` because its validation window is single-class.
- That promoted artifact was built under sklearn `1.8.0`, while the current runtime is sklearn `1.6.1`.
- `doctrine ml score-latest` is operational because it now rejects incompatible artifacts explicitly and scores with the newest compatible validated/trained model instead.
- Full closure should not be claimed until a current-runtime model is both governance-clean and promoted.

## What does not block manual-trading go-live

- Manual rollback remains the v1 governance rule.
- Chart snapshots remain optional and are outside required scope.
- Model quality is constrained by current market/label distribution, not by missing platform plumbing.
