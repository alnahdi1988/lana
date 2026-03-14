# Manual Trading SOP

## Scope

Use the doctrine product as an operator workflow tool.

- no broker execution
- no live-bar execution assumptions
- manual paper trading only

## Normal daily use

1. Double-click [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs).
2. In the launcher, click `Start System`.
3. Click `Open Dashboard`.
4. Use `Run Once Now` when you want an immediate cycle.
5. Review Telegram and the dashboard together.

## What counts as actionable

Actionability is determined by the existing alert workflow.

### Sendable

- Telegram message sent
- dashboard alert row shows full trade details
- the same setup is also tracked in PostgreSQL for outcome labeling

### Suppressed

- qualifying doctrine setup exists
- Telegram is intentionally not sent
- dashboard still shows:
  - signal
  - confidence
  - grade
  - setup state
  - entry type
  - entry zone
  - invalidation
  - TP1 / TP2
  - `signal_timestamp`
  - `known_at`
  - reason codes
  - regime / event risk
  - micro-state
  - suppression reason
  - tracked trade status

Suppressed does not mean “not logged.” A suppressed qualifying setup is still recorded for doctrine outcome tracking and ML labels.

## Staleness rule

- `known_at` is the delayed-data ceiling for operator action.
- `signal_timestamp` is not a live execution timestamp.
- If the setup is materially stale at review time, ignore it.

## Micro policy

Current runtime mode:
- `timeframes.micro = "5M"`
- `require_micro_confirmation = False`

Operator meaning:
- `NOT_REQUESTED`: 5M played no role
- `REQUESTED_UNAVAILABLE`: 5M was requested but missing
- `AVAILABLE_NOT_USED`: 5M context existed but did not gate the setup
- `AVAILABLE_USED`: 5M gated the setup

## Entry, invalidation, targets

Use the displayed trade plan exactly as shown:
- entry type
- entry zone
- confirmation level
- invalidation level
- TP1
- TP2

Do not replace the displayed plan with manual levels.

## Duplicate / cooldown / upgraded lineage

Before acting on repeated alerts, check:
- alert history for the ticker
- suppression reason
- prior signal linkage
- tracked trade history

Repeated alert families are not automatically fresh opportunities.

## Telegram interpretation

Telegram is the primary alert surface, but not the only source of truth.

Use the dashboard when:
- Telegram is quiet
- Telegram shows a test-send only
- an alert is suppressed
- you need prior lineage or tracked-trade status

## Dashboard review sequence

### Overview

Confirm:
- engine/web status
- latest run result
- latest `known_at`
- doctrine trades status
- recent errors

### Alerts

Review:
- sendable alerts
- suppressed alerts
- trade details
- Telegram status / error
- suppression reason

### Trades

Review:
- all qualifying tracked setups
- outcome status
- bars tracked
- MFE / MAE
- first barrier

### Symbols

Review:
- per-symbol recent outcomes
- alert history
- tracked trades
- errors

## Telegram test send

From `Settings`, click `Send Telegram Test Message`.

Expected result:
- a clearly labeled operator connectivity message
- persisted `TELEGRAM_TEST_SEND` event in SQLite
- no effect on real doctrine alert workflow decisions

## External journaling

If you manually act on a setup, record externally:
- ticker
- review time
- `signal_timestamp`
- `known_at`
- entry taken
- stop used
- TP outcome

The doctrine product tracks setup outcomes for training labels. It does not replace a manual execution journal.
