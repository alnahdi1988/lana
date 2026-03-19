# Operator Profile — Saleh Alnahdi
**Doctrine Engine | System Owner**

---

## 1. Role

Saleh Alnahdi is the sole operator and architect of Doctrine Engine — a long-only structural signal platform for U.S. equities built for autonomous, production-grade operation.

He is not a user of the system. He is the owner, designer, and final authority over it.

---

## 2. Primary Objective

Run a fully automated trading intelligence system that:
- identifies high-quality long setups using structural doctrine
- generates signals, trade plans, and ranked alerts without manual intervention
- compounds capital through disciplined, system-driven execution
- operates continuously with minimal daily operator involvement

---

## 3. System Architecture Ownership

Saleh controls all five Doctrine layers:

| Layer | Responsibility |
|---|---|
| Data & Universe | Polygon ingestion, universe filtering, bar storage |
| Structural Doctrine | BOS, CHOCH, zones, patterns, regime, event risk |
| Trade Planning | Entry, confirmation, invalidation, TP1, TP2, trail |
| Ranking & Learning | Signal confidence, grading, outcome tracking, retraining |
| Delivery & Monitoring | Telegram alerts (A+/A only), health, reporting |

---

## 4. Operating Philosophy

- **Deterministic over probabilistic.** Doctrine logic is rule-based. ML ranks doctrine-valid setups only — it does not override them.
- **Prefer NONE over forced signals.** Quality gate is non-negotiable.
- **Delayed-data honesty.** No assumptions of real-time data access.
- **Build once, run indefinitely.** Every component is designed for unattended operation.

---

## 5. Agent Authority Model

| Agent | Authority |
|---|---|
| `aria-chat` | Intake, approvals, operator summaries, escalation |
| `aria-ops` | Health, incidents, cron, backups, recovery |
| `aria-code` | Approved implementation and focused tests only |

Saleh is the only authority for:
- approving `proposed` → `approved` task transitions
- doctrine-definition changes
- trading authority decisions
- ranking model promotion to production

No agent acts outside its domain without explicit operator instruction.

---

## 6. Collaboration Standards

Anyone working on Doctrine Engine must understand:

- Every durable change requires a task in the queue with `affected_layer`, `priority`, `approval_state`, and `acceptance_criteria`
- No temporary or incomplete implementations reach production
- Every component must be structurally sound, testable, and production-ready
- Secrets, tokens, and `.env` contents are never exposed in logs, messages, or agent outputs

---

## 7. Strategic Principle

> **Build the system right. Let the system run.**

Every engineering decision in Doctrine Engine is made with long-term autonomous operation as the target state.
