# Victor Handoff: ML Closure and Remaining Governance Blocker

## Scope

This document consolidates the ML closure work completed in the recent audit/fix passes, the live verification that was run, the commits created, and the single remaining blocker preventing full ML governance closure.

Repo:
- `D:\Doctrine\structure-doctrine-engine`

Date:
- `2026-03-20`

## Commits delivered

1. `e3c5c36`
- Added closure spec and ML dataset foundation

2. `502eade`
- Completed ML closure and operator status

3. `0d5238b`
- Fixed ML audit closure blockers

## What was implemented

### 1. Canonical closure/spec artifacts

Created and updated repo-tracked closure documents:
- [D:\Doctrine\structure-doctrine-engine\docs\canonical_system_spec.md](/D:/Doctrine/structure-doctrine-engine/docs/canonical_system_spec.md)
- [D:\Doctrine\structure-doctrine-engine\docs\requirement_ledger.md](/D:/Doctrine/structure-doctrine-engine/docs/requirement_ledger.md)
- [D:\Doctrine\structure-doctrine-engine\docs\doctrine_logic_closure_matrix.md](/D:/Doctrine/structure-doctrine-engine/docs/doctrine_logic_closure_matrix.md)
- [D:\Doctrine\structure-doctrine-engine\docs\runtime_operator_closure_matrix.md](/D:/Doctrine/structure-doctrine-engine/docs/runtime_operator_closure_matrix.md)
- [D:\Doctrine\structure-doctrine-engine\docs\ml_data_integrity_audit.md](/D:/Doctrine/structure-doctrine-engine/docs/ml_data_integrity_audit.md)
- [D:\Doctrine\structure-doctrine-engine\docs\ml_baseline_contract.md](/D:/Doctrine/structure-doctrine-engine/docs/ml_baseline_contract.md)
- [D:\Doctrine\structure-doctrine-engine\docs\ml_validation_and_governance.md](/D:/Doctrine/structure-doctrine-engine/docs/ml_validation_and_governance.md)
- [D:\Doctrine\structure-doctrine-engine\docs\ml_operations_runbook.md](/D:/Doctrine/structure-doctrine-engine/docs/ml_operations_runbook.md)
- [D:\Doctrine\structure-doctrine-engine\docs\final_acceptance_matrix.md](/D:/Doctrine/structure-doctrine-engine/docs/final_acceptance_matrix.md)
- [D:\Doctrine\structure-doctrine-engine\docs\go_live_readiness_report.md](/D:/Doctrine/structure-doctrine-engine/docs/go_live_readiness_report.md)

### 2. Doctrine setup-state visibility and diagnosis

Implemented persisted signal traceability so setup-state selection can be audited:
- candidate MTF states
- candidate LTF trigger states
- confidence components

Key files:
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/engines/signal_engine.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\diagnostics.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/diagnostics.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\trace_backfill.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/trace_backfill.py)

CLI added:
- `python -m doctrine_engine.product.cli ml diagnose-signals --days N`
- `python -m doctrine_engine.product.cli ml trace-ticker --ticker TICKER --lookback-days N`
- `python -m doctrine_engine.product.cli ml backfill-trace-fields --days N`

### 3. ML dataset foundation

Implemented deterministic lifecycle dataset export and feature building for `lifecycle_v1`.

Key files:
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\ml_dataset.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/product/ml_dataset.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\dataset.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/dataset.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\features.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/features.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\schemas.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/schemas.py)

Important integrity fix completed:
- `event_risk_blocked` now exports correctly from lifecycle rows and reaches `LearningExample.features`

### 4. Baseline training / validation / reporting / promotion

Implemented the baseline ML stack:
- training
- validation
- retraining
- scoring
- reporting
- comparison
- recommendation
- manual promotion

Key files:
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\train.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/train.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\validate.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/validate.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\predict.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/predict.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\reporting.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/reporting.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\promote.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/promote.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\registry.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/registry.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\db\models\learning.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/db/models/learning.py)
- [D:\Doctrine\structure-doctrine-engine\alembic\versions\0003_model_run_uniqueness.py](/D:/Doctrine/structure-doctrine-engine/alembic/versions/0003_model_run_uniqueness.py)

CLI added:
- `python -m doctrine_engine.product.cli ml train-baseline ...`
- `python -m doctrine_engine.product.cli ml validate-baseline ...`
- `python -m doctrine_engine.product.cli ml retrain-baseline ...`
- `python -m doctrine_engine.product.cli ml validation-report --model-version ... --output ...`
- `python -m doctrine_engine.product.cli ml compare-models --limit N`
- `python -m doctrine_engine.product.cli ml recommend-promotion --model-version ...`
- `python -m doctrine_engine.product.cli ml promote --model-version ...`
- `python -m doctrine_engine.product.cli ml model-status --limit N`
- `python -m doctrine_engine.product.cli ml score-latest --limit N`

### 5. Score-latest live/runtime fixes

Fixed the live scoring path in two steps:

1. `score-latest` now uses the newest lifecycle rows rather than the oldest rows.
2. Artifact compatibility is now explicit:
   - incompatible sklearn/joblib artifacts fail clearly
   - scorer falls back to the newest compatible validated/trained model when the default promoted artifact is incompatible

Key file:
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\learning\artifact.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/learning/artifact.py)

### 6. Validation window contract

Validation now enforces:
- `train_end > train_start`
- `validate_end > validate_start`
- `validate_start > train_end`

This prevents overlapping or reversed walk-forward windows.

### 7. Dashboard/operator ML status

Added operator-facing ML status to Overview/Settings.

Key files:
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/product/web.py)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\overview.html](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/product/templates/overview.html)
- [D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\settings.html](/D:/Doctrine/structure-doctrine-engine/src/doctrine_engine/product/templates/settings.html)

## Tests added/updated

Key test files:
- [D:\Doctrine\structure-doctrine-engine\tests\control_plane\test_ml_dataset.py](/D:/Doctrine/structure-doctrine-engine/tests/control_plane/test_ml_dataset.py)
- [D:\Doctrine\structure-doctrine-engine\tests\learning\test_diagnostics.py](/D:/Doctrine/structure-doctrine-engine/tests/learning/test_diagnostics.py)
- [D:\Doctrine\structure-doctrine-engine\tests\learning\test_ml_pipeline.py](/D:/Doctrine/structure-doctrine-engine/tests/learning/test_ml_pipeline.py)

Added/covered:
- `event_risk_blocked` feature export integrity
- incompatible artifact handling
- latest-row scoring semantics
- fallback to newest compatible model
- validation window enforcement
- canonical model lifecycle behavior

## Verification run

### Full tests

Command:
```powershell
python -m pytest tests -q
```

Result:
- `246 passed`

### Live ML verification

Commands run:
```powershell
python -m doctrine_engine.product.cli ml dataset-summary
python -m doctrine_engine.product.cli ml diagnose-signals --days 1
python -m doctrine_engine.product.cli ml trace-ticker --ticker VG --lookback-days 1
python -m doctrine_engine.product.cli ml trace-ticker --ticker ONDS --lookback-days 1
python -m doctrine_engine.product.cli ml compare-models --limit 5
python -m doctrine_engine.product.cli ml recommend-promotion --model-version 976501d665bd
python -m doctrine_engine.product.cli ml score-latest --limit 5
python -m doctrine_engine.product.cli ml retrain-baseline --train-start 2026-03-14T00:00:00+03:00 --train-end 2026-03-19T12:00:00+03:00 --validate-start 2026-03-19T12:00:01+03:00 --validate-end 2026-03-19T23:59:59+03:00 --artifact-dir .doctrine/models
python -m doctrine_engine.product.cli ml recommend-promotion --model-version bd4be90eaaf8
python -m doctrine_engine.product.cli ml model-status --limit 5
```

Observed results:
- `dataset-summary` works
- `diagnose-signals --days 1` works
- `trace-ticker VG/ONDS` works
- `compare-models` works
- `score-latest --limit 5` works live
- live scoring now uses compatible model `bd4be90eaaf8`

## Current live diagnosis

Latest live diagnosis over 1 day:
- `31` rows analyzed
- all `31` rows are `BULLISH_RECLAIM`
- all `31` rows are grade `B`
- overlap rows: `0`
- average confidence: about `0.7119`

Interpretation:
- current quiet Telegram behavior is not a transport failure
- it is a real signal/grade distribution issue in the live data

## Remaining blocker preventing full ML governance closure

This is the only remaining open closure gap.

### Current promoted model

Promoted model:
- `976501d665bd`

Current status:
- `PROMOTED`
- `RECOMMEND_REJECT`
- reason: `VALIDATION_SINGLE_CLASS`
- artifact runtime: old sklearn artifact (`1.8.0`) vs current runtime (`1.6.1`)

### Current compatible validated model

New current-runtime model:
- `bd4be90eaaf8`

Current status:
- `VALIDATED`
- compatible with current runtime
- still `RECOMMEND_REJECT`
- reason: `VALIDATION_SINGLE_CLASS`

### Why this cannot be closed yet

The blocker is now the label chronology, not the code.

Current labeled data pattern:
- `2026-03-14`: positives only
- `2026-03-15`: positives only
- `2026-03-18`: negatives only
- `2026-03-19`: negatives only

That means there is currently no valid strictly chronological walk-forward split that gives:
- mixed-class training data
- and then a later mixed-class validation window

So:
- retraining works
- validation works
- recommendation works
- promotion governance works
- but the data does not currently support a `RECOMMEND_PROMOTE` outcome

### Consequence

Full ML governance closure cannot be claimed honestly until a later validation window contains both classes.

## Truthful current status

### Complete
- ML plumbing
- dataset/export integrity
- live scoring
- validation-window enforcement
- artifact compatibility handling
- operator-facing ML status
- honest docs

### Not complete
- a promoted model that is both:
  - runtime-compatible
  - and governance-clean (`RECOMMEND_PROMOTE`)

## Recommended next action for Victor

Do not change code first.

The next required step is operational/data-driven:
1. wait for or generate additional labeled history so a later validation window contains both positive and negative outcomes
2. retrain/validate again in the current runtime on that new mixed-class validation window
3. confirm:
   - `python -m doctrine_engine.product.cli ml recommend-promotion --model-version <new_version>`
   - returns `RECOMMEND_PROMOTE`
4. only then:
   - `python -m doctrine_engine.product.cli ml promote --model-version <new_version>`
5. verify:
   - `python -m doctrine_engine.product.cli ml compare-models --limit 5`
   - `python -m doctrine_engine.product.cli ml model-status --limit 5`
   - `python -m doctrine_engine.product.cli ml recommend-promotion --model-version <new_promoted_version>`
   - `python -m doctrine_engine.product.cli ml score-latest --limit 5`

## Unrelated local residue not included in this work

Still present in the worktree and intentionally not touched:
- `.openclaw/cron/jobs.json`
- `.openclaw/openclaw.json`
- [D:\Doctrine\structure-doctrine-engine\tests\test_openclaw_config.py](/D:/Doctrine/structure-doctrine-engine/tests/test_openclaw_config.py)
- [D:\Doctrine\structure-doctrine-engine\tests\test_doctrine_catalyst_watch.py](/D:/Doctrine/structure-doctrine-engine/tests/test_doctrine_catalyst_watch.py)
- [D:\Doctrine\structure-doctrine-engine\Discussions](/D:/Doctrine/structure-doctrine-engine/Discussions)
