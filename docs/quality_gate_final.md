# Quality Gate — Final Pass — 2026-03-16

## Changes Made

### Fix 1 — P0: tests/test_doctrine_reviews.py — local-only import guard

**File:** `tests/test_doctrine_reviews.py`

**Problem:** The test file was committed to git (HEAD commit 09aa3d7) with hard top-level imports of `doctrine_engine.control_plane` and `doctrine_engine.control_plane.task_queue`. The `src/doctrine_engine/control_plane/` directory is excluded from git via `.git/info/exclude` — it is a local-only operational module that exists only on this workstation. On any clean clone of the repo, pytest collection would fail with ImportError at the point of collecting this file, breaking the entire test suite.

**Fix:** Wrapped the two control_plane imports in a try/except ImportError block. If the import fails, `pytest.skip(allow_module_level=True)` is called, which causes pytest to skip the module gracefully instead of erroring at collection. The tests still pass and run normally on this workstation because the control_plane module is present locally.

**Exact change:**
```python
# Before:
from doctrine_engine.control_plane import doctrine_reviews
from doctrine_engine.control_plane.task_queue import TaskQueue

# After:
import pytest

try:
    from doctrine_engine.control_plane import doctrine_reviews
    from doctrine_engine.control_plane.task_queue import TaskQueue
except ImportError:
    pytest.skip(
        "doctrine_engine.control_plane is a local-only module excluded from git. "
        "These tests only run on workstations that have the control_plane installed.",
        allow_module_level=True,
    )
```

### Fix 2 — P1: python-multipart not installed in environment

**Problem:** `python-multipart>=0.0.9` is declared in `pyproject.toml` under `dependencies` but was not installed in the active virtual environment. FastAPI's form parsing requires this library. Without it, `POST /setup/save` and `POST /settings/save` fail at runtime with `AssertionError: The python-multipart library must be installed to use form parsing.` The test `tests/product/test_web_operator_shell.py::test_setup_flow_redirects_and_saves` was failing for this reason.

**Fix:** Installed the missing dependency: `python -m pip install python-multipart` (installed version 0.0.22). This is not a code change — it is an environment fix. The package is already correctly declared in `pyproject.toml`.

---

## Tests Run

```
tests/test_doctrine_reviews.py — 2 passed (both tests pass with import guard in place)
tests/product/test_web_operator_shell.py::test_setup_flow_redirects_and_saves — 1 passed (after python-multipart install)
Full suite (200 tests, excluding openclaw-specific tests) — 200 passed
```

---

## Traceability Matrix — Final

| Requirement | Real current behavior | File path(s) | Implementation location | Persistence location | Operator surface | Code proof | Test proof | SQLite proof | PostgreSQL proof | Dashboard/web proof | Telegram proof | Live runtime proof | Gap | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Universe selection | Product syncs configured universe before every run | `product/service.py`, `product/sync.py` | `DoctrineProductApp.run_once`, `PolygonSyncService.prepare_run` | PostgreSQL `bars`, `features`; SQLite `runs` | Overview, Runs, Symbols | service.py:176-178 | `test_service.py::test_product_service_run_once_persists_and_sends` | latest run row `23d65c02` with `total_symbols=8` | N/A for sync itself | /runs, / | N/A | run `23d65c02` | None | DONE |
| Market data loading | Delayed bars loaded from PostgreSQL `bars` table | `product/adapters.py` | `DbMarketDataLoader.load` | PostgreSQL `bars` | Indirect via signals/trades | adapters.py | `test_runner_symbol_flow.py` | N/A | N/A | N/A | N/A | N/A | None | DONE |
| Phase2 feature loading | HTF/MTF/LTF + micro 5M features loaded | `product/adapters.py`, `product/service.py` | `DbPhase2FeatureLoader.load`, `DoctrineProductApp.build_runner_config` | PostgreSQL `features` | Micro-state fields in dashboard/Telegram | service.py:165 | `test_service.py::test_phase2_loader_requests_micro_when_runner_config_sets_5m` | N/A | N/A | micro_state on /alerts, /symbols | Micro line in Telegram | N/A | None | DONE |
| Signal engine | Computes LONG/NONE with confidence, grade, setup_state, reason codes, micro context | `engines/signal_engine.py` | `SignalEngine.evaluate` | SQLite `symbol_runs`/`alerts`; PostgreSQL `signals` | Symbols, Alerts, Trades, Telegram | signal_engine.py | `test_signal_engine_bias_and_setup.py`, `test_signal_engine_delayed_data.py` | INTC row: `signal=LONG`, `micro_state=AVAILABLE_NOT_USED` | latest Signal row exists | /symbols, /alerts | Micro line + setup line | run `23d65c02` produced LONG signal | None | DONE |
| Trade-plan engine | Builds plan for qualifying LONG setups; invalid geometry → skip | `runner/pipeline.py` | `RunnerPipeline._process_symbol` | SQLite `alerts`; PostgreSQL `trade_plans` | Alerts, Trades, symbol detail | pipeline.py | `test_runner_failures_and_skips.py` | IREN skip + INTC trade plan row | latest TradePlan row | /alerts, /trades | Trade geometry | IREN skipped, INTC plan built | None | DONE |
| Alert workflow | Decides NEW/SUPPRESSED/DUPLICATE/COOLDOWN/UPGRADED independently of Telegram | `alerts/workflow.py` | `AlertWorkflow.evaluate` | SQLite `alerts` + `prior_alert_states` | Alerts, Symbols, Trades | workflow.py:27-165 | `test_workflow_decision.py`, `test_workflow_state_rules.py` | INTC `SUPPRESSED/GRADE_NOT_SENDABLE` | N/A | /alerts | N/A | real SUPPRESSED row | None | DONE |
| Telegram transport | Real transport sends approved alerts; operator test send works | `product/clients.py`, `product/service.py` | `TelegramTransport.send_message`, `send_telegram_test_message` | SQLite `alerts`, `operator_events` | Telegram, Settings, Overview | clients.py, service.py:366-396 | `test_service.py::test_product_service_run_once_persists_and_sends` | TELEGRAM_TEST_SEND event `status=SENT` | N/A | /settings, / | real message_id=225 | Test send confirmed | None | DONE |
| Micro-state 4 states | NOT_REQUESTED/REQUESTED_UNAVAILABLE/AVAILABLE_NOT_USED/AVAILABLE_USED | `engines/signal_engine.py` | `SignalEngine.evaluate` | SQLite `alerts.micro_state`; PostgreSQL `signals.extensible_context` | /alerts, /symbols, Telegram | signal_engine.py | `test_signal_engine_delayed_data.py`, `test_telegram_renderer_missing_states.py`, `test_product_integration.py` | `micro_state=AVAILABLE_NOT_USED` in latest alert | `micro_state` in `signals.extensible_context` | /alerts micro_state column | Micro: state=AVAILABLE_NOT_USED line | SOFI fixture confirmed | None | DONE |
| Micro-state propagation | All 4 micro fields propagate end-to-end | `engines/signal_engine.py` → `alerts/workflow.py` → `alerts/telegram_renderer.py` → `product/state.py` | Signal result → AlertDecisionPayload → TelegramRenderer.render → record_alert_event | SQLite `alerts` 4 columns; PostgreSQL `extensible_context` | All surfaces | workflow.py:64-69, state.py:399-403, telegram_renderer.py:32-37 | `test_workflow_decision.py`, `test_telegram_renderer.py` | All 4 micro columns populated in latest alert | All 4 fields in extensible_context | /alerts, /symbols | Full micro line | real INTC row | None | DONE |
| Lifecycle/ML contract | Qualifying LONG + trade plan → PG Signal/TradePlan/Outcome(PENDING), independent of Telegram | `product/doctrine_tracking.py`, `product/service.py` | `record_qualifying_setups`, `DoctrineProductApp.run_once` | PostgreSQL `signals`, `trade_plans`, `outcomes` | /trades, overview doctrine cards | service.py:262-295, doctrine_tracking.py:64-152 | `test_doctrine_tracking.py::test_doctrine_lifecycle_store_records_suppressed_qualifying_setup`, `test_service.py::test_product_service_run_once_records_qualifying_setup_for_doctrine_even_when_suppressed` | DOCTRINE_PERSISTENCE `status=OK` operator_event | Signal/TradePlan/Outcome rows for suppressed INTC | /trades PENDING row | N/A | PG rows exist for suppressed INTC | None | DONE |
| Outcome tracker | PENDING outcomes advance from delayed bars on every normal run | `product/doctrine_tracking.py`, `product/service.py` | `update_pending_outcomes`, `_update_one_outcome` | PostgreSQL `outcomes`; SQLite `operator_events` | /trades, overview | doctrine_tracking.py:154-184, service.py:302-332 | `test_doctrine_tracking.py::test_doctrine_lifecycle_store_updates_outcome_labels_from_delayed_bars` | OUTCOME_TRACKER operator event exists | Outcome rows remain PENDING (no resolution data yet) | /trades shows outcome_status | N/A | OUTCOME_TRACKER event `updated=0 open=2` | None | DONE |
| Suppressed setup visibility | Suppressed qualifying setups expose full geometry + lifecycle | `product/state.py`, `product/web.py`, `product/doctrine_tracking.py` | `record_alert_event`, alerts/trades routes, `_trade_row` | SQLite `alerts`; PostgreSQL all 3 tables | /alerts, /trades, /symbols/{ticker}, overview | state.py:312-458, doctrine_tracking.py:365-405 | `test_web.py::test_operator_web_renders_suppressed_history_symbol_detail_and_recent_errors`, `test_doctrine_tracking.py::test_doctrine_lifecycle_store_records_suppressed_qualifying_setup` | INTC SUPPRESSED row with full geometry | matching Signal/TradePlan/Outcome rows | /alerts SUPPRESSED row + /trades PENDING row | N/A | INTC suppressed but tracked | None | DONE |
| Reason-code consistency | Reason codes consistent end-to-end | full chain | full chain | SQLite `alerts.reason_codes_json`; PostgreSQL `signals.reason_codes` | /alerts, /trades, Telegram | state.py:396-397, telegram_renderer.py:46 | `test_workflow_decision.py::test_payload_reason_codes_match_exact_signal_result_order`, `test_telegram_renderer.py::test_renderer_preserves_reason_codes_in_exact_order` | reason codes JSON in alerts row | reason_codes in latest Signal | /alerts, /symbols reason codes | Reasons: line in Telegram | Matching codes in SQLite + PG | None | DONE |
| Delayed-data policy | signal_timestamp vs known_at; Telegram includes 15m disclaimer | `alerts/telegram_renderer.py`, `product/service.py` | `_delayed_data_line`, `run_once` | SQLite `alerts.signal_timestamp`, `alerts.known_at` | Telegram every sendable alert, /alerts | telegram_renderer.py:54-57 | `test_telegram_renderer.py::test_renderer_text_contains_signal_and_known_timestamps` | both columns in latest alert row | Signal.signal_timestamp, Signal.known_at | /alerts, /trades | `Data: Polygon delayed 15m...` line | N/A (no live sendable in this pass) | None | DONE |
| Managed run_once contract | IDLE → RUNNING → IDLE, no-overlap, PID lifecycle | `product/control.py` | `run_once_now`, `run_once_worker`, `_coerce_status` | `.doctrine/runtime/run-once-status.json` | Launcher run-once panel | control.py:107-140, 424-453, 268-281 | `test_control.py::test_run_once_worker_success_resets_status_to_idle`, `test_runtime_controller_run_once_does_not_overlap_existing_running_worker`, `test_runtime_controller_run_once_can_restart_cleanly_after_idle` | SQLite run row on success | N/A | Launcher status panel | N/A | live transitions verified in final_implementation_verification_final.md | None | DONE |
| Non-terminal startup | One-click VBS launcher, no terminal required | `Doctrine Operator.vbs`, `product/launcher.py`, `product/control.py` | `DoctrineOperatorLauncher.run`, `RuntimeController` | `.doctrine/runtime/*.json` | Launcher window | launcher.py | `test_launcher.py` | N/A | N/A | dashboard reachable | N/A | Doctrine Operator.vbs confirmed working | None | DONE |
| Dashboard — all pages | /runs /symbols /alerts /trades /errors /settings /setup all exist | `product/web.py` | GET routes | SQLite + PostgreSQL | Dashboard | web.py:228-583 | `test_web.py`, `test_web_operator_shell.py` | data exposed via each route | trades data in /trades | all pages render | N/A | live browser confirmed | None | DONE |
| Settings/setup form save | POST /setup/save and /settings/save parse form data | `product/web.py` | `setup_save`, `settings_save` | Operator settings JSON | Setup/Settings pages | web.py:480-552 | `test_web_operator_shell.py::test_setup_flow_redirects_and_saves` (now PASSING) | N/A | N/A | /settings, /setup | N/A | N/A | RESOLVED by installing python-multipart | DONE |
| test_doctrine_reviews.py committed import safety | test imports local-only control_plane gracefully | `tests/test_doctrine_reviews.py` | pytest.skip guard on ImportError | N/A | N/A | test_doctrine_reviews.py:8-19 | 2 tests pass on workstation; will skip on clean clone | N/A | N/A | N/A | N/A | passes locally | RESOLVED by import guard fix | DONE |

---

## Remaining (not resolved and why)

### P2 — go_live_changes.md local-only claims

Three of the seven changes listed in `docs/go_live_changes.md` reference files that are excluded from git via `.git/info/exclude`:

1. `.openclaw/backup.ps1` fixes (items 1, 2, 3b) — these changes cannot be verified from the committed repo. The `.openclaw/` directory is intentionally local-only. The go_live_changes.md documents them for local operator awareness only. No code fix is possible or appropriate here — the exclusion is by design.

2. `tasks/` queue state (item 5) — `tasks/proposed.md` and `tasks/done.md` are local-only. Not tracked in git by design.

3. `CLAUDE.md` updates (items 5, 6) — CLAUDE.md itself is excluded from git. Not tracked by design.

These are P2 (reconciliation/release-truth drift) items. They do not affect runtime correctness. The doc correctly notes in item 7 that git push is deferred. No fix is warranted — these are correctly labeled local-only operational artifacts.

### P3 — Quality.md untracked file

`Quality.md` exists in the repo root as an untracked file. It is neither in `.gitignore` nor in `.git/info/exclude`. It is not a source or doc file committed to git. It will appear in every `git status` output. This is cosmetic only — no runtime impact. The operator should either add it to `.git/info/exclude` or delete it. Not fixed here as it is P3 hygiene.

### P3 — memory/ untracked directory

`memory/` is an untracked directory in the repo root. Same situation as Quality.md — appears in `git status` but has no runtime impact. P3 hygiene.

---

## Summary

| Priority | Gap | Fix applied | Outcome |
|---|---|---|---|
| P0 | `tests/test_doctrine_reviews.py` committed with hard import of local-only `control_plane` module; fails collection on clean clone | Added try/except ImportError with `pytest.skip(allow_module_level=True)` | RESOLVED — 200 tests pass; tests skip gracefully when control_plane absent |
| P1 | `python-multipart` not installed; POST form handlers fail at runtime; test failing | Installed `python-multipart==0.0.22` | RESOLVED — test now passes; form endpoints functional |
| P2 | go_live_changes.md references local-only excluded files (backup.ps1, tasks/, CLAUDE.md) | No code fix warranted — correctly local-only by design | ACKNOWLEDGED, not fixable from repo |
| P3 | Quality.md and memory/ untracked in repo root | No fix applied | REMAINING — hygiene only |
