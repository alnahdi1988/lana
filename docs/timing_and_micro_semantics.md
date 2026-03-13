# Signal Timing, Delayed-Data Policy, and Micro-State Semantics

## signal_timestamp vs known_at

Every signal carries two timestamps. They are different and both matter.

| Field | Meaning | Example |
|---|---|---|
| `signal_timestamp` | The bar that triggered the signal — the market event that caused the engine to fire | 15:45 bar closes, reclaim confirmed |
| `known_at` | When the system actually had that data available — always lagged by Polygon's 15-minute delayed feed | 16:00 — data became known at close + 15m |

**Why this separation matters:**

The engine is honest about when data was known. A signal triggered at 15:45 cannot be acted on until the data is received at 16:00. The `known_at` field captures this. Any backtesting, replay, or latency analysis must use `known_at`, not `signal_timestamp`, as the actionable timestamp.

`known_at` is computed as `max(known_at)` across all consumed data sources (HTF bar, MTF bar, LTF bar, micro bar if used, regime data, event risk data, sector data, universe snapshot). It represents the latest moment any input to the signal was received — the earliest point the operator could have acted on the full picture.

## Delayed-Data Wording Policy

Every Telegram alert ends with:

```
Data: Polygon delayed 15m. Operator workflow alert only, not live execution.
```

This line is mandatory and must never be removed. The reasons:

1. **Polygon free/starter tier** delivers data with a 15-minute delay. The engine has no live feed.
2. **Operator workflow only** — this system produces triage alerts for human review, not execution orders. No broker API, no auto-execution.
3. **Legal/clarity** — anyone reading the alert must understand the data is not real-time.

The wording is hardcoded in `TelegramRenderer.render` and tested in `tests/alerts/test_telegram_renderer.py`.

## The Four Micro States

The 5-minute timeframe (`micro`) is optional context. Its state is always tracked, regardless of whether it was used for a gate.

| State | Condition | What it means |
|---|---|---|
| `NOT_REQUESTED` | `require_micro_confirmation=False` AND `timeframes.micro=None` | Config never asked for 5M data. Micro played no role whatsoever. |
| `REQUESTED_UNAVAILABLE` | Config requested 5M (either for context or confirmation), but DB returned no rows | 5M was wanted but missing. Signal was evaluated without it. |
| `AVAILABLE_NOT_USED` | 5M data was present, config requested it as context, but `require_micro_confirmation=False` | 5M was loaded and evaluated, but did not gate the signal. |
| `AVAILABLE_USED` | 5M data was present AND `require_micro_confirmation=True` | 5M trigger state was a hard gate — signal could not fire without it. |

### Propagation chain

```
SignalEngineConfig
  ├── micro_context_requested = (require_micro_confirmation OR timeframes.micro is not None)
  └── require_micro_confirmation

SignalEngine.evaluate
  → extensible_context["micro_state"]       ← one of the 4 states above
  → extensible_context["micro_present"]     ← bool: was 5M data in the input?
  → extensible_context["micro_trigger_state"]  ← LTF_BULLISH_RECLAIM, etc. or None
  → extensible_context["micro_used_for_confirmation"]  ← bool

AlertWorkflow.evaluate
  → AlertDecisionPayload.micro_state
  → AlertDecisionPayload.micro_present
  → AlertDecisionPayload.micro_trigger_state
  → AlertDecisionPayload.micro_used_for_confirmation

TelegramRenderer.render
  → "Micro: state=... | present=... | trigger=... | used_for_confirmation=..."

OperationalStateStore.record_alert_event
  → alerts.micro_state (TEXT column)
  → alerts.micro_present (INTEGER 0/1)
  → alerts.micro_trigger_state (TEXT)
  → alerts.micro_used_for_confirmation (INTEGER 0/1)

Operator web panel (/index)
  → micro_state, micro_present, micro_trigger, micro_used_confirm columns in alert tables
```

### Current production config

From `DoctrineProductApp.build_runner_config()`:

```python
timeframes = TimeframeConfig(micro="5M")
require_micro_confirmation = False
```

This means: 5M data is loaded and evaluated (`micro_context_requested=True`), but does not gate the signal (`require_micro_confirmation=False`). When 5M is present, `micro_state = AVAILABLE_NOT_USED`.
