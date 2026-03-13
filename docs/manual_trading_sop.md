# Manual Trading SOP

## Purpose

Use the doctrine product as an operator workflow tool. It does not execute trades.

## Alert classes

- **Actionable**
  - `signal = LONG`
  - alert workflow `send = True`
  - Telegram delivered or visible in the operator console
- **Blocked**
  - event-risk blocked
  - non-long signal
  - cooldown/duplicate suppression
- **Informational**
  - rendered preview exists in the operator console
  - not actionable for manual entry

## Staleness rule

- Treat `known_at` as the actionable ceiling.
- Do not interpret `signal_timestamp` as a live execution timestamp.
- If the alert is materially stale relative to your manual review time, ignore it.

## Delayed-data interpretation

- All alerts are delayed-data operator alerts.
- Telegram explicitly says:
  - `Polygon delayed 15m. Operator workflow alert only, not live execution.`

## Micro policy

Current runtime mode:
- `timeframes.micro = "5M"`
- `require_micro_confirmation = False`

Interpretation:
- `NOT_REQUESTED`: 5M played no role
- `REQUESTED_UNAVAILABLE`: 5M was wanted but unavailable
- `AVAILABLE_NOT_USED`: 5M context existed but did not gate the signal
- `AVAILABLE_USED`: 5M gated the signal

## Regime and event-risk handling

- If event risk is blocked, treat the alert as blocked.
- If regime degrades the setup but the alert is still sent, use caution and review the context line in Telegram/web.

## Entry / invalidation / targets

- Use the rendered trade plan exactly as displayed:
  - entry zone
  - confirmation level
  - invalidation level
  - TP1
  - TP2
- Do not invent alternate levels outside the displayed plan.

## Re-entry

- Do not treat repeated alerts as fresh opportunities automatically.
- Check prior alert history in the operator console first.
- Respect duplicate/cooldown/upgrade lineage before acting.

## Daily review

1. Open the operator web console.
2. Check latest run status and recent errors.
3. Review generated and suppressed alerts.
4. Review Telegram send outcomes.
5. For any actionable alert:
   - verify `known_at`
   - verify micro state
   - verify setup state
   - verify invalidation and targets

## Paper-trade logging

For each manually acted-on alert, record externally:
- ticker
- alert time reviewed
- `signal_timestamp`
- `known_at`
- micro state
- entry taken
- stop used
- TP outcome

The doctrine product does not yet manage execution journaling for you.
