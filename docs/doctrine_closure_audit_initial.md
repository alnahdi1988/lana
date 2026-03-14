# Doctrine Closure Audit Initial

Baseline commit: `ecee558 Close doctrine lifecycle and operator truth gaps`  
Audit date: 2026-03-15  
Audit mode: closure-control pass

## P0 / P1 Findings Opened First

### P1-01 Telegram trading-alert message omitted confidence and explicit alert-state meaning
- User-facing consequence: a sendable Telegram alert did not tell the operator the numeric confidence or whether the alert was a new signal versus an upgraded signal in plain language.
- First live-path divergence: `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py` -> `TelegramRenderer.render`
- Smallest vertical fix required: add `confidence` and `alert_state` meaning to the rendered Telegram text and update renderer proofs.

### P1-02 `symbol_id` was persisted but not shown on the alert/trade operator surfaces
- User-facing consequence: the operator could not trace an actionable or suppressed setup back to the exact doctrine symbol identifier from the web console.
- First live-path divergence:
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\alerts_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\trades_table.html`
- Smallest vertical fix required: expose `symbol_id` in the alert and trade tables and extend web proofs.

## Matrix

### Row 01
- Requirement: doctrine rule completeness
- Priority: P0
- Intended behavior: doctrine rules required by repo specs must exist in code and produce deterministic outputs.
- Real current behavior: core doctrine rules are implemented across structure, zone, pattern, signal, trade-plan, regime, event-risk, ranking, and workflow modules.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\docs\doctrine_definitions.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\signal_contract.md`
  - `D:\Doctrine\structure-doctrine-engine\docs\trade_plan_contract.md`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\structure_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\zone_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\pattern_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\trade_plan_engine.py`
- Implementation location (class/function): `StructureEngine.evaluate`, `ZoneEngine.evaluate`, `PatternEngine.evaluate`, `SignalEngine.evaluate`, `TradePlanEngine.build_plan`
- Persistence location: N/A
- Operator surface: downstream via alert/trade outputs
- Proof: engine code above; `tests/engines/test_*.py`
- Gap: none at baseline
- Status: DONE
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A

### Row 02
- Requirement: trade object completeness
- Priority: P1
- Intended behavior: every actionable or suppressed setup must expose ticker, symbol_id, signal, confidence, grade, setup_state, entry type, entry zone, confirmation, invalidation, TP1, TP2, signal timestamp, known_at, reason codes, regime state, sector state, event-risk state, micro-state, send/suppress state, transport result, suppression reason, lineage, and lifecycle status across operator surfaces where relevant.
- Real current behavior: SQLite and PostgreSQL persisted the full object; dashboard pages surfaced all listed fields except `symbol_id`, and Telegram trading alerts omitted explicit confidence and alert-state meaning.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\alerts_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\trades_table.html`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
- Implementation location (class/function): `OperationalStateStore.record_alert_event`, `create_operator_app`, `TelegramRenderer.render`
- Persistence location: SQLite `alerts`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/alerts`, `/trades`, `/symbols/{ticker}`, Telegram for sendable alerts
- Proof: latest SQLite alert row for `INTC` contained all trade fields; `/alerts` and `/trades` showed the fields but not `symbol_id`; renderer code/tests showed no explicit confidence/state-meaning line.
- Gap: Telegram missing confidence/state meaning; web missing symbol_id
- Required action: patch renderer; patch alert/trade templates
- Status: PARTIAL
- Proof dimensions:
  - code proof: present
  - test proof: partial
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: partial
  - Telegram proof: partial
  - live runtime proof: partial

### Row 03
- Requirement: lifecycle completeness
- Priority: P0
- Intended behavior: every doctrine-qualified `LONG` with a successful trade plan must create PostgreSQL `Signal`, `TradePlan`, and `Outcome(PENDING)` rows independent of Telegram sendability, then update outcomes during normal execution.
- Real current behavior: doctrine lifecycle persistence is active and current rows exist for suppressed qualified setups.
- File path(s):
  - `D:\Doctrine\structure-doctrine-engine\docs\labeling_and_validation.md`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
  - `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
- Implementation location (class/function): `DoctrineLifecycleStore.record_qualifying_setups`, `DoctrineLifecycleStore.update_pending_outcomes`, `DoctrineProductApp.run_once`
- Persistence location: PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/trades`, `/alerts`, `/symbols/{ticker}`
- Proof: `tests/product/test_doctrine_tracking.py::test_doctrine_lifecycle_store_records_suppressed_qualifying_setup`; `tests/product/test_doctrine_tracking.py::test_doctrine_lifecycle_store_updates_outcome_labels_from_delayed_bars`; `tests/product/test_service.py::test_product_service_run_once_records_qualifying_setup_for_doctrine_even_when_suppressed`; live PostgreSQL rows existed for `INTC` with `Outcome=PENDING`.
- Gap: none
- Status: DONE
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: N/A
  - live runtime proof: present

### Row 04
- Requirement: operator truth completeness
- Priority: P1
- Intended behavior: launcher + dashboard + Telegram must expose a coherent manual-trading view of the current setup truth.
- Real current behavior: dashboard/operator truth was coherent; Telegram trading-alert text missed confidence/state meaning; web omitted symbol_id.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
- Implementation location (class/function): `create_operator_app`, `TelegramRenderer.render`
- Persistence location: SQLite `alerts`, `runs`, `symbol_runs`, `operator_events`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: launcher, dashboard pages, Telegram
- Proof: live dashboard pages rendered full trade details; latest SQLite alert row matched dashboard; renderer content gap remained.
- Gap: Telegram text incomplete; `symbol_id` omitted from dashboard
- Required action: patch renderer; patch web templates
- Status: PARTIAL
- Proof dimensions:
  - code proof: present
  - test proof: partial
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: partial
  - Telegram proof: partial
  - live runtime proof: partial

### Row 05
- Requirement: runtime truth completeness
- Priority: P0
- Intended behavior: live runtime must execute loader -> runner -> signal -> trade-plan -> workflow -> persistence -> web/Telegram without dropping truth required for manual trading.
- Real current behavior: current runtime path used all required stages and persisted the outputs; latest real run was successful.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\runner\pipeline.py`
- Implementation location (class/function): `DoctrineProductApp.run_once`, `RunnerPipeline.run`, `RunnerPipeline._process_symbol`
- Persistence location: SQLite `runs`, `symbol_runs`, `alerts`, `errors`, `operator_events`; PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/`, `/alerts`, `/trades`, Telegram transport/test send
- Proof: `tests/product/test_service.py::test_product_service_run_once_persists_and_sends`; `tests/integration/test_product_operator_shell.py::test_operator_shell_run_once_to_web`; latest run `9be42429-4ed4-49fa-bccf-9a528dc05c42` SUCCESS in SQLite.
- Gap: none
- Status: DONE
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: present
  - live runtime proof: present

### Row 06
- Requirement: structure and zone doctrine
- Priority: P0
- Intended behavior: structure logic must implement swings, BOS, CHOCH, protected highs/lows, active range, equilibrium, and premium/discount deterministically.
- Real current behavior: implemented in structure and zone engines and consumed by signal/trade-plan logic.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\structure_engine.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\zone_engine.py`
- Implementation location (class/function): `StructureEngine.evaluate`, `_select_bullish_bos_reference`, `_select_bullish_choch_reference`, `_determine_trend_state`, `_select_active_range`; `ZoneEngine.evaluate`
- Runtime path: `RunnerPipeline._build_signal_input` -> `SignalEngine.evaluate`
- Persistence location: downstream only
- Operator surface: downstream via setup/trade outputs
- Test coverage: `tests/engines/test_structure_engine_swings.py`; `tests/engines/test_structure_engine_references.py`; `tests/engines/test_zone_engine_ranges.py`
- Status: DONE
- Evidence: engine tests above prove BOS, CHOCH, active range, equilibrium band boundaries, and premium/discount selection.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A

### Row 07
- Requirement: pattern doctrine
- Priority: P0
- Intended behavior: reclaim, displacement, recontainment, fake breakdown, trap reverse, and compression must be implemented as deterministic pattern states.
- Real current behavior: implemented in `PatternEngine` and consumed by `SignalEngine`.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\pattern_engine.py`
- Implementation location (class/function): `_evaluate_compression`, `_advance_displacement`, `_advance_reclaim`, `_advance_fake_breakdown`, `_advance_trap_reverse`, `_advance_recontainment`
- Runtime path: `RunnerPipeline._build_signal_input` -> `SignalEngine.evaluate`
- Persistence location: downstream only
- Operator surface: downstream via `setup_state`, reason codes, and trade plan
- Test coverage: `tests/engines/test_pattern_engine_compression_displacement.py`; `tests/engines/test_pattern_engine_reclaim_family.py`
- Status: DONE
- Evidence: the pattern-engine tests prove compression/displacement behavior and reclaim/fake-breakdown/trap-reverse/recontainment lifecycles.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A

### Row 08
- Requirement: regime, sector, event-risk, and micro-state doctrine
- Priority: P0
- Intended behavior: the live path must compute regime/sector permission, event-risk blocking, and micro-state semantics and feed them into the signal and alert payloads.
- Real current behavior: implemented and propagated end to end.
- File path(s): `D:\Doctrine\structure-doctrine-engine\docs\regime_rules.md`; `D:\Doctrine\structure-doctrine-engine\docs\event_risk_rules.md`; `D:\Doctrine\structure-doctrine-engine\docs\timing_and_micro_semantics.md`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\regime\engine.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\event_risk\engine.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py`
- Implementation location (class/function): `RegimeEngine.evaluate`, `EventRiskEngine.evaluate`, `SignalEngine._micro_state`, `SignalEngine._determine_trigger_state`
- Runtime path: `RunnerPipeline._process_symbol` -> `RegimeEngine.evaluate` / `EventRiskEngine.evaluate` -> `SignalEngine.evaluate`
- Persistence location: SQLite `alerts`; PostgreSQL `signals.extensible_context`
- Operator surface: `/alerts`, `/trades`, `/symbols/{ticker}`, Telegram micro/context lines
- Test coverage: `tests/engines/test_signal_engine_delayed_data.py`; `tests/engines/test_signal_engine_triggers_and_alignment.py`; `tests/engines/test_signal_engine_decision_and_confidence.py`; `tests/integration/test_product_integration.py::TestCanonicalSofiScenario`
- Status: DONE
- Evidence: current live SQLite alert rows contain `market_regime`, `sector_regime`, `event_risk_class`, and `micro_*` fields; live PostgreSQL trades include the same values.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: present
  - live runtime proof: present

### Row 09
- Requirement: signal grading and setup_state mapping
- Priority: P0
- Intended behavior: signal confidence, grade, and setup_state must be deterministic and preserved through the live path.
- Real current behavior: implemented and persisted.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\signal_engine.py`
- Implementation location (class/function): `SignalEngine._compute_confidence`, `SignalEngine._output_setup_state`, `SignalEngine._grade`
- Runtime path: `RunnerPipeline._process_symbol` -> `SignalEngine.evaluate` -> alert workflow
- Persistence location: SQLite `alerts.confidence`, `alerts.grade`, `alerts.setup_state`; PostgreSQL `signals.confidence`, `signals.grade`, `signals.setup_state`
- Operator surface: `/alerts`, `/trades`, Telegram
- Test coverage: `tests/engines/test_signal_engine_bias_and_setup.py`; `tests/engines/test_signal_engine_decision_and_confidence.py`; `tests/product/test_service.py::test_product_service_run_once_records_qualifying_setup_for_doctrine_even_when_suppressed`
- Status: DONE
- Evidence: latest SQLite and PostgreSQL rows for `INTC` match on `confidence=0.7100`, `grade=B`, `setup_state=BULLISH_RECLAIM`.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: partial
  - live runtime proof: present

### Row 10
- Requirement: trade-plan logic
- Priority: P0
- Intended behavior: entry type, entry zone, confirmation, invalidation, TP1, and TP2 must be derived from doctrine setup geometry and preserved through persistence.
- Real current behavior: implemented and persisted.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\engines\trade_plan_engine.py`
- Implementation location (class/function): `TradePlanEngine.build_plan`, `_determine_entry_type`, `_entry_zone`, `_confirmation_level`, `_invalidation_level`, `_tp1`, `_tp2`
- Runtime path: `RunnerPipeline._process_symbol` -> `TradePlanEngine.build_plan`
- Persistence location: SQLite `alerts`; PostgreSQL `trade_plans`
- Operator surface: `/alerts`, `/trades`, `/symbols/{ticker}`, Telegram
- Test coverage: `tests/engines/test_trade_plan_engine_entry_levels.py`; `tests/engines/test_trade_plan_engine_invalidation_targets.py`; `tests/engines/test_trade_plan_engine_timestamps.py`; `tests/engines/test_trade_plan_engine_gating.py`
- Status: DONE
- Evidence: latest live `INTC` rows show consistent entry zone / invalidation / TP1 / TP2 across SQLite, PostgreSQL, and web.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: partial
  - live runtime proof: present

### Row 11
- Requirement: suppression / cooldown / duplicate / upgrade logic
- Priority: P0
- Intended behavior: the workflow must distinguish sendable vs suppressed results and preserve duplicate/cooldown/upgrade state.
- Real current behavior: implemented and persisted.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\workflow.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
- Implementation location (class/function): `AlertWorkflow.evaluate`; `OperationalStateStore.record_alert_event`
- Runtime path: `DoctrineProductApp.run_once` -> `RecordingAlertWorkflow.evaluate` -> `record_alert_event`
- Persistence location: SQLite `alerts`; SQLite `prior_alert_states`
- Operator surface: `/alerts`; `/symbols/{ticker}`
- Test coverage: `tests/alerts/test_workflow_decision.py`; `tests/alerts/test_workflow_state_rules.py`; `tests/product/test_state.py`
- Status: DONE
- Evidence: live latest `INTC` alert is `SUPPRESSED/GRADE_NOT_SENDABLE`; dedicated state tests prove duplicate/cooldown/upgrade persistence.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: N/A
  - dashboard/web proof: present
  - Telegram proof: N/A for suppressed rows
  - live runtime proof: present

### Row 12
- Requirement: runtime execution path uses every doctrine component
- Priority: P0
- Intended behavior: live runtime must use loader -> runner -> signal -> trade-plan -> ranking -> workflow -> persistence -> web/Telegram.
- Real current behavior: used live; no computed doctrine object identified as dropped before persistence except the Telegram renderer gap above.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\runner\pipeline.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`
- Implementation location (class/function): `RunnerPipeline.run`, `RunnerPipeline._process_symbol`, `DoctrineProductApp.run_once`
- Persistence location: SQLite operator tables; PostgreSQL doctrine tables
- Operator surface: dashboard pages; Telegram transport
- Proof: `tests/integration/test_product_operator_shell.py::test_operator_shell_run_once_to_web`; `tests/product/test_service.py::test_product_service_run_once_persists_micro_contract_and_web_reads_same_values`; live run `9be42429-4ed4-49fa-bccf-9a528dc05c42`
- Gap: none
- Status: DONE
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: present
  - live runtime proof: present

### Row 13
- Requirement: SQLite operator persistence
- Priority: P0
- Intended behavior: runs, symbol outcomes, alerts, prior alert state, transport outcomes, errors, and operator events must be stored and queryable.
- Real current behavior: implemented and live.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
- Implementation location (class/function): `OperationalStateStore.initialize`, `record_run`, `record_alert_event`, `record_error`, `record_operator_event`, query helpers
- Persistence location: SQLite `runs`, `symbol_runs`, `alerts`, `prior_alert_states`, `errors`, `operator_events`
- Operator surface: `/`, `/runs`, `/alerts`, `/errors`, `/symbols/{ticker}`
- Test coverage: `tests/product/test_state.py`; `tests/product/test_web.py`
- Status: DONE
- Evidence: current live SQLite rows exist for the latest run, latest alert, and latest `TELEGRAM_TEST_SEND`.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: N/A
  - dashboard/web proof: present
  - Telegram proof: present
  - live runtime proof: present

### Row 14
- Requirement: PostgreSQL doctrine / ML persistence
- Priority: P0
- Intended behavior: doctrine-qualified setups must be tracked as lifecycle candidates for ML labels.
- Real current behavior: implemented and current.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\db\models\signals.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\doctrine_tracking.py`
- Implementation location (class/function): `Signal`, `TradePlan`, `Outcome`; `DoctrineLifecycleStore.record_qualifying_setups`; `DoctrineLifecycleStore.update_pending_outcomes`
- Persistence location: PostgreSQL `signals`, `trade_plans`, `outcomes`
- Operator surface: `/trades`, `/alerts`, `/symbols/{ticker}`
- Test coverage: `tests/product/test_doctrine_tracking.py`; `tests/product/test_service.py::test_product_service_run_once_records_qualifying_setup_for_doctrine_even_when_suppressed`
- Status: DONE
- Evidence: latest PostgreSQL rows existed for `INTC` with `Outcome=PENDING`; `doctrine_status_snapshot` reported `open_trades=4`.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: present
  - dashboard/web proof: present
  - Telegram proof: N/A
  - live runtime proof: present

### Row 15
- Requirement: Telegram transport contract
- Priority: P1
- Intended behavior: real transport must surface configured/unconfigured state, persist send outcomes, and allow a clearly labeled UAT test send.
- Real current behavior: implemented and live.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\clients.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\service.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\state.py`
- Implementation location (class/function): `TelegramTransport.send_message`; `DoctrineProductApp.send_telegram_test_message`; `OperationalStateStore.record_operator_event`
- Persistence location: SQLite `alerts.telegram_*`; SQLite `operator_events`
- Operator surface: `/settings`; `/alerts`; Telegram UAT test send
- Test coverage: `tests/product/test_transport.py`; `tests/product/test_web_operator_shell.py::test_settings_page_and_telegram_test_send_route`
- Status: DONE
- Evidence: live `TELEGRAM_TEST_SEND` operator event already existed with `status=SENT`.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: present
  - PostgreSQL proof: N/A
  - dashboard/web proof: present
  - Telegram proof: present
  - live runtime proof: present

### Row 16
- Requirement: Telegram trading-alert rendering contract
- Priority: P1
- Intended behavior: sendable trading alerts must render symbol, grade/confidence, setup_state, entry type, entry zone, invalidation, TP1/TP2, signal timestamp, known_at, delayed-data wording, micro-state line, reasons, and explicit alert-state meaning.
- Real current behavior: renderer included symbol, grade, setup, entry, zone, invalidation, TP1/TP2, timestamps, context, delayed-data wording, summary, and reasons; it omitted explicit confidence and alert-state meaning.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\alerts\telegram_renderer.py`
- Implementation location (class/function): `TelegramRenderer.render`
- Runtime path: `DoctrineProductApp.run_once` -> `RecordingTelegramRenderer.render`
- Persistence path: SQLite `alerts.rendered_text` for sendable alerts
- Operator-visible path: Telegram for sendable alerts; `/alerts` preview column for persisted rendered text
- Test coverage: `tests/alerts/test_telegram_renderer.py`; `tests/alerts/test_telegram_renderer_missing_states.py`; `tests/integration/test_product_integration.py::TestCanonicalSofiScenario`
- Status: PARTIAL
- Evidence: code inspection of `TelegramRenderer.render` showed no confidence line and no state-meaning line; existing renderer tests did not assert those fields.
- Gap: missing confidence; missing alert-state meaning
- Required action: patch renderer and tests
- Proof dimensions:
  - code proof: present
  - test proof: partial
  - SQLite proof: N/A for baseline row because no live sendable alert in the refreshed run
  - PostgreSQL proof: N/A
  - dashboard/web proof: partial via preview column only
  - Telegram proof: partial
  - live runtime proof: N/A in this baseline because no live sendable trading alert occurred

### Row 17
- Requirement: dashboard / web operator completeness
- Priority: P1
- Intended behavior: the dashboard must show full trade details, suppressed alerts, Telegram outcomes, lifecycle status, and filters required for manual operation.
- Real current behavior: implemented; only `symbol_id` omission remained.
- File path(s): `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\web.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\alerts_table.html`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\templates\partials\trades_table.html`
- Implementation location (class/function): `create_operator_app`; `alerts`; `trades`; `symbol_detail`
- Persistence location: SQLite + PostgreSQL joined through `enrich_alert_rows` and `recent_trades`
- Operator surface: `/`; `/alerts`; `/trades`; `/symbols/{ticker}`
- Test coverage: `tests/product/test_web.py`; `tests/product/test_web_operator_shell.py`
- Status: PARTIAL
- Evidence: live `/alerts` and `/trades` pages showed trade details; `symbol_id` was not rendered.
- Gap: missing `symbol_id` column on operator tables
- Required action: patch templates and web proof
- Proof dimensions:
  - code proof: present
  - test proof: partial
  - SQLite proof: present
  - PostgreSQL proof: present
  - dashboard/web proof: partial
  - Telegram proof: N/A
  - live runtime proof: partial

### Row 18
- Requirement: launcher / no-terminal usage
- Priority: P1
- Intended behavior: the operator must start and use the system without terminal or PowerShell.
- Real current behavior: implemented and working through the Windows launcher and managed controller.
- File path(s): `D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs`; `D:\Doctrine\structure-doctrine-engine\Doctrine Operator.cmd`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\launcher.py`; `D:\Doctrine\structure-doctrine-engine\src\doctrine_engine\product\control.py`
- Implementation location (class/function): `RuntimeController`; `run_launcher`
- Persistence location: `.doctrine/runtime/*.json`
- Operator surface: launcher window; dashboard
- Test coverage: `tests/product/test_control.py`; `tests/product/test_launcher.py`; `tests/product/test_web_operator_shell.py::test_click_only_runtime_skips_setup_when_effective_runtime_is_already_valid`
- Status: DONE
- Evidence: live `RuntimeController.status_snapshot()` showed `setup_complete=True` and `web.state=RUNNING`.
- Gap: none
- Required action: none
- Proof dimensions:
  - code proof: present
  - test proof: present
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: present
  - Telegram proof: N/A
  - live runtime proof: present

### Row 19
- Requirement: doctrine-to-spec reconciliation
- Priority: P2
- Intended behavior: doctrine docs, runtime docs, handoff docs, and product behavior must agree on the current manual-trading-ready system.
- Real current behavior: doctrine/product docs were broadly aligned, but this doctrine-specific closure-control audit document did not exist yet.
- File path(s): `D:\Doctrine\structure-doctrine-engine\README.md`; `D:\Doctrine\structure-doctrine-engine\docs\manual_trading_sop.md`; `D:\Doctrine\structure-doctrine-engine\docs\runtime_validation_pack.md`; `D:\Doctrine\structure-doctrine-engine\docs\labeling_and_validation.md`
- Implementation location (class/function): N/A
- Persistence location: N/A
- Operator surface: docs / handoff truth
- Test coverage: N/A
- Status: PARTIAL
- Evidence: no doctrine-specific closure-control audit doc existed at baseline.
- Gap: missing audit artifact
- Required action: create initial/final doctrine closure audit docs
- Proof dimensions:
  - code proof: N/A
  - test proof: N/A
  - SQLite proof: N/A
  - PostgreSQL proof: N/A
  - dashboard/web proof: N/A
  - Telegram proof: N/A
  - live runtime proof: N/A

## Baseline Conclusion
- P0 open: none
- P1 open:
  - Row 02 trade object completeness
  - Row 04 operator truth completeness
  - Row 16 Telegram trading-alert rendering contract
  - Row 17 dashboard/web operator completeness
- P2 open:
  - Row 19 doctrine-to-spec reconciliation artifact missing
