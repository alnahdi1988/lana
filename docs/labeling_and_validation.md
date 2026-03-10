# Labeling and Validation

## 1. Purpose

This document defines how signal outcomes are measured and how the ranking model is validated.

The goal is to learn from real signal outcomes honestly.

---

## 2. Core principle

Every `LONG` signal becomes a tracked event.

The system must measure what happened after the signal, not what could have happened in hindsight.

---

## 3. Outcome tracking fields

For every signal, track:

- signal timestamp
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

---

## 4. Labeling method

Use triple-barrier logic.

### Barriers
- profit barrier
- loss barrier
- time barrier

A label should be assigned when one of these occurs first:
- TP1 / TP2 hit
- invalidation hit
- time window expires

---

## 5. Required labels

Minimum labels:

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

---

## 6. Validation rules

Model validation must be time-aware.

Use:
- walk-forward validation
- purged time-series cross-validation where possible
- out-of-time forward testing
- embargo periods if labels overlap heavily

Do not use random train/test splits.

---

## 7. Baseline comparison

Before promoting any ranking model, compare against:
- deterministic doctrine-only baseline
- prior promoted model

A model should only be promoted if it improves on unseen data.

---

## 8. Reporting metrics

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

---

## 9. Drift detection

The system must detect performance deterioration over time.

Drift checks should compare:
- recent performance vs historical baseline
- setup family performance
- regime-specific performance
- confidence calibration drift

---

## 10. Final rule

No ML model should override doctrine logic.
It only ranks doctrine-valid setups based on learned outcome quality.
