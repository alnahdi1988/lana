# Operator Output Propagation Matrix

Active end-to-end path:

`SignalEngineResult -> TradePlanEngineResult -> AlertDecisionPayload -> TelegramRenderer -> SQLite ops state -> PostgreSQL doctrine lifecycle -> operator web UI`

| Field | Signal Result | Trade Plan | Alert Payload | Telegram | SQLite Ops | PostgreSQL Doctrine | Web UI | Disposition |
|---|---|---|---|---|---|---|---|---|
| `signal` | source | dependency | copied | rendered | persisted | persisted | shown | survives |
| `confidence` | source | - | copied | rendered | persisted | persisted | shown | survives |
| `grade` | source | - | copied | rendered | persisted | persisted | shown | survives |
| `setup_state` | source | dependency | copied | rendered | persisted | persisted | shown | survives |
| `entry_type` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `entry_zone_low` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `entry_zone_high` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `confirmation_level` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `invalidation_level` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `tp1` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `tp2` | - | source | copied | rendered | persisted | persisted | shown | survives |
| `signal_timestamp` | source | dependency | copied | rendered | persisted | persisted | shown | survives |
| `known_at` | source | preserved | copied | rendered | persisted | persisted | shown | survives |
| `reason_codes` | source | plan dependency | copied | rendered | persisted | persisted | shown | survives |
| `market_regime` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `sector_regime` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `event_risk_class` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `micro_state` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `micro_present` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `micro_trigger_state` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `micro_used_for_confirmation` | extensible context | - | copied | rendered | persisted | persisted | shown | survives |
| `alert_state` | workflow result | - | source | rendered meaningfully or suppressed | persisted | persisted in signal context | shown | survives |
| `suppression_reason` | workflow result | - | source | not always sent | persisted | persisted in signal context | shown | survives |
| `telegram_status` | transport result | - | - | source | persisted | not primary doctrine field | shown | survives in ops layer |
| `telegram_error` | transport result | - | - | source | persisted | not primary doctrine field | shown | survives in ops layer |
| `telegram_message_id` | transport result | - | - | source | persisted | not primary doctrine field | shown | survives in ops layer |
| duplicate/cooldown/upgrade lineage | prior alert state | - | workflow result | not always sent | persisted in alert row lineage fields / prior alert state | alert state remains reflected in doctrine signal context | shown | survives |
| tracked trade lifecycle | - | - | - | not a Telegram concept | operator events only | `signals` / `trade_plans` / `outcomes` | shown on overview, alerts, trades, symbol detail | survives |

## Result

No operator-critical field is intentionally dropped anymore for qualifying setups.

The remaining split is structural:
- SQLite is the operator-state truth
- PostgreSQL is the doctrine / ML-tracking truth

The dashboard joins both so the operator sees one coherent record.
