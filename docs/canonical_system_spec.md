# Canonical System Spec

## Purpose

This document normalizes the final intended system from:

- `Discussions/Discussion 1 .md`
- `Discussions/Discussion 2.md`

Later repeated intent overrides earlier brainstorming. Optional ideas stay optional unless later promoted to required operator or ML scope.

## Required System

### Core trading system

- U.S. stocks only.
- Universe constrained to liquid names with last price between `$5` and `$50`.
- Doctrine remains deterministic.
- Signal engine returns only `LONG` or `NONE`.
- Trade plans are built only for valid `LONG` signals.
- Multi-timeframe doctrine uses `4H`, `1H`, `15M`, with optional `5M` micro context.

### Doctrine outputs

- Structure logic must cover swings, BOS, CHOCH, protected highs/lows, active range, equilibrium, premium/discount, reclaim, displacement, recontainment, fake breakdown, trap reverse, and compression.
- The signal engine must map doctrine evidence to explicit setup states.
- Setup-state selection must be precedence-driven and explainable.
- A ticker failing one setup family must still be evaluated for the remaining valid setup families.

### Operator system

- Launcher and dashboard are the normal operating surface.
- Dashboard is the full operational truth.
- Telegram is the sendable-alert delivery surface only.
- `Trades` and symbol detail are the source of lifecycle state.
- Suppressed setups are first-class operator objects and must remain reviewable.

### Lifecycle system

- Every qualifying setup with a valid trade plan becomes a tracked lifecycle event.
- Lifecycle persistence is independent of Telegram sendability.
- Each qualifying setup creates:
  - `Signal`
  - `TradePlan`
  - `Outcome`
- Outcome progression must update during normal runs.

### ML system

- ML is required for full system completion.
- Doctrine remains the signal generator; ML ranks or calibrates doctrine-valid setups.
- The system must provide:
  - stable training dataset export
  - feature/label integrity
  - baseline model training
  - walk-forward validation
  - model version tracking
  - promotion/governance rules
  - retraining/reporting workflow

## Optional System

- Chart snapshot generation for alerts.
- Chart images attached to Telegram or dashboard, as long as absence does not break operator use.

## Superseded Intent

- Short-side trading is superseded by the later long-only policy.
- Telegram as the sole source of truth is superseded by the later dashboard-first operator model.
- Snapshot service as a blocking dependency is superseded by the later optional/non-blocking framing.
