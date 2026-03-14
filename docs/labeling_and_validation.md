# Labeling and Validation

## 1. Purpose

This document defines how doctrine-qualified setup outcomes are measured and how the ranking model is validated.

The goal is to learn from real setup outcomes honestly.

## 2. Core principle

Every doctrine-qualified `LONG` setup becomes a tracked trade.

Implemented qualifying contract:
- `signal == LONG`
- trade plan successfully built
- independent of Telegram sendability

Not tracked as open trades:
- `NONE` signals
- skipped trade-plan failures where no valid executable plan exists

## 3. Outcome tracking fields

For every tracked trade, persist:
- signal timestamp
- known_at
- entry zone
- invalidation level
- TP1
- TP2
- bars tracked
- max favorable excursion (MFE)
- max adverse excursion (MAE)
- whether TP1 was hit
- whether TP2 was hit
- whether invalidation was hit first
- time to follow-through

## 4. Labeling method

Use triple-barrier logic.

### Barriers
- profit barrier
- loss barrier
- time barrier

Labels are assigned when one occurs first:
- TP1 / TP2 hit
- invalidation hit
- time window expires

## 5. Required labels

### success_label
- `1` if TP1 is hit before invalidation
- `0` otherwise

### tp2_label
- `1` if TP2 is hit before invalidation
- `0` otherwise

### invalidated_first
- `true` if invalidation is reached before TP1

### mfe_pct
Maximum favorable excursion in percentage terms.

### mae_pct
Maximum adverse excursion in percentage terms.

### bars_to_tp1
Bars required to hit TP1 if successful.

## 6. Persistence split

### PostgreSQL doctrine truth

Used for:
- `signals`
- `trade_plans`
- `outcomes`

This is the training / doctrine lifecycle store.

### SQLite operator truth

Used for:
- runs
- symbol outcomes
- alert history
- operator events
- Telegram results

This is the operator review store.

Telegram `SENT` vs `NOT_SENT` must not gate PostgreSQL trade tracking.

## 7. Validation rules

Model validation must remain time-aware.

Use:
- walk-forward validation
- purged time-series cross-validation where possible
- out-of-time forward testing
- embargo periods if labels overlap heavily

Do not use random train/test splits.

## 8. Baseline comparison

Before promoting any ranking model, compare against:
- deterministic doctrine-only baseline
- prior promoted model

A model should only be promoted if it improves on unseen data.

## 9. Reporting metrics

At minimum, report:
- sample size
- TP1 hit rate
- TP2 hit rate
- invalidation-first rate
- average MFE
- average MAE
- expectancy proxy
- median bars to follow-through
- performance by regime
- performance by setup type
- performance by grade

## 10. Final rule

No ML model should override doctrine logic.

ML only ranks or learns from doctrine-valid setups that already passed the qualifying contract.
