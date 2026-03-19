from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_openclaw_template_is_secret_free() -> None:
    payload = json.loads((REPO_ROOT / ".openclaw" / "openclaw.json").read_text(encoding="utf-8"))

    telegram = payload["channels"]["telegram"]
    assert "botToken" not in telegram
    assert telegram["tokenFile"] == "__OPENCLAW_HOME__\\secrets\\telegram-bot-token.txt"
    assert telegram["dmPolicy"] == "allowlist"
    assert telegram["allowFrom"] == ["8569633077"]
    assert payload["gateway"]["auth"]["token"] == "__BOOTSTRAP_REQUIRED__"
    assert payload["gateway"]["auth"]["allowTailscale"] is True
    assert payload["gateway"]["trustedProxies"] == ["127.0.0.1", "::1"]
    assert payload["gateway"]["tailscale"]["mode"] == "serve"
    assert "models" not in payload
    assert payload["plugins"]["allow"] == ["telegram"]


def test_openclaw_template_declares_three_isolated_agents() -> None:
    payload = json.loads((REPO_ROOT / ".openclaw" / "openclaw.json").read_text(encoding="utf-8"))

    agents = {entry["id"]: entry for entry in payload["agents"]["list"]}
    assert set(agents) == {"aria-chat", "aria-ops", "aria-code"}
    assert agents["aria-chat"]["workspace"].endswith(r".openclaw\workspaces\aria-chat")
    assert agents["aria-ops"]["workspace"].endswith(r".openclaw\workspaces\aria-ops")
    assert agents["aria-code"]["workspace"].endswith(r".openclaw\workspaces\aria-code")
    assert "edit" in agents["aria-chat"]["tools"]["deny"]
    assert "process" in agents["aria-chat"]["tools"]["deny"]
    assert agents["aria-chat"]["model"]["primary"] == "anthropic/claude-sonnet-4-6"
    assert agents["aria-chat"]["model"]["fallbacks"] == ["ollama/kimi-k2.5:cloud"]
    assert agents["aria-ops"]["model"]["primary"] == "openai/gpt-5.4"
    assert agents["aria-ops"]["model"]["fallbacks"] == ["anthropic/claude-sonnet-4-6"]
    assert agents["aria-code"]["model"]["primary"] == "openai-codex/gpt-5.4"
    assert agents["aria-code"]["model"]["fallbacks"] == ["openai/gpt-5.4", "anthropic/claude-sonnet-4-6"]
    assert agents["aria-ops"]["heartbeat"]["every"] == "15m"


def test_openclaw_cron_template_removes_unsafe_autodeploy() -> None:
    payload = json.loads((REPO_ROOT / ".openclaw" / "cron" / "jobs.json").read_text(encoding="utf-8"))

    assert payload["version"] == 2
    assert payload["timezone"] == "Asia/Riyadh"
    ids = {job["id"] for job in payload["jobs"]}
    assert ids == {
        "approval-review",
        "data-freshness-review",
        "daily-security-audit",
        "git-backup",
        "heartbeat-check",
        "incident-review",
        "premarket-readiness",
        "market-open-verify",
        "pipeline-integrity-review",
        "eod-report",
        "weekly-cron-audit",
        "weekly-progress",
        "weekly-version-check",
    }

    serialized = json.dumps(payload)
    assert "git pull" not in serialized
    assert "pip install -e ." not in serialized
    assert "doctrine once" not in serialized
    assert "openclaw_task_queue.py report" in serialized
    assert "health_check.py --json --emit-task" in serialized
    assert "doctrine_control_review.py data-freshness --json --emit-task" in serialized
    assert "doctrine_control_review.py pipeline-integrity --json --emit-task" in serialized


def test_openclaw_cron_template_uses_standard_operator_sections() -> None:
    payload = json.loads((REPO_ROOT / ".openclaw" / "cron" / "jobs.json").read_text(encoding="utf-8"))

    for job in payload["jobs"]:
        if job["id"] in {"daily-security-audit", "premarket-readiness", "market-open-verify", "approval-review", "incident-review", "eod-report", "weekly-progress"}:
            assert "Current incidents" in job["message"]
            assert "Approved work in flight" in job["message"]
            assert "Next approval needed" in job["message"]


def test_openclaw_cron_template_uses_ops_agent_defaults_for_burn() -> None:
    payload = json.loads((REPO_ROOT / ".openclaw" / "cron" / "jobs.json").read_text(encoding="utf-8"))

    for job in payload["jobs"]:
        assert "model" not in job

    jobs = {job["id"]: job for job in payload["jobs"]}
    assert jobs["approval-review"]["agent"] == "aria-ops"
    assert jobs["eod-report"]["agent"] == "aria-ops"
    assert jobs["weekly-progress"]["agent"] == "aria-ops"


def test_openclaw_hardening_audit_exists() -> None:
    payload = (REPO_ROOT / ".openclaw" / "HARDENING_AUDIT.md").read_text(encoding="utf-8")

    assert "Verified Facts" in payload
    assert "Absent Or Version-Dependent Items Left Unchanged" in payload


def test_openclaw_mission_control_contract_exists() -> None:
    payload = (REPO_ROOT / ".openclaw" / "MISSION_CONTROL.md").read_text(encoding="utf-8")

    assert "## Team View" in payload
    assert "## Calendar View" in payload
    assert "## Pipeline View" in payload
