# Doctrine Mission Control

**System:** structure-doctrine-engine
**Timezone:** Asia/Riyadh (UTC+3)
**Last updated:** 2026-03-16
**Source files:** `.openclaw/openclaw.json`, `.openclaw/cron/jobs.json`, `tasks/`

> Local-only file. Excluded from git via `.git/info/exclude`.
> Reflects live workstation state, not committed repo state.
> These are observability contracts, not authority sources.
> No agent has trading authority. No agent may change doctrine definitions.

---

## Team View

| Agent | ID | Primary Model | Fallback | Core Responsibility | Allowed Task Types | Queue Ownership | Can Write Code |
|---|---|---|---|---|---|---|---|
| Victor | `aria-chat` | `anthropic/claude-sonnet-4-6` | `openai/gpt-5.4` | Operator-facing command center. Routes Telegram DMs, dispatches to subagents, signal intelligence, outcome tracking, briefings, approval gate. | Dispatch + signal queries | None (relay) | No |
| ARIA-OPS | `aria-ops` | `openai/gpt-5.4` | `anthropic/claude-sonnet-4-6` | Platform operations. Owns all cron jobs. Monitors health, proposes tasks, emits operator briefings. Read-only on code — edit/write/apply_patch denied. | maintenance, incident, health, ops | All 13 cron jobs | No |
| ARIA-CODE | `aria-code` | `openai-codex/gpt-5.4` | `openai/gpt-5.4`, `anthropic/claude-sonnet-4-6` | Engineering agent. Implements approved tasks. Applies code changes and resolves P0/P1 defects. Activated only after operator approval. | feature, bug, docs, research, maintenance | mc-001 (pending approval) | Yes |

**Routing:** Telegram DM from `8569633077` → aria-chat → subagent dispatch to aria-ops or aria-code.

**Subagent policy:**
- aria-chat may spawn aria-ops and aria-code
- aria-ops and aria-code cannot spawn subagents
- Heartbeat: aria-ops every 15m, aria-chat and aria-code on-demand only

---

## Calendar View

Source: `.openclaw/cron/jobs.json` — 13 jobs, timezone Asia/Riyadh (UTC+3).

| Job | ID | Cron | Schedule (plain) | Days | Owner | Operator-facing |
|---|---|---|---|---|---|---|
| Heartbeat Check | `heartbeat-check` | `*/30 * * * *` | Every 30 min (:00, :30) | Daily | aria-ops | **Silent** |
| Data Freshness Review | `data-freshness-review` | `0 */4 * * *` | Every 4h at :00 (00:00, 04:00, 08:00, 12:00, 16:00, 20:00) | Daily | aria-ops | **Silent** |
| Pipeline Integrity Review | `pipeline-integrity-review` | `15 */4 * * *` | Every 4h at :15 (00:15, 04:15, 08:15 …) | Daily | aria-ops | **Silent** |
| Git Backup | `git-backup` | `0 */2 * * *` | Every 2h at :00 (00:00, 02:00, 04:00 …) | Daily | aria-ops | **Silent** |
| Daily Security Audit | `daily-security-audit` | `0 6 * * *` | 06:00 | Daily | aria-ops | **Telegram** |
| Morning Briefing | `premarket-readiness` | `0 8 * * 1-5` | 08:00 | Mon–Fri | aria-ops | **Telegram** |
| Approval Review | `approval-review` | `0 8,12,16,20 * * 1-5` | 08:00, 12:00, 16:00, 20:00 | Mon–Fri | aria-ops | **Telegram** |
| Market Open Verify | `market-open-verify` | `30 9 * * 1-5` | 09:30 | Mon–Fri | aria-ops | **Telegram** |
| Incident Review | `incident-review` | `15 8,12,16,20 * * 1-5` | 08:15, 12:15, 16:15, 20:15 | Mon–Fri | aria-ops | **Telegram** |
| Evening Review | `eod-report` | `0 17 * * 1-5` | 17:00 | Mon–Fri | aria-ops | **Telegram** |
| Weekly Cron Audit | `weekly-cron-audit` | `0 7 * * 1` | Mon 07:00 | Mon only | aria-ops | **Telegram** |
| Weekly Version Check | `weekly-version-check` | `15 7 * * 1` | Mon 07:15 | Mon only | aria-ops | **Telegram** |
| Weekly Progress | `weekly-progress` | `0 9 * * 1` | Mon 09:00 | Mon only | aria-ops | **Telegram** |

**Silent** = runs silently; Telegram only if anomaly detected.
**Telegram** = always delivers output to operator.

**Monday schedule (today, 2026-03-16):**

| Time (AST) | Job |
|---|---|
| 07:00 | Weekly Cron Audit |
| 07:15 | Weekly Version Check |
| 08:00 | Morning Briefing + Approval Review |
| 08:15 | Incident Review |
| 09:00 | Weekly Progress |
| 09:30 | Market Open Verify |
| 12:00 | Approval Review |
| 12:15 | Incident Review |
| 16:00 | Approval Review |
| 16:15 | Incident Review |
| 17:00 | Evening Review |
| 20:00 | Approval Review |
| 20:15 | Incident Review |

---

## Pipeline View

Eight layers in evaluation order. Each run traverses this chain for every symbol in the universe.
Source: committed code + verified runtime evidence in `docs/project_closure_matrix_final.md`.

---

### Layer 1 — Universe

| | |
|---|---|
| **Purpose** | Select and sync the eligible stock universe before every run |
| **Owner** | `src/doctrine_engine/product/sync.py` → `PolygonSyncService.prepare_run()` |
| **Config** | `service.py → DoctrineProductApp.run_once()` |
| **Persistence** | PostgreSQL — symbols + universe snapshots |
| **Operator surface** | Overview page (run counts), Symbols page (symbol list) |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | Run `23d65c02-6563-46c2-b786-80f4bf373e44` — universe synced, symbols processed |
| **Open incidents** | None |
| **Queue items** | None |
| **Monitored by** | `premarket-readiness` (08:00 Mon–Fri) — checks universe freshness |

---

### Layer 2 — Ingestion

| | |
|---|---|
| **Purpose** | Load delayed OHLCV bars and Phase2 features from PostgreSQL for each symbol |
| **Owner** | `src/doctrine_engine/product/adapters.py` → `DbMarketDataLoader.load()`, `DbPhase2FeatureLoader.load()` |
| **Micro config** | `timeframes=TimeframeConfig(micro="5M")` — requests 5M bars when available |
| **Persistence** | PostgreSQL `bars`, `features` |
| **Operator surface** | Symbols page → `known_at`; Overview → latest `known_at` advances on fresh data |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | SOFI: `phase2.micro present=True`, `signal input micro present=True` (canonical CLAUDE.md fixture) |
| **Open incidents** | None |
| **Queue items** | None |
| **Monitored by** | `data-freshness-review` (every 4h), `premarket-readiness` (08:00 Mon–Fri) |

---

### Layer 3 — Structure

| | |
|---|---|
| **Purpose** | Evaluate HTF structural bias (4H), MTF setup qualification (1H), LTF trigger (15M), micro context (5M) |
| **Owner** | `src/doctrine_engine/engines/signal_engine.py` → `SignalEngine.evaluate()` |
| **Sub-engines** | `structure_engine.py`, `zone_engine.py`, `pattern_engine.py`, `regime/`, `event_risk/` |
| **Required LONG states** | `RECONATINMENT_CONFIRMED`, `BULLISH_RECLAIM`, `DISCOUNT_RESPONSE`, `EQUILIBRIUM_HOLD` |
| **Blocking conditions** | Event-risk block, regime disallow, non-bullish HTF, invalid/premium/chop MTF, missing trigger, confidence below threshold, missing micro when `require_micro_confirmation=True` |
| **Persistence** | PostgreSQL `signals.extensible_context` |
| **Operator surface** | Symbols page → stage reached, reason codes; Alerts page → regime/sector/event-risk context |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | SOFI: micro_state=AVAILABLE_NOT_USED confirmed end-to-end |
| **Open incidents** | None |
| **Queue items** | None |

---

### Layer 4 — Signal

| | |
|---|---|
| **Purpose** | Produce `LONG` or `NONE` with confidence, grade, setup_state, reason codes, micro-state |
| **Owner** | `src/doctrine_engine/engines/signal_engine.py` → `SignalEngine.evaluate()` → `SignalEngineResult` |
| **Output** | `micro_state` (4 states), `micro_present`, `micro_trigger_state`, `micro_used_for_confirmation` |
| **Micro states** | `NOT_REQUESTED` / `REQUESTED_UNAVAILABLE` / `AVAILABLE_NOT_USED` / `AVAILABLE_USED` |
| **Current micro config** | `require_micro_confirmation=False` → produces `AVAILABLE_NOT_USED` when 5M present |
| **Persistence** | PostgreSQL `signals` |
| **Operator surface** | Symbols page → signal, confidence, grade, micro state; Alerts page → full signal context |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | INTC: LONG signal row in PostgreSQL; SOFI: `micro_state=AVAILABLE_NOT_USED` verified |
| **Open incidents** | None |
| **Queue items** | None |

---

### Layer 5 — Trade Plan

| | |
|---|---|
| **Purpose** | Build entry zone, confirmation, invalidation, TP1, TP2, trail mode for qualifying LONG setups |
| **Owner** | `src/doctrine_engine/engines/trade_plan_engine.py` via `src/doctrine_engine/runner/pipeline.py` |
| **Skip policy** | Invalid geometry → symbol skip (not run failure) |
| **Persistence** | PostgreSQL `trade_plans` |
| **Operator surface** | Alerts page → full plan detail; Trades page → entry/invalidation/TP1/TP2 |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | INTC: trade plan row confirmed in PostgreSQL; IREN: graceful skip on invalid geometry confirmed |
| **Open incidents** | None |
| **Queue items** | None |

---

### Layer 6 — Ranking

| | |
|---|---|
| **Purpose** | Rank doctrine-valid signals; assign confidence tier and grade |
| **Owner** | `src/doctrine_engine/ranking/` via `src/doctrine_engine/runner/pipeline.py` |
| **Persistence** | SQLite `symbol_runs` (tier); PostgreSQL `signals` (confidence, grade) |
| **Operator surface** | Symbols page → ranking tier; Runs page → `ranked_symbols` count |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | Latest run: `ranked_symbols=1` confirmed on Symbols page |
| **Open incidents** | None |
| **Queue items** | None |
| **Note** | Ranking persists to operator layer only — intentional per closure matrix |

---

### Layer 7 — Notifier

| | |
|---|---|
| **Purpose** | Decide alert state and deliver qualifying alerts to operator via Telegram |
| **Owner** | `alerts/workflow.py` → `AlertWorkflow.evaluate()` → `alerts/telegram_renderer.py` → `product/clients.py` |
| **Alert states** | `NEW`, `UPGRADED`, `SUPPRESSED`, `DUPLICATE_BLOCKED`, `COOLDOWN_BLOCKED` |
| **Telegram states** | `SENT`, `NOT_SENT`, `FAILED`, `SKIPPED_DISABLED`, `SKIPPED_UNCONFIGURED` |
| **Delayed-data label** | All Telegram alerts include the Polygon +15m disclaimer |
| **Persistence** | SQLite `alerts` — full alert row including micro fields, Telegram result, suppression reason |
| **Operator surface** | Alerts page (full history + suppression reasons); Overview (counts); Symbols page; Telegram |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | `TELEGRAM_TEST_SEND status=SENT` confirmed from Settings page; latest real alert row in SQLite |
| **Open incidents** | None |
| **Queue items** | None |

---

### Layer 8 — Outcomes

| | |
|---|---|
| **Purpose** | Track every qualifying LONG+trade-plan setup over time; update PENDING outcomes from later bars |
| **Owner** | `src/doctrine_engine/product/doctrine_tracking.py` → `DoctrineLifecycleStore` |
| **Key methods** | `record_qualifying_setups()`, `update_pending_outcomes()` |
| **Gating rule** | Telegram sendability does NOT gate lifecycle entry — suppressed setups enter outcomes tracking |
| **Lifecycle states** | `PENDING` → resolved: success / TP2 / invalidation; first barrier wins; MFE/MAE tracked |
| **Persistence** | PostgreSQL `outcomes`; SQLite `operator_events` (summary) |
| **Operator surface** | Trades page → full lifecycle state, first barrier, bars tracked, MFE, MAE; Overview → doctrine cards |
| **Current state** | ✅ OPERATIONAL |
| **Last evidence** | `OUTCOME_TRACKER` operator event confirmed; suppressed setup lifecycle test passing |
| **Open incidents** | None |
| **Queue items** | None |

---

## TASK QUEUE SUMMARY

| Queue | Count | Items |
|---|---|---|
| proposed | 1 | `ops-pipeline-integrity` — pre-market Polygon empty data (auto-resolves at market open) |
| approved | 0 | — |
| in-progress | 0 | — |
| blocked | 0 | — |
| done | 13 | mc-001, task-001–006, ops-backup-recursive-growth, ops-backup-staging-cleanup, ops-backup-failure, incident-backup-20260315, incident-backup-fail-20260316, ops-gateway-watchdog |

