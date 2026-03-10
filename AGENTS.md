# AGENTS.md

This project builds a **production-grade long-only structural signal platform** for **U.S. stocks** using **delayed Polygon data**.

## Non-negotiable constraints

- U.S. equities only
- Stock price must be between **$5 and $50**
- **LONG signals only**
- No short logic anywhere
- Delayed data must be treated honestly
- The signal engine returns only:
  - `LONG`
  - `NONE`
- The trade plan engine is separate from the signal engine
- No broker execution in v1
- No reinforcement learning
- No replacing doctrine logic with ML
- ML is only for **ranking valid doctrine setups**

## Project philosophy

This system is built in layers:

1. **Universe and data layer**
2. **Structural doctrine engine**
3. **Trade plan engine**
4. **Ranking and learning engine**
5. **Notification and reporting layer**

The doctrine is the source of truth.
The model ranks; it does not invent structure.

## Authority of definitions

All structural terms and behaviors are defined in:

- `docs/doctrine_definitions.md`
- `docs/signal_contract.md`
- `docs/trade_plan_contract.md`

Do not invent alternate definitions unless explicitly instructed.

## Delayed data policy

Polygon data is delayed by 15 minutes.

This means:
- A signal can only be considered known after the delayed bar is available
- No code may assume live intrabar knowledge
- No backtest may use unrealistic same-bar execution assumptions
- Entry logic must reflect delayed awareness

## Signal engine rules

The signal engine must:
- determine HTF bullish context
- determine MTF valid setup
- determine LTF bullish trigger
- require cross-frame alignment
- prefer `NONE` over ambiguity

The signal engine must not:
- decide order size
- place trades
- manage portfolio
- send every technically valid low-quality setup

## Trade plan engine rules

The trade plan engine must:
- output entry zone
- output confirmation level
- output invalidation level
- output TP1 and TP2
- use structure, not arbitrary percentages

## Code quality requirements

- Use Python 3.11+
- Prefer explicit typing
- Prefer deterministic behavior
- Prefer modular services
- Add unit tests for core structural logic
- Add logging
- Add docstrings where useful
- Avoid hidden side effects
- Keep business logic separate from transport / API logic

## Preferred stack

- FastAPI
- PostgreSQL
- TimescaleDB
- Redis
- Celery
- SQLAlchemy
- Alembic
- MLflow
- XGBoost or LightGBM

## Build order

Codex should build in this order:

1. DB schema and migrations
2. Polygon ingestion and universe filtering
3. Structural event engine
4. Zone and pattern engines
5. Regime and event-risk engines
6. Signal engine
7. Trade plan engine
8. Telegram notifier and chart snapshots
9. Outcome tracker and labels
10. ML ranking engine
11. Monitoring, tests, and docs

## Signal policy

Only high-quality alerts should be sent to Telegram.

Signal grades:
- A+
- A
- B
- Ignore

Telegram should only receive:
- A+
- A

## Final instruction

When in doubt:
- choose simpler and more explicit architecture
- prefer `NONE`
- do not overfit
- do not guess structural definitions