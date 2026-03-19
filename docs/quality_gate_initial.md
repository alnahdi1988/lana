# Quality Gate — Initial Pass — 2026-03-16

## B. Committed vs Local-Only Truth

### git status
```
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	Quality.md
	memory/

nothing added to commit but untracked files present (use "git add" to track)
```

### git log --oneline -5
```
09aa3d7 Add operator handoff docs, doctrine review tests, and go-live changes log
0829530 Add run_once completion verification proof
dac4ccd Finalize implementation verification proof pass
07db8ae Close doctrine closure-control gaps
ecee558 Close doctrine lifecycle and operator truth gaps
```

### git diff origin/main --stat
```
 docs/go_live_changes.md        | 120 +++++++++++++++
 docs/operator_handoff_pack.md  | 335 +++++++++++++++++++++++++++++++++++++++++
 tests/test_doctrine_reviews.py | 109 ++++++++++++++
 3 files changed, 564 insertions(+)
```
The local branch is 1 commit ahead of origin/main. This commit (09aa3d7) adds operator_handoff_pack.md, test_doctrine_reviews.py, and go_live_changes.md. These files are committed locally but not yet pushed.

### .git/info/exclude
```
# git ls-files --others --exclude-from=.git/info/exclude
# Lines that start with '#' are comments.
.claude/
.openclaw/
CLAUDE.md
SESSION_COMMANDS.sh
deploy.sh
health_check.py
tasks/
tests/test_openclaw_config.py
scripts/
src/doctrine_engine/control_plane/
tests/test_openclaw_task_queue.py
```

### Committed (in git):
- All source code under `src/doctrine_engine/` (except `src/doctrine_engine/control_plane/`)
- All tests under `tests/` (except `tests/test_openclaw_config.py` and `tests/test_openclaw_task_queue.py`)
- `tests/test_doctrine_reviews.py` — committed in HEAD (09aa3d7), ahead of origin/main
- `docs/operator_handoff_pack.md` — committed in HEAD, ahead of origin/main
- `docs/go_live_changes.md` — committed in HEAD, ahead of origin/main
- All other `docs/*.md` committed to origin/main

### Local-only (excluded or untracked):
- `.claude/` — excluded via .git/info/exclude (local AI session files)
- `.openclaw/` — excluded via .git/info/exclude (local operational scripts, backup.ps1)
- `CLAUDE.md` — excluded via .git/info/exclude (project instructions for Claude sessions, local-only)
- `SESSION_COMMANDS.sh` — excluded via .git/info/exclude
- `deploy.sh` — excluded via .git/info/exclude
- `health_check.py` — excluded via .git/info/exclude
- `tasks/` — excluded via .git/info/exclude (local task queue state)
- `tests/test_openclaw_config.py` — excluded via .git/info/exclude
- `tests/test_openclaw_task_queue.py` — excluded via .git/info/exclude
- `scripts/` — excluded via .git/info/exclude
- `src/doctrine_engine/control_plane/` — excluded via .git/info/exclude; contains `doctrine_reviews.py`, `task_queue.py`, `__init__.py`
- `Quality.md` — untracked (not excluded, just not added)
- `memory/` — untracked directory

### Critical gap identified:
`tests/test_doctrine_reviews.py` is COMMITTED (in HEAD commit 09aa3d7) but it imports `from doctrine_engine.control_plane import doctrine_reviews` and `from doctrine_engine.control_plane.task_queue import TaskQueue`. The `src/doctrine_engine/control_plane/` directory is in `.git/info/exclude` — it is local-only and not committed to git. Any clone of this repository that does not have the local control_plane files will fail to import and collect this test. The test is committed but its dependency is local-only.

---

## Traceability Matrix

### A. Doctrine Requirement Traceability

| Requirement | Real current behavior | File path(s) | Implementation location | Persistence location | Operator surface | Proof | Gap | Status |
|---|---|---|---|---|---|---|---|---|
| Universe selection | Product syncs configured universe before every run | `product/service.py`, `product/sync.py` | `DoctrineProductApp.run_once`, `PolygonSyncService.prepare_run` | PostgreSQL `bars`, `features`; SQLite `runs` | Overview, Runs, Symbols | Code: service.py:176-178; Test: `tests/product/test_service.py::test_product_service_run_once_persists_and_sends`; SQLite: latest run row; Live runtime: run 23d65c02 | None | DONE |
| Market data loading | Runtime loads delayed bars from PostgreSQL for engine evaluation | `product/adapters.py` | `DbMarketDataLoader.load` | PostgreSQL `bars` | Indirect via signals/trades | Code: adapters.py; Test: `tests/runner/test_runner_symbol_flow.py` | None | DONE |
| Phase2 feature loading | Runtime loads HTF/MTF/LTF and micro 5M features | `product/adapters.py`, `product/service.py` | `DbPhase2FeatureLoader.load`, `DoctrineProductApp.build_runner_config` | PostgreSQL `features` | Micro-state fields in dashboard/Telegram | Code: service.py:165; Test: `test_service.py::test_phase2_loader_requests_micro_when_runner_config_sets_5m` | None | DONE |
| Signal engine | Computes LONG/NONE with confidence, grade, setup_state, reason codes, micro context | `engines/signal_engine.py` | `SignalEngine.evaluate` | SQLite `symbol_runs`/`alerts`; PostgreSQL `signals` | Symbols, Alerts, Trades, Telegram | Code: signal_engine.py; Test: multiple `tests/engines/` files; SQLite proof: latest INTC row; PG proof: latest Signal row | None | DONE |
| Trade-plan engine | Builds plan for qualifying LONG setups; invalid geometry → symbol skip not run failure | `runner/pipeline.py`, `product/doctrine_tracking.py` | `RunnerPipeline._process_symbol`, `record_qualifying_setups` | SQLite `alerts`/`symbol_runs`; PostgreSQL `trade_plans` | Alerts, Trades, symbol detail | Code: pipeline.py; Test: `tests/runner/test_runner_failures_and_skips.py`; SQLite: real IREN skip and INTC trade_plan row | None | DONE |
| Alert workflow | Decides NEW/SUPPRESSED/DUPLICATE/COOLDOWN/UPGRADED independently of Telegram | `alerts/workflow.py` | `AlertWorkflow.evaluate` | SQLite `alerts` + `prior_alert_states` | Alerts, Symbols, Trades | Code: workflow.py:27-165; Test: `test_workflow_decision.py`, `test_workflow_state_rules.py`; SQLite: real SUPPRESSED INTC row | None | DONE |
| Telegram transport | Real transport sends workflow-approved alerts; operator test sends work | `product/clients.py`, `product/service.py` | `TelegramTransport.send_message`, `send_telegram_test_message` | SQLite `alerts`, `operator_events` | Telegram, Settings, Overview | Code: clients.py; Test: `test_service.py::test_product_service_run_once_persists_and_sends`; SQLite: real TELEGRAM_TEST_SEND event status=SENT | None | DONE |
| Micro-state model (4 states) | NOT_REQUESTED, REQUESTED_UNAVAILABLE, AVAILABLE_NOT_USED, AVAILABLE_USED derived by SignalEngine | `engines/signal_engine.py` | `SignalEngine.evaluate` | SQLite `alerts.micro_state`; PostgreSQL `signals.extensible_context` | Alerts page, symbol detail, Telegram line | Code: signal_engine.py; Test: `test_signal_engine_delayed_data.py`, `test_telegram_renderer_missing_states.py`, `test_product_integration.py` | None | DONE |
| Micro-state propagation | micro_state/micro_present/micro_trigger_state/micro_used_for_confirmation propagate end-to-end | `engines/signal_engine.py` → `alerts/workflow.py` → `alerts/telegram_renderer.py` → `product/state.py` | Signal result → AlertDecisionPayload → TelegramRenderer.render → record_alert_event | SQLite `alerts` (all 4 columns); PostgreSQL `signals.extensible_context` | All alert surfaces + Telegram | Code: workflow.py:64-69, state.py:399-403, telegram_renderer.py:32-37; Test: `test_workflow_decision.py`, `test_telegram_renderer.py`; SQLite: real row with all 4 micro fields | None | DONE |
| Lifecycle/ML contract | Every qualifying LONG + trade plan → Signal + TradePlan + Outcome(PENDING) in PostgreSQL, independent of Telegram sendability | `product/doctrine_tracking.py`, `product/service.py` | `DoctrineLifecycleStore.record_qualifying_setups`, `DoctrineProductApp.run_once` | PostgreSQL `signals`, `trade_plans`, `outcomes` | Trades page, overview doctrine cards | Code: service.py:262-295, doctrine_tracking.py:64-152; Test: `test_doctrine_tracking.py::test_doctrine_lifecycle_store_records_suppressed_qualifying_setup`; PG proof: real Signal/TradePlan/Outcome rows for suppressed INTC | None | DONE |
| Outcome tracker | Pending outcomes update automatically from delayed bars during normal runs | `product/doctrine_tracking.py`, `product/service.py` | `DoctrineLifecycleStore.update_pending_outcomes`, `_update_one_outcome` | PostgreSQL `outcomes`; SQLite `operator_events` | Trades, overview doctrine status | Code: doctrine_tracking.py:154-184, service.py:302-332; Test: `test_doctrine_tracking.py::test_doctrine_lifecycle_store_updates_outcome_labels_from_delayed_bars`; SQLite: real OUTCOME_TRACKER event | None | DONE |
| Suppressed setup visibility | Suppressed qualifying setups are first-class operator objects with full trade geometry and lifecycle tracking | `product/state.py`, `product/web.py`, `product/doctrine_tracking.py` | `record_alert_event`, alerts/trades routes, `_trade_row` | SQLite `alerts`; PostgreSQL `signals/trade_plans/outcomes` | /alerts, /trades, /symbols/{ticker}, overview | Code: state.py:312-458, doctrine_tracking.py:365-405; Test: `test_web.py::test_operator_web_renders_suppressed_history_symbol_detail_and_recent_errors`; SQLite: real INTC SUPPRESSED row with full geometry | None | DONE |
| Reason-code consistency | Setup reasoning survives consistently end-to-end across all surfaces | `engines/signal_engine.py`, `alerts/workflow.py`, `product/state.py`, `alerts/telegram_renderer.py` | full chain | SQLite `alerts.reason_codes_json`; PostgreSQL `signals.reason_codes` | /alerts, /trades, Telegram | Code: state.py:396-397, telegram_renderer.py:46; Test: `test_workflow_decision.py::test_payload_reason_codes_match_exact_signal_result_order`, `test_telegram_renderer.py::test_renderer_preserves_reason_codes_in_exact_order` | None | DONE |
| Delayed-data policy | signal_timestamp vs known_at separation; Telegram includes 15m disclaimer | `alerts/telegram_renderer.py`, `product/service.py` | `TelegramRenderer._delayed_data_line`, `run_once` | SQLite `alerts` (`signal_timestamp`, `known_at`); PostgreSQL `signals.signal_timestamp`, `signals.known_at` | Telegram every alert, /alerts, /trades | Code: telegram_renderer.py:54-57; Test: `test_telegram_renderer.py::test_renderer_text_contains_signal_and_known_timestamps` | None | DONE |
| Managed run_once contract | IDLE → RUNNING transition, PID tracking, completion → IDLE return, no-overlap enforcement | `product/control.py` | `RuntimeController.run_once_now`, `run_once_worker`, `_coerce_status` | `.doctrine/runtime/run-once-status.json` | Launcher run-once status panel | Code: control.py:107-140 (no-overlap check), 424-453 (worker writes IDLE); Test: `test_control.py::test_run_once_worker_success_resets_status_to_idle`, `test_runtime_controller_run_once_does_not_overlap_existing_running_worker`, `test_runtime_controller_run_once_can_restart_cleanly_after_idle` | None | DONE |
| Non-terminal startup | One-click VBS launcher starts launcher UI + dashboard without terminal | `Doctrine Operator.vbs`, `product/launcher.py`, `product/control.py` | `DoctrineOperatorLauncher.run`, `RuntimeController` | `.doctrine/runtime/*.json` and pid/log files | Launcher window | Code: launcher.py; Test: `test_launcher.py`, `test_web_operator_shell.py`; Live: Doctrine Operator.vbs confirmed working | None | DONE |
| Dashboard pages — overview | / shows engine state, web state, run-once state, latest run, recent runs, symbols, alerts, trades, errors, known_at | `product/web.py` | `overview` route | SQLite + PostgreSQL join | http://127.0.0.1:8000/ | Code: web.py:152-226; Test: `test_web.py::test_operator_web_renders_latest_state` | None | DONE |
| Dashboard pages — all pages | /runs, /symbols, /alerts, /trades, /errors, /settings, /setup all exist | `product/web.py` | All GET routes | SQLite + PostgreSQL | Dashboard | Code: web.py:228-583; Test: `test_web.py`, `test_web_operator_shell.py` | None | DONE |
| Settings page — Telegram test send | /control/send-telegram-test route sends a labeled test message | `product/web.py`, `product/service.py` | `control_send_telegram_test`, `send_telegram_test_message` | SQLite `operator_events` | Settings page, Overview | Code: web.py:579-582, service.py:366-396; Test: `test_web_operator_shell.py::test_settings_page_and_telegram_test_send_route`; Live: message_id=225 | None | DONE |
| Setup page — form save | /setup/save POSTs settings form; requires python-multipart for form parsing | `product/web.py` | `setup_save` async handler | Operator settings JSON file | Setup page, redirect to Settings | Code: web.py:480-517 | python-multipart not installed in local env → `test_setup_flow_redirects_and_saves` FAILED | P1 GAP — dependency missing from environment |
| go_live_changes.md claims backup.ps1 fixes | Changes 1, 2, 3 applied to `.openclaw/backup.ps1` | `.openclaw/backup.ps1` | powershell script | local only | N/A | `.openclaw/` is excluded from git | LOCAL_ONLY — backup.ps1 is not committed, not verifiable from repo | P2 |
| go_live_changes.md claims tasks/ closed | Task queue items moved from proposed to done | `tasks/proposed.md`, `tasks/done.md` | task queue files | local only | N/A | `tasks/` is excluded from git | LOCAL_ONLY — task state is not in git | P2 |
| test_doctrine_reviews.py committed with local-only dependency | Test file committed to git (HEAD) imports `doctrine_engine.control_plane` which is in `.git/info/exclude` | `tests/test_doctrine_reviews.py` imports `src/doctrine_engine/control_plane/` | `doctrine_reviews.run_data_freshness_review`, `run_pipeline_integrity_review` | N/A | N/A | Test passes locally because control_plane/ exists on this workstation. On a clean clone it fails import collection. | Committed test has unresolvable import on any clone without local-only excluded module | P0 GAP |

---

## C. Operator Acceptance

### Dashboard pages verified in code:
- `GET /` — overview (web.py:152)
- `GET /runs` — runs list (web.py:228)
- `GET /runs/{run_id}` — run detail (web.py:244)
- `GET /symbols` — symbols list (web.py:267)
- `GET /symbols/{ticker}` — symbol detail (web.py:310)
- `GET /alerts` — alerts history (web.py:345)
- `GET /trades` — trades/lifecycle (web.py:390)
- `GET /errors` — error list (web.py:426)
- `GET /settings` — settings page (web.py:445)
- `GET /setup` — setup wizard (web.py:463)
- `POST /setup/save` — save setup settings (web.py:480) — REQUIRES python-multipart
- `POST /settings/save` — save operator settings (web.py:519) — REQUIRES python-multipart
- `POST /control/start`, `/control/stop`, `/control/restart`, `/control/run-once`, `/control/send-telegram-test` — control endpoints (web.py:554-582)
- `GET /api/status`, `/api/runs`, `/api/runs/{run_id}`, `/api/symbols`, `/api/alerts`, `/api/trades`, `/api/errors`, `/api/settings` — JSON APIs (web.py:52-149)

### Alert states in code (telegram_renderer.py):
- `NEW` — send new operator alert
- `UPGRADED` — send updated operator alert
- `SUPPRESSED` — log only, not sent
- `DUPLICATE_BLOCKED` — blocked duplicate, not sent
- `COOLDOWN_BLOCKED` — blocked by cooldown, not sent

### Micro-state fields persisted in SQLite `alerts` table (state.py:118-121):
- `micro_state TEXT`
- `micro_present INTEGER`
- `micro_trigger_state TEXT`
- `micro_used_for_confirmation INTEGER`

### Micro-state fields surfaced in Telegram (telegram_renderer.py:32-37):
```
Micro: state={micro_state} | present={micro_present} | trigger={micro_trigger_state or 'NONE'} | used_for_confirmation={micro_used_for_confirmation}
```

---

## D. Lifecycle Acceptance

### Qualifying setups create Signal + TradePlan + Outcome(PENDING):
- `service.py:262-295` — filters workflow_wrapper.records for `signal_result.signal == "LONG"`
- `doctrine_tracking.py:64-152` — `record_qualifying_setups` writes Signal, TradePlan, Outcome(PENDING) to PostgreSQL

### Suppressed setups still enter lifecycle:
- `service.py:271-273` — `QualifyingSetupRecord` is created for all LONG records regardless of `decision_result.send`
- The filter is `signal_result.signal == "LONG"` only, not send=True

### Outcome tracker updates PENDING outcomes:
- `service.py:302-332` — `update_pending_outcomes()` called unconditionally on every run when lifecycle store is available

### Telegram sendability does NOT gate lifecycle persistence:
- CONFIRMED — lifecycle path at service.py:262 is guarded only by `self.doctrine_lifecycle_store is not None`, not by any Telegram condition

---

## E. Runtime Control Acceptance

### run_once contract (control.py):
- **IDLE → RUNNING**: `run_once_now()` writes `state: RUNNING` before spawning worker (control.py:114-126)
- **PID tracking**: `_start_worker` writes PID to status file; worker writes its own PID (control.py:434-442)
- **No-overlap**: `run_once_now()` reads current status, returns if `state == RUNNING` (control.py:111-113)
- **Completion → IDLE**: `run_once_worker()` writes `state: IDLE, pid: None` at end of execution (control.py:450-453)
- **Stuck/timeout**: `_coerce_status` re-reads process liveness; if PID dead → downgrades to STOPPED/ERROR (control.py:273-274)
- **Spawn debounce**: `_spawn_in_progress` returns True for 15 seconds after a STARTING state (control.py:332-342)

---

## F. Release Truth (go_live_changes.md)

| Claim | Verification status |
|---|---|
| Fix backup.ps1 recursive archive growth | LOCAL_ONLY — `.openclaw/backup.ps1` excluded from git; cannot verify from committed code |
| Fix backup.ps1 staging cleanup | LOCAL_ONLY — same as above |
| Fix archive retention (count-based) | LOCAL_ONLY — same as above |
| Commit operator_handoff_pack.md + test_doctrine_reviews.py | COMMITTED — in HEAD commit 09aa3d7; 1 commit ahead of origin/main |
| Close resolved ops tasks | LOCAL_ONLY — `tasks/` excluded from git |
| Production DB URL closed as non-issue | LOCAL_ONLY — CLAUDE.md is excluded from git |
| Git remote already configured | LOCAL_ONLY — git state is local workstation context, not committed state |

---

## Gaps Summary

| Priority | Gap | Location |
|---|---|---|
| P0 | `tests/test_doctrine_reviews.py` committed to git imports `doctrine_engine.control_plane` which is in `.git/info/exclude` (local-only). On any clean clone, test collection fails with ImportError. | `tests/test_doctrine_reviews.py:8-9` |
| P1 | `python-multipart` declared in `pyproject.toml` but not installed in environment. `/setup/save` and `/settings/save` POST handlers fail at runtime. Test `test_setup_flow_redirects_and_saves` was failing before install. | Environment / `pyproject.toml` |
| P2 | go_live_changes.md claims backup.ps1 changes done and tasks closed — these are local-only and not verifiable from committed repo state | `docs/go_live_changes.md` |
| P3 | `Quality.md` is untracked and not in .gitignore or .git/info/exclude — it is orphaned | `Quality.md` |
