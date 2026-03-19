# Signal Logic Audit 2026-03-19

## Scope

- Audited `src/doctrine_engine/engines/signal_engine.py`
- Audited `src/doctrine_engine/engines/models.py`
- Audited `src/doctrine_engine/runner/pipeline.py`
- Audited `src/doctrine_engine/engines/*.py`
- Queried PostgreSQL `bars`, `features`, and `signals`

## Summary

The signal engine was not stubbed and it was not returning a fixed hardcoded state. The real defect was a setup-state shortcut in [`src/doctrine_engine/engines/signal_engine.py:264`](D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py#L264): generic `BULLISH_RECLAIM` classification ran before the more specific location-aware `DISCOUNT_RESPONSE` and `EQUILIBRIUM_HOLD` branches.

That precedence collapsed valid 1H discount and equilibrium setups into `BULLISH_RECLAIM` even when the persisted phase-2 feature data already contained the required pattern and zone context.

## Findings

### 1. MTF classification shortcut found

- File: [`src/doctrine_engine/engines/signal_engine.py:277`](D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py#L277)
- Issue: `_determine_internal_mtf_state()` checked `bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}` before checking discount/equilibrium setup context.
- Effect:
  - Discount reclaim bars were emitted as `BULLISH_RECLAIM` instead of `DISCOUNT_RESPONSE`.
  - Equilibrium reclaim bars were emitted as `BULLISH_RECLAIM` instead of `EQUILIBRIUM_HOLD`.
  - Historical `signals` rows in the DB show this collapse: `BULLISH_RECLAIM x 65`, no other setup states.

### 2. No stubbed engine or pipeline logic found

- Audited files contained no `TODO`, `FIXME`, `NotImplemented`, placeholder, or stub logic in the signal/runner pipeline paths requested.
- `models.py`, `runner/pipeline.py`, `pattern_engine.py`, `zone_engine.py`, `structure_engine.py`, and `trade_plan_engine.py` all use real state/data inputs.

### 3. No DB ingestion gap found for target setup ingredients

- `bars` contains raw OHLCV and timing fields only. Target setup components are not expected there.
- `features` stores structure/zone/pattern outputs in `values` JSON. This is the authoritative source for:
  - recontainment status
  - bullish reclaim status
  - fake breakdown status
  - zone location
  - equilibrium and range levels

Observed DB evidence on `1H` features:

- `PATTERN_ENGINE` rows exist: `2138`
- `ZONE_ENGINE` rows exist: `2138`
- `STRUCTURE_ENGINE` rows exist: `2138`
- Example persisted statuses:
  - `recontainment = CANDIDATE/ACTIVE/INVALIDATED` all present
  - `zone_location = DISCOUNT/PREMIUM/EQUILIBRIUM` all present

Historical signal rows were the problem, not missing feature ingestion:

- `signals.setup_state = BULLISH_RECLAIM`: `65`

## Fix Applied

### File changed

- [`src/doctrine_engine/engines/signal_engine.py:264`](D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py#L264)

### Old behavior

```python
if mtf_pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}:
    return "RECONTAINMENT_CANDIDATE"
if mtf_pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
    return "BULLISH_RECLAIM"
if discount-context:
    return "DISCOUNT_RESPONSE"
if equilibrium-context:
    return "EQUILIBRIUM_HOLD"
```

### New behavior

```python
if mtf_pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}:
    return "RECONTAINMENT_CANDIDATE"
if discount-context:
    return "DISCOUNT_RESPONSE"
if equilibrium-context:
    return "EQUILIBRIUM_HOLD"
if mtf_pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
    return "BULLISH_RECLAIM"
```

### Implementation detail

- Added explicit helper methods:
  - `_is_discount_response()`
  - `_is_equilibrium_hold()`
- This makes precedence intentional and easier to audit.

## Test Coverage Added

- [`tests/engines/test_signal_engine_bias_and_setup.py:287`](D:\Doctrine\structure-doctrine-engine\tests\engines\test_signal_engine_bias_and_setup.py#L287)
  - `test_discount_response_takes_precedence_over_generic_bullish_reclaim`
- [`tests/engines/test_signal_engine_bias_and_setup.py:311`](D:\Doctrine\structure-doctrine-engine\tests\engines\test_signal_engine_bias_and_setup.py#L311)
  - `test_equilibrium_hold_takes_precedence_over_generic_bullish_reclaim`

These tests fail if the engine regresses to reclaim-first classification.

## Reachability After Fix

Using the revised precedence against persisted `1H` phase-2 features:

| Revised state | Count |
|---|---:|
| `DISCOUNT_RESPONSE` | 922 |
| `RECONTAINMENT_CANDIDATE` | 55 |
| `EQUILIBRIUM_HOLD` | 55 |

Using the revised precedence against the historical `signals` table's own `1H` source bars:

| Revised state | Count |
|---|---:|
| `DISCOUNT_RESPONSE` | 65 |

Interpretation:

- `RECONTAINMENT_CANDIDATE` is reachable.
- `DISCOUNT_RESPONSE` is reachable and was previously being collapsed into `BULLISH_RECLAIM`.
- `EQUILIBRIUM_HOLD` is reachable.
- Historical `signals` rows are not automatically rewritten; a new pipeline run is required to persist new setup states.

## Data Gaps

No missing DB fields were found that block these three setup states.

Notes:

- `bars` does not contain setup-state columns by design.
- `features` stores the needed inputs inside `values` JSON, and those values are populated.
- No additional ingestion work is required for `recontainment`, discount zone, or equilibrium zone support.

## Verification

- `python -m pytest tests/ -q -x`
  - Result: `215 passed`
- `python scripts/doctrine_control_review.py pipeline-integrity --json`
  - Result: healthy

