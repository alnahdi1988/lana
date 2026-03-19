# Final Acceptance Matrix

| Area | Required status for 100% | Current status | Result |
|---|---|---|---|
| Canonical spec and requirement ledger | Present and reconciled against both discussion files | Implemented in `canonical_system_spec.md` and `requirement_ledger.md` | DONE |
| Doctrine engine and setup-state closure | Deterministic, precedence-driven, overlap-tested | Implemented and audited; candidate-state traceability added | DONE |
| Operator/runtime/manual-trading system | Launcher, dashboard, Telegram, lifecycle, suppressed setups all operator-complete | Implemented and already verified in prior closure docs | DONE |
| Lifecycle persistence and outcome progression | Every qualifying setup tracked with progressing outcomes | Implemented and test-backed | DONE |
| ML dataset/export foundation | Stable joined dataset with point-in-time fields and labels | Implemented in `ml_dataset.py` | DONE |
| Baseline model training | Live trainer with recorded `model_runs` artifacts | Implemented in `src/doctrine_engine/learning/train.py` and CLI | DONE |
| Walk-forward validation | Live validator with stored validation windows and metrics | Implemented in `src/doctrine_engine/learning/validate.py` and CLI | DONE |
| Model governance and promotion | Live promotion/rollback logic and clean promoted-model evidence | Governance commands and canonical `model_runs` rows are implemented, but the current promoted model `976501d665bd` is recommendation-rejected (`VALIDATION_SINGLE_CLASS`) and its artifact is not runtime-compatible with sklearn `1.6.1` | PARTIAL |
| Retraining/reporting workflow | Live retraining and reporting path | Implemented in `src/doctrine_engine/learning/reporting.py` and CLI; current-runtime retrain produced compatible validated model `bd4be90eaaf8` | DONE |
| Live ML scoring path | `doctrine ml score-latest` works in the current runtime | Scoring now rejects incompatible artifacts clearly and falls back to the newest compatible validated/trained model; live scoring currently uses `bd4be90eaaf8` | DONE |

## Acceptance judgment

The repo is **not yet at 100% against the normalized required scope captured in the discussion-defined system ledger**.

Current status:
- required ML platform plumbing exists and is test-backed
- live scoring works in the current runtime
- live governance evidence is still not clean because the currently promoted model is both recommendation-rejected and tied to an older sklearn artifact runtime

The remaining work is narrow:
- retrain and validate a compatible model on a validation window that satisfies the governance recommendation gate
- promote that model only after live evidence supports it
