# Git Batch Review — 9 Batches (STAGED, NOT COMMITTED)
Generated: 2026-05-01 | Repo: /mnt/d/Doctrine/structure-doctrine-engine

---

## Batch 1: Alembic Schema Migrations
**Batch name:** `alembic-schema-v2`
**Purpose:** Apply signal uniqueness and outcome/fill state migrations
**Risk level:** LOW — additive schema changes only
**File count:** 4
**Exact files:**
- M alembic.ini
- M alembic/env.py
- M alembic/script.py.mako
- M alembic/versions/0002_signal_timestamp_uniqueness.py
**Why commit:** 0002 migration is part of the implementation spec — should be in repo
**Why not defer:** Core schema integrity; needed for production
**Rollback method:** `git revert <commit>` or `git reset --hard HEAD~1`

---

## Batch 2: Doctrine Engine Core
**Batch name:** `doctrine-engine-v2`
**Purpose:** Core engine implementation files
**Risk level:** LOW — implementation files, well-tested structure
**File count:** 10
**Exact files:**
- M src/doctrine_engine/__init__.py
- M src/doctrine_engine/alerts/models.py
- M src/doctrine_engine/alerts/telegram_renderer.py
- M src/doctrine_engine/alerts/workflow.py
- M src/doctrine_engine/config/__init__.py
- M src/doctrine_engine/config/settings.py
- M src/doctrine_engine/db/__init__.py
- M src/doctrine_engine/db/base.py
- M src/doctrine_engine/db/session.py
- M src/doctrine_engine/db/types.py
**Why commit:** Core engine changes that are production-ready
**Why not defer:** Blocking other development — engine references these modules
**Rollback method:** `git revert <commit>`

---

## Batch 3: DB Models
**Batch name:** `db-models-v3`
**Purpose:** All database model definitions
**Risk level:** LOW — schema definitions, no data migration
**File count:** 7
**Exact files:**
- M src/doctrine_engine/db/models/__init__.py
- M src/doctrine_engine/db/models/doctrine.py
- M src/doctrine_engine/db/models/features.py
- M src/doctrine_engine/db/models/learning.py
- M src/doctrine_engine/db/models/market_data.py
- M src/doctrine_engine/db/models/signals.py
- M src/doctrine_engine/db/models/symbols.py
**Why commit:** Model definitions are stable and versioned
**Why not defer:** Other teams/tools may depend on these schemas
**Rollback method:** `git revert <commit>`

---

## Batch 4: Signal and Trade Plan Engines
**Batch name:** `engines-v2`
**Purpose:** Core engine logic for signals and trade plans
**Risk level:** MEDIUM — contains trading logic, needs review
**File count:** 2
**Exact files:**
- M src/doctrine_engine/engines/signal_engine.py
- M src/doctrine_engine/engines/trade_plan_engine.py
**Why commit:** Production trading logic — must be versioned
**Why not defer:** High-value code that should be tracked
**Rollback method:** `git revert <commit>`
**Note:** These warrant a pre-commit code review

---

## Batch 5: ML Pipeline
**Batch name:** `ml-pipeline-v2`
**Purpose:** ML learning module — training, prediction, validation, reporting
**Risk level:** MEDIUM — ML code with potential for silent failures
**File count:** 9
**Exact files:**
- M src/doctrine_engine/learning/artifact.py
- M src/doctrine_engine/learning/dataset.py
- M src/doctrine_engine/learning/features.py
- M src/doctrine_engine/learning/predict.py
- M src/doctrine_engine/learning/reporting.py
- M src/doctrine_engine/learning/schemas.py
- M M src/doctrine_engine/learning/train.py
- M src/doctrine_engine/learning/validate.py
**Why commit:** ML pipeline is a core differentiator — must be versioned
**Why not defer:** Experiment tracking depends on committed code
**Rollback method:** `git revert <commit>`

---

## Batch 6: Product / Operator Module
**Batch name:** `product-v2`
**Purpose:** Doctrine product layer — CLI, control, launcher, state, web
**Risk level:** MEDIUM — operator-facing code, lots of surface area
**File count:** 12
**Exact files:**
- M src/doctrine_engine/product/__init__.py
- M src/doctrine_engine/product/adapters.py
- M src/doctrine_engine/product/cli.py
- M src/doctrine_engine/product/control.py
- M src/doctrine_engine/product/doctrine_tracking.py
- M src/doctrine_engine/product/launcher.py
- M src/doctrine_engine/product/ml_dataset.py
- M src/doctrine_engine/product/operator_config.py
- M src/doctrine_engine/product/service.py
- M src/doctrine_engine/product/state.py
- M src/doctrine_engine/product/sync.py
- M src/doctrine_engine/product/web.py
**Why commit:** Large batch — high value but requires thorough review
**Why not defer:** Many interdependencies; deferring delays all dependent work
**Rollback method:** `git revert <commit>`

---

## Batch 7: Regime and Runner
**Batch name:** `regime-runner-v2`
**Purpose:** Regime classification and pipeline runner
**Risk level:** MEDIUM — pipeline orchestration and regime logic
**File count:** 4
**Exact files:**
- M src/doctrine_engine/regime/engine.py
- M src/doctrine_engine/regime/models.py
- M src/doctrine_engine/runner/models.py
- M src/doctrine_engine/runner/pipeline.py
**Why commit:** Pipeline order and regime gating are critical paths
**Why not defer:** Testing depends on committed pipeline code
**Rollback method:** `git revert <commit>`

---

## Batch 8: Tests (Comprehensive)
**Batch name:** `tests-v2`
**Purpose:** Comprehensive test suite
**Risk level:** LOW — tests don't affect production, they protect it
**File count:** 20
**Exact files:**
- M tests/alerts/test_workflow_decision.py
- M tests/config/test_settings.py
- M tests/engines/test_signal_engine_bias_and_setup.py
- M tests/engines/test_trade_plan_engine_gating.py
- M tests/engines/test_trade_plan_engine_invalidation_targets.py
- M tests/learning/test_ml_pipeline.py
- M tests/product/test_cli.py
- M tests/product/test_control.py
- M tests/product/test_doctrine_tracking.py
- M tests/product/test_launcher.py
- M tests/product/test_service.py
- M tests/product/test_state.py
- M tests/product/test_web.py
- M tests/regime/test_regime_engine_permissions.py
- M tests/runner/test_runner_alert_integration.py
- M tests/runner/test_runner_failures_and_skips.py
- M tests/runner/test_runner_pipeline_order.py
- M tests/test_doctrine_reviews.py
- M tests/test_openclaw_config.py
**Why commit:** Tests are the verification layer — essential for CI/CD
**Why not defer:** Critical for regression prevention as development continues
**Rollback method:** `git revert <commit>`

---

## Batch 9: Config, Docs, and Project Files
**Batch name:** `config-docs-v2`
**Purpose:** Configuration, documentation, and project metadata
**Risk level:** LOW-MEDIUM — config files, documentation
**File count:** 15
**Exact files:**
- M .env.example
- M .openclaw/MISSION_CONTROL.md
- M .openclaw/cron/jobs.json
- M .openclaw/openclaw.json
- M AGENTS.md
- M Quality.md
- M docs/architecture.md
- M docs/doctrine_closure_audit_final.md
- M docs/doctrine_closure_audit_initial.md
- M docs/doctrine_definitions.md
- M docs/event_risk_rules.md
- M docs/final_implementation_verification_final.md
- M docs/regime_rules.md
- M docs/signal_contract.md
- M docs/trade_plan_contract.md
- M docs/universe_rules.md
- M memory/2026-03-15.md
- M pyproject.toml
**Why commit:** Project configuration and documentation must stay in sync
**Why not defer:** Docs and config are lagging behind implementation
**Rollback method:** `git revert <commit>`

---

## Files NOT Recommended for Commit

### Hermès Config (NEW UNTRACKED)
**Files:** hermes/ directory (61 files)
**Reason:** These are Hermes/OpenClaw runtime configs — not part of Doctrine engine repo
**Recommendation:** Move to Doctrine's own hermes profile or .hermes directory

### Docker / DevOps (NEW UNTRACKED)
**Files:** docker-compose.yml, frontend/, n8n/, .n8n/, docs/n8n_week1_runbook.md
**Reason:** Not reviewed, unknown state, potential secrets
**Recommendation:** Review separately before committing

### Debug / Temp Files (NEVER COMMIT)
**Files:** tmp-*.png, tmp-*.db, lifecycle-*.png, panel-*.png, check_db_tables.py, check_dbs.py
**Reason:** Temporary artifacts, binary images, debug scripts
**Recommendation:** Delete — never commit

### Discord Integration (NEW UNTRACKED)
**Files:** Discord.md, Discord/
**Reason:** Not reviewed
**Recommendation:** Review separately

### Project Notes (NEW UNTRACKED)
**Files:** 17-4-2026.md, ORCHESTRATOR.md, PAPER_TRADING_READINESS_CHECKLIST.md, Frontend Skill.md
**Reason:** Inconsistent with project structure
**Recommendation:** Review — some may be useful, most should be archived

---

## Summary Table

| Batch | Name | Files | Risk | Commit Priority |
|---|---|---|---|---|
| 1 | alembic-schema-v2 | 4 | LOW | HIGH |
| 2 | doctrine-engine-v2 | 10 | LOW | HIGH |
| 3 | db-models-v3 | 7 | LOW | HIGH |
| 4 | engines-v2 | 2 | MEDIUM | HIGH |
| 5 | ml-pipeline-v2 | 9 | MEDIUM | MEDIUM |
| 6 | product-v2 | 12 | MEDIUM | MEDIUM |
| 7 | regime-runner-v2 | 4 | MEDIUM | HIGH |
| 8 | tests-v2 | 20 | LOW | HIGH |
| 9 | config-docs-v2 | 18 | LOW-MEDIUM | MEDIUM |

**Total: 86 files across 9 batches**
**Files NOT recommended for commit: ~75**

---
