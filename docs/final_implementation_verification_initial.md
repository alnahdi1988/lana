# Final Implementation Verification Initial

Baseline commit: `07db8ae Close doctrine closure-control gaps`  
Verification date: 2026-03-15

## Matrix

### Row 01
- Requirement: Doctrine logic completeness
- Real current behavior: Structure, pattern, signal, trade-plan, regime, sector, event-risk, micro-state, grading, setup-state mapping, and workflow rules are implemented in the active engine modules and consumed by the live runner path.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\docs\doctrine_definitions.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\signal_contract.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\trade_plan_contract.md`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\structure_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\zone_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\pattern_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\trade_plan_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\regime\engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\event_risk\engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\workflow.py`
- Implementation location (class/function): `StructureEngine.evaluate`, `ZoneEngine.evaluate`, `PatternEngine.evaluate`, `SignalEngine.evaluate`, `TradePlanEngine.build_plan`, `RegimeEngine.evaluate`, `EventRiskEngine.evaluate`, `AlertWorkflow.evaluate`
- Persistence location: downstream only
- Operator surface: downstream via alert/trade outputs
- Proof:
  - code proof: present in the engine and workflow modules above
  - test proof: `tests/engines/test_structure_engine_swings.py`, `test_structure_engine_references.py`, `test_zone_engine_ranges.py`, `test_pattern_engine_compression_displacement.py`, `test_pattern_engine_reclaim_family.py`, `test_signal_engine_bias_and_setup.py`, `test_signal_engine_decision_and_confidence.py`, `test_signal_engine_delayed_data.py`, `test_signal_engine_triggers_and_alignment.py`, `test_trade_plan_engine_entry_levels.py`, `test_trade_plan_engine_gating.py`, `test_trade_plan_engine_invalidation_targets.py`, `test_trade_plan_engine_timestamps.py`, `tests/alerts/test_workflow_decision.py`, `tests/alerts/test_workflow_state_rules.py`
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A
- Gap: none
- Status: DONE

### Row 02
- Requirement: Runtime path completeness
- Real current behavior: The active path is `PolygonSyncService -> RunnerPipeline -> SignalEngine -> TradePlanEngine -> RankingEngine -> AlertWorkflow -> TelegramTransport -> OperationalStateStore -> DoctrineLifecycleStore -> FastAPI operator app`.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\runner\pipeline.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\sync.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
- Implementation location (class/function): `DoctrineProductApp.run_once`, `RunnerPipeline.run`, `RunnerPipeline._process_symbol`, `PolygonSyncService.prepare_run`, `OperationalStateStore.record_*`, `DoctrineLifecycleStore.record_qualifying_setups`, `DoctrineLifecycleStore.update_pending_outcomes`, `create_operator_app`
- Persistence location: SQLite `runs`, `symbol_runs`, `alerts`, `prior_alert_states`, `errors`, `operator_events`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: launcher, `/`, `/alerts`, `/trades`, `/symbols/{ticker}`, Telegram
- Proof:
  - code proof: present in service/pipeline/sync/state/doctrine_tracking/web modules
  - test proof: `tests/product/test_service.py`, `tests/integration/test_product_operator_shell.py`, `tests/product/test_web.py`
  - SQLite proof: latest run and alert rows exist
  - PostgreSQL proof: latest signal/trade_plan/outcome rows exist
  - dashboard/web proof: live `/`, `/alerts`, `/trades`, `/symbols/INTC` render current truth
  - Telegram proof: live `TELEGRAM_TEST_SEND` event exists; renderer tests cover sendable message content
  - live runtime proof: fresh latest run `14a8f567-61b5-4997-9769-38464b0fb9ea`
- Gap: none
- Status: DONE

### Row 03
- Requirement: Trade object completeness
- Real current behavior: The full operator object exists in SQLite and PostgreSQL and is surfaced on the dashboard, but exact reason-code survival across SQLite, dashboard, and Telegram is not explicitly test-backed in the current baseline.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\alerts_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\trades_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\db\models\signals.py`
- Implementation location (class/function): `OperationalStateStore.record_alert_event`, `create_operator_app`, `TelegramRenderer.render`, `DoctrineLifecycleStore._trade_row`
- Persistence location: SQLite `alerts`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/alerts`, `/trades`, `/symbols/{ticker}`, `/`, Telegram for sendable alerts
- Proof:
  - code proof: present
  - test proof: partial; existing tests prove fields broadly, but exact reason-code survival across all layers is not explicit
  - SQLite proof: latest alert row contains ticker, symbol_id, signal, confidence, grade, setup_state, entry, invalidation, TP1, TP2, signal time, known_at, reasons, regime, sector, event risk, micro fields, alert state, suppression reason, telegram status, prior signal link
  - PostgreSQL proof: latest `Signal`, `TradePlan`, and `Outcome` rows contain lifecycle-tracked object
  - dashboard/web proof: `/alerts`, `/trades`, `/symbols/INTC`, and `/` show the live `INTC` object including lifecycle status
  - Telegram proof: partial; renderer code includes the fields, but the exact reason-code line is not yet explicitly tested in baseline
  - live runtime proof: present through the latest suppressed qualifying `INTC` setup
- Gap: exact reason-code survival is not explicitly test-backed across SQLite/web/Telegram
- Status: PARTIAL

### Row 04
- Requirement: Lifecycle / ML contract completeness
- Real current behavior: Every qualifying `LONG` + successful trade plan is persisted as PostgreSQL `Signal`, `TradePlan`, and `Outcome(PENDING)` independent of Telegram sendability; suppressed qualifying setups are tracked; non-fatal trade-plan skips are not tracked as open trades.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\docs\labeling_and_validation.md`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
- Implementation location (class/function): `DoctrineLifecycleStore.record_qualifying_setups`, `DoctrineLifecycleStore.update_pending_outcomes`, `DoctrineProductApp.run_once`
- Persistence location: PostgreSQL `signals`, `trade_plans`, `outcomes`; SQLite `operator_events`
- Operator surface: `/trades`, `/alerts`, `/symbols/{ticker}`, overview doctrine status
- Proof:
  - code proof: present
  - test proof: `tests/product/test_doctrine_tracking.py`, `tests/product/test_service.py::test_product_service_run_once_records_qualifying_setup_for_doctrine_even_when_suppressed`
  - SQLite proof: latest `OUTCOME_TRACKER` event `updated=0 open=6 finalized=0`
  - PostgreSQL proof: latest `Signal`, `TradePlan`, and `Outcome` rows exist for current `INTC`
  - dashboard/web proof: `/trades` and `/symbols/INTC` show `PENDING` lifecycle state
  - Telegram proof: N/A for lifecycle persistence itself
  - live runtime proof: fresh run created new tracked trade row for `INTC`
- Gap: none
- Status: DONE

### Row 05
- Requirement: Telegram completeness
- Real current behavior: Sendable alert rendering includes ticker, signal, confidence, grade, setup, entry, confirmation, invalidation, TP1, TP2, timestamps, micro line, context, delayed-data wording, and explicit alert-state meaning; transport UAT path is real; dashboard shows transport outcomes. Exact reason-code line ordering is not explicitly test-backed in baseline.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\clients.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
- Implementation location (class/function): `TelegramRenderer.render`, `TelegramTransport.send_message`, `DoctrineProductApp.send_telegram_test_message`
- Persistence location: SQLite `alerts.telegram_*`; SQLite `operator_events`
- Operator surface: Telegram for sendable alerts, `/alerts`, `/settings`
- Proof:
  - code proof: present
  - test proof: partial; renderer structure is tested, but exact reasons line preservation is not explicit in baseline
  - SQLite proof: latest `TELEGRAM_TEST_SEND` event exists, latest alert has `telegram_status=NOT_SENT`
  - PostgreSQL proof: N/A
  - dashboard/web proof: settings page exposes test send and alerts page exposes telegram outcome
  - Telegram proof: live UAT test send `message_id=225`
  - live runtime proof: present for test send, N/A for live sendable trade alert in this pass
- Gap: exact reason-code preservation in Telegram text is not explicitly test-backed
- Status: PARTIAL

### Row 06
- Requirement: Dashboard / operator completeness
- Real current behavior: Dashboard pages expose latest run, latest symbols, suppressed alerts, trades, symbol detail, errors, lifecycle state, full trade geometry, suppression reason, transport state, and symbol_id.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\overview.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\symbol_detail.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\alerts_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\trades_table.html`
- Implementation location (class/function): `overview`, `alerts`, `trades`, `symbol_detail`, `_enrich_alert_rows`
- Persistence location: SQLite + PostgreSQL joined views
- Operator surface: `/`, `/alerts`, `/trades`, `/symbols/{ticker}`
- Proof:
  - code proof: present
  - test proof: `tests/product/test_web.py`, `tests/product/test_web_operator_shell.py`
  - SQLite proof: latest alert row contains full suppressed trade object
  - PostgreSQL proof: recent trades expose lifecycle state
  - dashboard/web proof: live pages render `INTC`, symbol_id, trade geometry, suppression, reason codes, and `PENDING`
  - Telegram proof: N/A
  - live runtime proof: present
- Gap: none
- Status: DONE

### Row 07
- Requirement: Reason-code consistency
- Real current behavior: signal-to-workflow reason-code order is test-backed, and the latest live suppressed setup shows the same reasons in SQLite, PostgreSQL, and web, but exact SQLite/web/Telegram preservation is not fully test-backed yet.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\workflow.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
- Implementation location (class/function): `SignalEngine.evaluate`, `AlertWorkflow.evaluate`, `OperationalStateStore.record_alert_event`, `create_operator_app`, `TelegramRenderer.render`
- Persistence location: SQLite `alerts.reason_codes_json`; PostgreSQL `signals.reason_codes`
- Operator surface: `/alerts`, `/trades`, `/symbols/{ticker}`, Telegram for sendable alerts
- Proof:
  - code proof: present
  - test proof: partial; `tests/alerts/test_workflow_decision.py::test_payload_reason_codes_match_exact_signal_result_order` proves signal -> payload only
  - SQLite proof: latest alert row stores full JSON reason list
  - PostgreSQL proof: latest `Signal.reason_codes` matches the same list
  - dashboard/web proof: live pages contain `PRICE_RANGE_VALID`
  - Telegram proof: partial; reasons line exists in renderer code
  - live runtime proof: latest suppressed `INTC` setup uses the same reasons in SQLite/PostgreSQL/web
- Gap: missing explicit test proof for SQLite/web/Telegram reason-code survival
- Status: PARTIAL

### Row 08
- Requirement: Suppressed setup usability
- Real current behavior: suppressed qualifying setups are first-class operator objects and expose full trade geometry, suppression reason, and lifecycle status for manual review and ML tracking.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
- Implementation location (class/function): `record_alert_event`, `alerts`, `trades`, `symbol_detail`, `DoctrineLifecycleStore._trade_row`
- Persistence location: SQLite `alerts`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/alerts`, `/trades`, `/symbols/INTC`, overview suppressed alerts section
- Proof:
  - code proof: present
  - test proof: `tests/product/test_web.py::test_operator_web_renders_suppressed_history_symbol_detail_and_recent_errors`, `tests/product/test_doctrine_tracking.py::test_doctrine_lifecycle_store_records_suppressed_qualifying_setup`
  - SQLite proof: latest `INTC` alert row is `SUPPRESSED/GRADE_NOT_SENDABLE`
  - PostgreSQL proof: matching `Signal/TradePlan/Outcome` rows exist for the same `signal_id`
  - dashboard/web proof: live `/alerts`, `/trades`, `/symbols/INTC` show suppression reason + `PENDING`
  - Telegram proof: N/A because suppressed trading alerts are intentionally not sent
  - live runtime proof: present
- Gap: none
- Status: DONE

### Row 09
- Requirement: Outcome progression, not only creation
- Real current behavior: normal runs execute the outcome tracker hook; dedicated tests prove pending outcomes can advance to finalized labels when later bars move.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
- Implementation location (class/function): `DoctrineLifecycleStore.update_pending_outcomes`, `DoctrineLifecycleStore._update_one_outcome`, `DoctrineProductApp.run_once`
- Persistence location: PostgreSQL `outcomes`; SQLite `operator_events`
- Operator surface: `/trades`, `/symbols/{ticker}`, overview doctrine status
- Proof:
  - code proof: present
  - test proof: `tests/product/test_doctrine_tracking.py::test_doctrine_lifecycle_store_updates_outcome_labels_from_delayed_bars`
  - SQLite proof: latest `OUTCOME_TRACKER` event proves the hook executed in a normal run
  - PostgreSQL proof: live latest `Outcome` row exists and remains `PENDING`
  - dashboard/web proof: `/trades` and `/symbols/INTC` expose `outcome_status`
  - Telegram proof: N/A
  - live runtime proof: present for hook execution; finalized live row not available in this pass
- Gap: none
- Status: DONE

### Row 10
- Requirement: Operator decision sufficiency
- Real current behavior: the operator can interpret the current suppressed qualifying setup and the lifecycle-tracked trade from launcher/dashboard without logs or SQL; sendable new/upgraded, duplicate, and cooldown behaviors are test-backed in workflow/renderer paths.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\control.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\workflow.py`
- Implementation location (class/function): `RuntimeController.status_snapshot`, `overview`, `alerts`, `trades`, `symbol_detail`, `TelegramRenderer.render`, `AlertWorkflow.evaluate`
- Persistence location: SQLite `alerts`, `operator_events`; PostgreSQL `outcomes`
- Operator surface: launcher, dashboard, Telegram
- Proof:
  - code proof: present
  - test proof: `tests/product/test_web.py`, `tests/product/test_web_operator_shell.py`, `tests/alerts/test_workflow_state_rules.py`, `tests/alerts/test_telegram_renderer.py`
  - SQLite proof: current suppressed setup persists the required fields
  - PostgreSQL proof: lifecycle `PENDING` row exists
  - dashboard/web proof: live dashboard pages show trade geometry, suppression reason, and lifecycle status
  - Telegram proof: sendable renderer contract is covered by tests; live transport proof is current UAT test send
  - live runtime proof: present for suppressed/manual-review path; N/A for live sendable new/upgraded in this pass
- Gap: none
- Status: DONE

### Row 11
- Requirement: Cross-surface truth consistency
- Real current behavior: the latest suppressed qualifying `INTC` setup is consistent across SQLite, PostgreSQL, `/alerts`, `/trades`, and `/symbols/INTC`; Telegram runtime is N/A because the alert is suppressed.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
- Implementation location (class/function): `record_alert_event`, `recent_trades`, `_trade_row`, `alerts`, `trades`, `symbol_detail`
- Persistence location: SQLite `alerts`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/alerts`, `/trades`, `/symbols/INTC`
- Proof:
  - code proof: present
  - test proof: partial; cross-surface consistency is proven by runtime evidence more than by one dedicated test in baseline
  - SQLite proof: latest alert `signal_id=d43c87a5-862c-40d3-bc8d-308fc418dd56`
  - PostgreSQL proof: latest signal/trade_plan/outcome rows for the same `signal_id`
  - dashboard/web proof: live pages show matching symbol_id, entry zone, TP1, suppression reason, micro state, and `PENDING`
  - Telegram proof: N/A for the suppressed live record; applicable renderer proof exists only for sendable alerts
  - live runtime proof: present
- Gap: cross-surface reason consistency is not explicitly test-backed in baseline
- Status: PARTIAL

### Row 12
- Requirement: Manual-trading flow proof
- Real current behavior: launcher/bootstrap state is valid, dashboard is reachable, non-terminal run path exists, latest qualifying setup appears with full details, lifecycle state is visible, and the operator can interpret the live suppressed setup without logs or SQL.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\control.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
- Implementation location (class/function): `RuntimeController`, `create_operator_app`
- Persistence location: `.doctrine/runtime/*.json`; SQLite operator state; PostgreSQL doctrine state
- Operator surface: launcher, `/`, `/alerts`, `/trades`, `/symbols/INTC`
- Proof:
  - code proof: present
  - test proof: `tests/product/test_control.py`, `tests/product/test_launcher.py`, `tests/product/test_web_operator_shell.py`, `tests/integration/test_product_operator_shell.py`
  - SQLite proof: latest run and alert rows exist
  - PostgreSQL proof: latest lifecycle rows exist
  - dashboard/web proof: current web routes reachable and contain the live setup details
  - Telegram proof: live test send is current
  - live runtime proof: present
- Gap: none
- Status: DONE

### Row 13
- Requirement: Reconciliation / drift control
- Real current behavior: docs and code are aligned on current runtime defaults, launcher-first operator usage, Telegram behavior, lifecycle tracking, and SQLite/PostgreSQL split.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\docs\runtime_validation_pack.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\manual_trading_sop.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\labeling_and_validation.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\doctrine_closure_audit_final.md`
- Implementation location (class/function): N/A
- Persistence location: N/A
- Operator surface: docs / handoff truth
- Proof:
  - code proof: N/A
  - test proof: N/A
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A
- Gap: none
- Status: DONE

### Row 14
- Requirement: Managed run_once completion contract
- Real current behavior: The controller and worker code indicate that `run_once_now()` should move from `RUNNING` back to `IDLE` and clear the worker PID after completion, but the baseline did not yet include an explicit fresh managed cycle proof through completion or restartability after completion.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\control.py`
  - `D:\Doctrine\structure-doctrine-engine\tests\product\test_control.py`
  - `D:\Doctrine\structure-doctrine-engine\.doctrine\runtime\run-once-status.json`
- Implementation location (class/function): `RuntimeController.run_once_now`, `RuntimeController.status_snapshot`, `RuntimeController._coerce_status`, `run_once_worker`
- Persistence location: `.doctrine\runtime\run-once-status.json`; SQLite `runs` on successful completion
- Operator surface: launcher/control status
- Proof:
  - code proof: present in `run_once_now`, `status_snapshot`, `_coerce_status`, and `run_once_worker`
  - test proof: partial; baseline control tests covered spawn behavior but not full completion + clean restartability
  - SQLite proof: partial; latest successful run row existed, but no dedicated managed-cycle proof tied it to a freshly observed `run_once_now`
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: partial; baseline had historical `run_once` success in status history, but not an explicitly captured fresh managed cycle through completion
- Gap: no explicit proof yet for start state, live `RUNNING` state, completion state, PID exit, `IDLE` return, and clean second `run_once_now()` after completion
- Status: PARTIAL

## Initial Result
- P0: none
- P1: Row 03 trade object completeness, Row 05 Telegram completeness, Row 07 reason-code consistency, Row 14 managed run_once completion contract
- P2: Row 11 cross-surface truth consistency proof gap
