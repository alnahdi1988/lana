# 1. Daily use: launcher and dashboard

1. Double-click [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs).
2. Wait for the launcher window to open.
3. Click `Start System`.
4. Confirm:
   - `Engine = RUNNING`
   - `Web = RUNNING`
5. Click `Open Dashboard`.
6. Use `Run Once Now` whenever you want an immediate refresh cycle.
7. Use the dashboard and Telegram together:
   - Telegram for sendable alerts
   - dashboard for review, suppressed setups, lifecycle status, and error visibility
8. Use `Restart System` after changing runtime settings.
9. Use `Stop System` when you want to stop the background engine loop. The dashboard may remain available even when the background engine is stopped.

## Source of truth

- the dashboard is the full operational truth
- Telegram is the sendable-alert delivery surface only
- `Trades` and symbol detail are the source for lifecycle tracking state

## What to do when Telegram is quiet

- no Telegram alert does not mean no setup existed
- suppressed setups still matter
- check `Alerts` and `Trades`
- review latest run status and latest `known_at`

# 2. What each dashboard page means

## Overview

Use this as the main health page.

It shows:
- engine, web, and `Run Once` state
- latest run result
- recent runs
- latest symbol outcomes
- generated alerts
- suppressed alerts
- tracked trades
- recent errors
- latest `known_at`
- current Telegram activity

## Runs

Use this to review each completed run.

It shows:
- run status
- start and finish time
- how many symbols were processed
- how many were skipped or failed
- how many signals and trade plans were produced
- how many alerts were sendable, sent, or failed

## Symbols

Use this to see the latest outcome for each ticker from the most recent run.

It shows:
- ticker
- status
- stage reached
- signal
- ranking tier
- alert state
- setup state
- reason codes
- micro state
- Telegram status
- current tracked-trade outcome
- error message if one exists

## Alerts

Use this as the full alert history page.

It shows:
- sent alerts
- suppressed alerts
- duplicate-blocked alerts
- cooldown-blocked alerts
- upgraded alerts
- full trade plan details
- suppression reason
- reason codes
- regime, sector, and event-risk context
- micro-state details
- Telegram result
- current lifecycle outcome

## Trades

Use this to review all qualifying tracked setups.

It shows:
- the trade idea that qualified
- entry, invalidation, and targets
- current lifecycle state
- first barrier reached
- bars tracked
- MFE and MAE
- whether TP2 or invalidation happened first

This page is for follow-through and review, not for sending orders.

## Errors

Use this to see operator-visible problems.

It shows:
- recent errors
- grouped by stage
- grouped by ticker
- timestamps and messages

## Settings

Use this for operator settings and transport checks.

It lets you:
- review current settings
- save operator settings
- restart the system if required
- send a labeled Telegram test message
- review validation status for database, ops store, Polygon, and Telegram

# 3. What each Telegram state means

## Alert states

### `NEW`

A new sendable alert. This is the first active alert for that setup family inside the current rules.

### `UPGRADED`

A sendable update to an existing setup. This means the setup improved enough to send a fresh operator alert.

### `SUPPRESSED`

A real setup existed, but the system intentionally did not send it to Telegram. It still appears in the dashboard and can still be lifecycle-tracked.

### `DUPLICATE_BLOCKED`

The setup matched an already-sent or already-known signal closely enough that the system treated it as a duplicate and did not send it.

### `COOLDOWN_BLOCKED`

The setup was inside the cooldown window, so the system did not send it even though the idea family was recognized.

## Telegram transport states

### `SENT`

Telegram accepted the message.

### `NOT_SENT`

The system intentionally did not send a trading alert. This is normal for suppressed or blocked outcomes.

### `FAILED`

The system tried to send a Telegram message and Telegram did not accept it.

### `SKIPPED_DISABLED`

Telegram sending is turned off in settings.

### `SKIPPED_UNCONFIGURED`

Telegram sending is enabled in principle, but the Telegram destination is not configured correctly.

# 4. Actionable vs suppressed vs informational

## Actionable

Treat a setup as actionable when:
- it is a sendable trade idea
- it has a complete plan
- you can see entry, invalidation, TP1, TP2, timestamps, context, and reason codes
- the setup is still acceptable when you review it manually

Actionable does not mean guaranteed. You still decide whether it is too stale or no longer usable when you see it.

## Suppressed

Treat a setup as suppressed when:
- the doctrine setup exists
- the trade plan exists
- the system intentionally did not send it
- the dashboard still shows the full object

Suppressed setups are first-class review objects. They matter for later review and lifecycle tracking even when no Telegram trading alert was sent.

## Informational

Treat these as informational:
- run status
- latest symbol outcomes
- Telegram test messages
- tracked-trade progress
- recent errors
- validation messages

Informational items help you understand the system, but they are not trade ideas by themselves.

## How to judge whether a setup is stale when I review it

- compare your review time to `known_at`
- use `signal_timestamp` to understand when the setup happened in market time
- use `known_at` to understand when the system could know it on delayed data
- review the entry zone and invalidation before acting
- if price has already moved far beyond the entry zone or invalidation before you review it, treat it as stale
- if your review happens well after `known_at` and current price action no longer fits the displayed entry zone and invalidation structure, treat it as stale

# 5. How lifecycle/open-trade tracking works in plain language

When a qualifying long setup gets a valid trade plan, the system starts tracking it as a trade idea over time.

This means:
- the idea is stored as a tracked trade
- it remains tracked even if the Telegram alert is suppressed
- later bars are checked to see what happened after the setup
- the trade can stay open as `PENDING` until enough later price movement exists

As more bars arrive, the system updates:
- whether the setup succeeded
- whether TP2 was reached
- whether invalidation happened first
- which barrier was hit first
- how much favorable and adverse movement occurred

Plain language meaning:
- `PENDING` means the trade idea is still being tracked or not yet resolved
- a later closed status means the system has enough later movement to label the result

# 6. What normal system behavior looks like

Normal behavior includes:
- the launcher opens normally
- `Start System` changes the engine to `RUNNING`
- `Open Dashboard` opens the local dashboard
- the web page stays reachable
- `Run Once Now` starts, runs, and returns to idle
- latest run information updates after a completed cycle
- skipped symbols appear as skipped, not failed
- suppressed setups still show full trade details in the dashboard
- tracked trades show lifecycle state such as `PENDING`
- Telegram test send from `Settings` arrives as a clearly labeled test message
- `known_at` moves forward as fresh delayed data is processed

# 7. What abnormal behavior looks like and when I should report it

Report it if any of these happen:
- the launcher opens but the dashboard never becomes reachable
- `Engine` or `Web` state is stuck in the wrong condition
- `Run Once` stays busy and does not return to idle after 2 minutes
- the dashboard stops updating and `known_at` stays old for too long
- Telegram test messages fail repeatedly
- the `Errors` page shows repeated provider or system failures
- a setup appears without enough trade detail to understand entry, invalidation, and targets
- a suppressed setup appears in one page but is missing from `Alerts`, `Trades`, or symbol detail
- tracked trades disappear or stop showing lifecycle state
- the same idea shows conflicting values across pages

Do not report normal suppression by itself. Report only when the system becomes unclear, stuck, inconsistent, or repeatedly failing.

Most normal runs finish in about 10-20 seconds. If `Run Once` is still not back to idle after 2 minutes, treat it as stuck and report it.

# 8. One-page daily operating checklist

1. Open the launcher.
2. Confirm `Engine = RUNNING`.
3. Confirm `Web = RUNNING`.
4. Open the dashboard.
5. Review `Overview`:
   - latest run status
   - latest `known_at`
   - tracked trades status
   - recent errors
6. Review `Alerts`:
   - sent alerts
   - suppressed alerts
   - suppression reasons
   - Telegram outcome
7. Review `Trades`:
   - `PENDING` trades
   - any newly changed lifecycle state
8. Review `Symbols` for the latest symbol outcomes.
9. Use `Run Once Now` if you want an immediate refresh.
10. If needed, use `Settings` to send a Telegram test message.

# 9. One-page trade review checklist

For any setup you review:

1. Confirm the ticker and setup state.
2. Confirm whether it is `NEW`, `UPGRADED`, `SUPPRESSED`, `DUPLICATE_BLOCKED`, or `COOLDOWN_BLOCKED`.
3. Read the entry type.
4. Read the full entry zone.
5. Read the confirmation level.
6. Read the invalidation level.
7. Read TP1 and TP2.
8. Read `signal_timestamp`.
9. Read `known_at`.
10. Check the reason codes.
11. Check market, sector, and event-risk context.
12. Check the micro-state line.
13. If it is suppressed, read the suppression reason.
14. Check the lifecycle state on `Trades` or symbol detail.
15. Decide whether the setup is still usable at the time you are reviewing it.

# 10. System boundaries

This system:
- finds and reviews long setup ideas
- builds trade plans
- decides whether an alert is sendable or suppressed
- sends Telegram messages for sendable alerts
- keeps a dashboard history of runs, symbols, alerts, trades, and errors
- tracks qualifying setups over time for later outcome review

This system does not:
- place trades
- guarantee a setup is still actionable when you see it
- operate on live data
- replace your manual review
- replace a separate execution or journaling process

Use it as a manual paper-trading workflow tool, not as an execution engine or certainty engine.
