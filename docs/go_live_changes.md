# Go-Live Changes — 2026-03-16

This file records every change made during the go-live preparation pass.

---

## 1. Fix backup.ps1 — recursive archive growth (HIGH)

**File:** `.openclaw/backup.ps1`

**Problem:** `backup.ps1` copies the entire `.openclaw` directory into each backup archive. `.openclaw/runtime/backups` is inside `.openclaw`, so every archive includes all prior archives. This caused exponential size growth: 193KB → 2.5GB in ~32 hours. The latest archive was 0 bytes because `Compress-Archive` ran out of memory/space.

**Fix:** After copying `.openclaw` into the staging area, immediately remove the `runtime/` subdirectory from the staging copy before zipping. The `runtime/` directory contains only operational state (logs, prior archives) — not config — so it should never be archived.

**Change:** Added 3 lines after the `Copy-Item .openclaw` call:
```powershell
$runtimeInStaging = Join-Path $stagingRoot "repo-openclaw\runtime"
if (Test-Path -LiteralPath $runtimeInStaging) {
    Remove-Item -LiteralPath $runtimeInStaging -Recurse -Force
}
```

---

## 2. Fix backup.ps1 — staging dir cleanup failure (MEDIUM)

**File:** `.openclaw/backup.ps1`

**Problem:** `Remove-Item` on the staging directory after `Compress-Archive` fails with exit code 1 because `Compress-Archive` holds file handles open. Since `$ErrorActionPreference = "Stop"`, this throws, triggers the catch block, and creates an `ops-backup-failure` task — even though the archive was already created successfully.

**Fix (two parts):**

1. Force .NET GC collection before `Remove-Item` to release file handles held by `Compress-Archive`:
   ```powershell
   [System.GC]::Collect()
   [System.GC]::WaitForPendingFinalizers()
   ```

2. Use `-ErrorAction SilentlyContinue` on the final `Remove-Item` so a residual handle lock doesn't fail a successful backup. Orphaned staging dirs are cleaned up at the start of the next run by the new cleanup block.

3. Added orphaned staging dir cleanup at the start of the `try` block:
   ```powershell
   Get-ChildItem -Path $env:TEMP -Filter "openclaw-backup-*" -Directory -ErrorAction SilentlyContinue |
       Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-1) } |
       ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
   ```

---

## 3. Commit untracked operator docs and tests

**Files committed:**
- `docs/operator_handoff_pack.md` — complete operator guide: daily checklist, dashboard page meanings, alert state glossary, trade review checklist, system boundary definitions
- `tests/test_doctrine_reviews.py` — control plane doctrine review tests (data freshness and pipeline integrity checks)

Both files were complete and passing but not yet added to git.

---

## 4. Close resolved ops tasks

**Tasks moved from `proposed` → `done`:**

- `ops-gateway-watchdog`: The gateway self-recovered on 2026-03-14T03:48. Watchdog state shows `failureCount=0`. Gateway log confirms fresh healthy start on 2026-03-16T00:47. No code change required — the watchdog correctly detected and triggered restart; gateway recovered within ~5 minutes. Incident closed.

- `ops-backup-recursive-growth`: Fixed by change #1 above.

- `ops-backup-staging-cleanup`: Fixed by change #2 above.

- `incident-backup-20260315`: Root cause was the backup.ps1 staging issues fixed by changes #1 and #2. Closed.

---

## 5. Production DB URL — no action required

**Finding:** The `.env` file already contains `SDE_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/doctrine`. This system is a local operator tool by design — the database is localhost. No production remote DB URL is needed. The "Open Unknown" in CLAUDE.md was based on the assumption of a remote deployment, which is not the intended deployment model.

**Action:** Updated CLAUDE.md to close this open unknown.

---

## 6. Git remote — already configured (no action needed)

**Finding:** Remote `origin` is already configured pointing to `https://github.com/alnahdi1988/lana.git` and branch is already named `main`. The CLAUDE.md "Git State" section was outdated and has been updated to reflect the current state.

**Note:** `.openclaw/`, `tasks/`, `CLAUDE.md`, `scripts/`, and `src/doctrine_engine/control_plane/` are intentionally excluded from git via `.git/info/exclude` — they are local operational files only.

---

---

## 3b. Fix backup.ps1 — archive retention (HIGH)

**File:** `.openclaw/backup.ps1`

**Problem:** The original pruning logic removed archives older than 14 days. Since the recursive bug created 31 archives in 2 days, no archives qualified for pruning — they were all less than 14 days old. This left 24.64 GB of archives in `runtime/backups`, causing staging copy failures.

**Fix:** Replaced age-based pruning with count-based pruning: retain the 7 most recent archives and remove the rest. This caps total archive count permanently, regardless of how frequently backups run.

**Change:** Replaced the `Get-ChildItem | Where-Object { LastWriteTime -lt -14days }` line with:
```powershell
$allArchives = Get-ChildItem -LiteralPath $paths.RuntimeBackupDir -Filter "*.zip" | Sort-Object LastWriteTime -Descending
if ($allArchives.Count -gt 7) {
    $allArchives | Select-Object -Skip 7 | Remove-Item -Force
}
```

---

## Summary

| # | Change | File(s) | Status |
|---|---|---|---|
| 1 | Exclude runtime/ from backup staging | `.openclaw/backup.ps1` | Done |
| 2 | Fix staging cleanup (GC flush + SilentlyContinue + orphan purge) | `.openclaw/backup.ps1` | Done |
| 3 | Fix archive retention (count-based, keep 7) | `.openclaw/backup.ps1` | Done |
| 4 | Commit operator_handoff_pack.md + test_doctrine_reviews.py | `docs/`, `tests/` | Done |
| 5 | Close 6 resolved ops tasks (4 backup + 1 gateway + 1 incident) | `tasks/proposed.md`, `tasks/done.md` | Done |
| 6 | Production DB URL closed as non-issue (localhost by design) | `CLAUDE.md` | Done |
| 7 | Git remote | — | Deferred — no URL |
