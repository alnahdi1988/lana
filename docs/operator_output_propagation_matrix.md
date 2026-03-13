# Operator Output Propagation Matrix

This matrix tracks the operator-facing fields across the final product path:

`SignalEngineResult -> TradePlanEngineResult -> AlertDecisionPayload -> TelegramRenderer -> SQLite ops state -> operator web UI`

| Field | Signal Result | Trade Plan | Alert Payload | Telegram | SQLite Ops | Web UI | Disposition |
|---|---|---|---|---|---|---|---|
| `signal` | source | - | copied | rendered | persisted via `symbol_runs` | shown in latest symbols | survives |
| `confidence` | source | - | copied | rendered | not stored in alerts table | not shown | intentionally dropped after payload |
| `grade` | source | - | copied | rendered | persisted via prior alert state only | not shown | intentionally dropped after payload |
| `setup_state` | source | source dependency | copied | rendered | persisted | shown | survives |
| `entry_type` | - | source | copied | rendered | persisted | shown | survives |
| `entry_zone_low` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `entry_zone_high` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `confirmation_level` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `invalidation_level` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `tp1` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `tp2` | - | source | copied | rendered | not stored | not shown | intentionally dropped after render |
| `signal_timestamp` | source | source dependency | copied | rendered | persisted | shown in preview | survives |
| `known_at` | source | preserved | copied | rendered | persisted | shown in preview | survives |
| `reason_codes` | source | - | copied exactly | rendered exactly | persisted as JSON | shown in preview | survives |
| `market_regime` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `sector_regime` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `event_risk_class` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `micro_state` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `micro_present` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `micro_trigger_state` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `micro_used_for_confirmation` | extensible_context | - | copied | rendered | persisted | shown | survives |
| `alert_decision` | - | - | `alert_state` | rendered by prefix/content | persisted | shown | survives |
| `suppression_reason` | - | - | result metadata | not rendered | persisted | shown | intentionally transformed into persisted/UI-only field |
| `telegram_status` | - | - | - | transport result only | persisted | shown | survives in ops layer |
| `telegram_error` | - | - | - | transport result only | persisted | shown | survives in ops layer |
| duplicate/cooldown/upgrade lineage | - | - | family/fingerprint in result | not rendered | persisted in prior alert state | partially visible through alert state history | intentionally transformed |

## Silent-drop result

No active silent-drop bug remains for operator-critical fields.

Known intentional drops:
- raw confidence/grade after the alert payload boundary in persisted ops rows
- raw trade-plan numeric levels after rendered message unless later added to ops rows

Those are product choices, not propagation bugs.
