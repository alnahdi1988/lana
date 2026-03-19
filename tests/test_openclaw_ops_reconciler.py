from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / ".openclaw" / "skills" / "openclaw-ops-reconciler" / "reconciler.py"
SPEC = importlib.util.spec_from_file_location("openclaw_ops_reconciler", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_classify_path_claim_uses_exact_bucket_precedence(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "src" / "app").mkdir(parents=True)
    (repo_root / "src" / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / ".openclaw" / "skills" / "demo").mkdir(parents=True)
    (repo_root / ".openclaw" / "skills" / "demo" / "reconciler.py").write_text("", encoding="utf-8")
    (repo_root / ".openclaw" / "runtime" / "backups").mkdir(parents=True)
    (repo_root / ".openclaw" / "runtime" / "backups" / "latest.zip").write_text("", encoding="utf-8")
    (repo_root / "docs").mkdir()
    (repo_root / "docs" / "handoff.md").write_text("# note\n", encoding="utf-8")

    snapshot = MODULE.GitSnapshot(
        available=True,
        head="abc123",
        latest_commit="abc123 add main",
        tracked_files=frozenset({"src/app/main.py", "docs/handoff.md"}),
        head_files=frozenset({"src/app/main.py"}),
        origin_diff_files=frozenset({"src/app/main.py"}),
        worktree_files=frozenset(),
        origin_ref="origin/main",
        error=None,
    )
    matcher = MODULE.ExcludeMatcher([".openclaw/"])

    committed, _, _ = MODULE.classify_path_claim("src/app/main.py", repo_root, snapshot, matcher)
    local_only, _, _ = MODULE.classify_path_claim(
        ".openclaw/skills/demo/reconciler.py", repo_root, snapshot, matcher
    )
    runtime_only, _, _ = MODULE.classify_path_claim(
        ".openclaw/runtime/backups/latest.zip", repo_root, snapshot, matcher
    )
    doc_only, _, _ = MODULE.classify_path_claim("docs/handoff.md", repo_root, snapshot, matcher)

    assert committed == "committed"
    assert local_only == "local-only"
    assert runtime_only == "runtime-only"
    assert doc_only == "doc-only"


def test_flag_mixed_summary_requires_explicit_labels() -> None:
    unlabeled = "Updated src/app/main.py and .openclaw/skills/demo/reconciler.py in the same task."
    labeled = "Committed: src/app/main.py. Local-only: .openclaw/skills/demo/reconciler.py."

    assert MODULE.flag_mixed_summary(unlabeled, ["committed", "local-only"]) is True
    assert MODULE.flag_mixed_summary(labeled, ["committed", "local-only"]) is False


def test_resolve_token_prefers_heading_scoped_skill_file(tmp_path: Path) -> None:
    repo_root = tmp_path
    skill_dir = repo_root / ".openclaw" / "skills" / "openclaw-ops-reconciler"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")

    basename_index = {"skill.md": ["docs/another/SKILL.md", "other/SKILL.md"]}
    resolved = MODULE.resolve_token_to_path(
        "SKILL.md",
        repo_root,
        basename_index,
        "openclaw-ops-reconciler",
    )

    assert resolved == ".openclaw/skills/openclaw-ops-reconciler/SKILL.md"
