# System audit, stage 0: repos, slices, template, merge procedure (#1298)

Plan only. Nothing in this document moves, edits or deletes a file; neither do the slice cards it defines.
Sequence set by Artem (2026-11-13): **compact the system → improve → second compaction = first decent MVP →
only then the automated self-improvement loop** (weekly calibrator starts after the audit).
Rule from the same request: documents, folders and tools are not split without need; a proposal that creates a
new file or folder must say why merging into an existing one does not work.

Measured 2026-11-14 on pilot `origin/main` `fd1c1738`, `hermes_kanban` `main` (local clone, last commit
2026-11-13), `max-viz` (`C:/x/max-ui`, last commit 2026-11-13). Commands: `git ls-files`, `git rev-list --count
--since=30.days HEAD`, `du -sh`; GitHub sizes from `gh repo list artsafro --json diskUsage,pushedAt`.
The current `gh` token sees only 7 public/visible repos; the private ones (`hermes_kanban`, `max-viz`,
`GeoAGR-private`, `agr-lab`, `codex-3ds-max`) were measured from local clones or not measured (marked).

## 1. Repositories and verdicts

| Repo | Where | Size | Activity | Verdict |
|---|---|---|---|---|
| `AGR-DigitalTwin-pilot` | `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin` | 3 056 tracked files; `.git` 115 MB; GitHub 49.9 MB | 3 382 commits / 30 d; 165 worktrees; 359 local / 147 remote branches | **active**, main repo; audit first (10 slices, §2.1); collapse inside itself, stays a separate repo |
| `hermes_kanban` | `C:/Users/artsafro/hermes_kanban` + runtime `~/.hermes/` | 426 tracked files, 79 MB on disk (`kpi/` 39 MB, `logs/` 28 MB) | 294 commits / 30 d | **active** (board, crons, scripts); audit second (5 slices, §2.2) |
| `max-viz` (local folder `max-ui`) | `C:/x/max-ui` | 283 tracked files; 914 MB on disk (`build/` 397 MB, `backups/` 42 MB) | 293 commits / 30 d; 20 worktrees | **active** (Max UI, Viz tools); audit third (5 slices, §2.3). AGR Tools itself lives in pilot `adapters/max/agr_tools` (124 files) |
| `agr-lab` | lab laptop DESKTOP-IHMQLNS | not measured (private, not visible to the current token) | runs pilot CI from `lab-ci.toml` | **active infrastructure**, out of compaction scope; only the `lab-ci.toml` interface is checked (slice P09) |
| `GeoAGR-private` | `C:/x/GeoAGR-private` | 57 920 tracked files, 3.9 GB | 2 332 commits / 30 d, last 2026-11-05 | **archive, read-only** (decompiled GeoAGR 13.64 reference); no audit; pilot only keeps pointers to it |
| `AGR-DigitalTwin` | `C:/Users/artsafro/AGR-DigitalTwin` | 893 tracked files; GitHub 24.8 MB | 15 commits / 30 d, last 2026-10-18 | **candidate to close** (predecessor of pilot): check unique branches against pilot, then archive on GitHub |
| `AGR_Project` | GitHub only (bundle in pilot backlog H11) | GitHub 23.1 MB | pushed 2026-11-04 | **archive**: `docs/agr/case_studies` link its PRs #2, #4, #17 and issues #11, #12; mark the repo archived, keep links |
| `DigitalTwinProject-Claude` | `C:/Users/artsafro/DigitalTwinProject` | 110 tracked files | last 2026-10-06, 0 commits / 30 d | **candidate to close** (bundle already in backlog H11) |
| `codex-3ds-max` | GitHub only | not measured (private) | created 2026-11-04, one commit (seen in a hermes transcript) | **candidate to close** (empty Max-tools workspace) |
| `Artem-Test`, `my`, `binance-spot-api-docs`, `pandamania-opensea-netlify` | GitHub | 0–3.3 MB | unrelated to AGR | **out of scope** (not AGR); `Artem-Test` is a candidate to close |

Closing or archiving a repo is Artem's decision and is listed in the merge plan, never done by a slice card.

## 2. Slices

Rules for every slice:
- One slice = one card = one agent; slices of one repo are **disjoint** and together **cover every tracked
  file** (each path belongs to the slice with the longest matching prefix in the block below).
- All slices of one repo read the same frozen commit (`audit_base`, set by the orchestrator when it files the
  cards), so results do not drift while `main` moves.
- Cross-slice facts ("who uses this file") are read from the whole repo with `git grep`; the slice only *judges*
  its own files.
- Existing inventories are reused, not redone: job scripts, `tools/`, `src/dt_ai` entry points and Max AGR Tools
  are already in `docs/research/reuse-1296/data/inventory.csv` (656 rows, #1296).

### 2.1 `AGR-DigitalTwin-pilot` (10 slices)

| Id | Scope | Size at `fd1c1738` | Focus |
|---|---|---|---|
| P01 | rules and state docs: `docs/` (top level, `domain/`, `agents/`, `procedure/`, `scenarios/`, `plans/`, `adr/`, `agr-tools/`, `agr/` read-only KB, `qa/`, `retros/`, …), `standards/`, `schemas/`, `routes/`, `GLOSSARY.md` | 227 files; 28 MB, of which `standards/` 24 MB machine JSON (read the README and shapes only) | contradictions with `docs/decisions.md`, duplicated rules across `domain/` / `agents/` / `procedure/`, oversized `backlog.md` / `decisions*.md` / `pipeline-tools.md`, orphans not in the "Where things are" map |
| P02 | research and experiments: `docs/research/`, `docs/experiments/`, `docs/evidence/`, `docs/methods/`, `experiments/`, `evals/`, `benchmark/` | 542 files, 7.3 MB | finished research still in the tree (archive candidates like `archive/2026-11`), experiment docs duplicated between `docs/experiments` and `experiments/`, evals without a runner |
| P03 | `src/` (`dt_ai`, `twinqa`, `agr_mcp`) | 155 files, 2.1 MB | dead modules (no import, no CLI, no test), duplicate helpers, modules duplicated by `tools/` |
| P04 | `tools/` | 306 files, 3.1 MB | one-off research scripts (`tools/research` 78), duplicates of `src/`, hooks still wired vs unwired; reuse #1296 rows |
| P05 | `adapters/` (`max/agr_tools` 124, `sketchup`, `cad`, `revit`, `blender`) | 141 files, 2.8 MB | AGR Tools structure vs `max-viz`, dead MAXScript, single-file adapters; reuse #1296 rows |
| P06 | `jobs/` (21 job folders) | 684 files, 10 MB; 290 job scripts already inventoried by #1296 | job folders without `passport.json` / `sources.json`, finished jobs to archive (as `docs/ARCHIVE.md` phase 2), duplicated job scripts → `agr` CLI candidates (only point to #1296) |
| P07 | `tests/` and `test-polygon/` | 814 files, 9 MB (`tests/` root alone 299 files) | tests of removed code, duplicated fixtures, flat `tests/` root, `test-polygon/expected` 113 files |
| P08 | `library/`, `technical_library/`, `assets/` | 104 files, 4.8 MB | overlap `library/` vs `technical_library/` vs `max-viz/library`, entries without a consumer |
| P09 | agent surface: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `.agents/` (skills), `.claude/`, `.codex/`, `.pi/`, `.github/`, `skills-lock.json`, `lab-ci.toml`, `pyproject.toml`, `uv.lock`, `.gitignore`, `.gitattributes` | 83 files, 0.6 MB | what an agent must read before work (tokens), duplicated skills/commands across `.agents` / `.claude` / Hermes profiles, stale instructions |
| P10 | hygiene, untracked: `logs/`, `.venv`, ignored `jobs/*/outputs` and `data/`, 165 `.worktrees`, 359 local / 147 remote branches, 19 tags, scratch `C:/x` (5 915 dirs, of which 4 316 `ci-receipt-*`, 301 `review-*`, 927 `t_*`), Drive `AGR-evidence/` | no tracked files | stale worktrees and branches (merged/closed PR), scratch retention rule, which generated output may be committed |

### 2.2 `hermes_kanban` (5 slices)

| Id | Scope | Focus |
|---|---|---|
| H01 | `profiles/` (17: SOULs, `COORDINATION_RULES.md`, `PROMPT_RULES.md`, `ACCEPTANCE_TABLE.md`, `models.yaml`) + read-only `~/.hermes/profiles/*/SOUL.md` and model settings | rules repeated across SOULs and the card policy, contradicting rules, profiles with no lane (e.g. `dt-worker-xai` idle), Kimi lane missing |
| H02 | `scripts/` (55) + read-only `~/.hermes/scripts/` (41) + `~/.hermes/cron/jobs.json` (31 jobs) | 33 scripts exist in both places (32 identical, 1 drifted): one source of truth + deploy step; crons pointing at missing or one-off scripts (`*_116.py`, `notify_cards_20261019.py`) |
| H03 | `docs/`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `skills/`, `experiments/`, `tests/`, `.gitignore`, `.gitattributes` | duplicates of pilot docs (`decisions.md`, `HANDOFF*.md`, `pipeline.md`), stale research |
| H04 | state and metrics: `kpi/` (283 files, 39 MB: `readiness/` 119, `profile_backup_20261019/`), `moltbook/`, `night_queue.json`, `self_queue.json`, `suite_slots.json` | generated files committed, backups in git, retention rule |
| H05 | runtime, untracked: `logs/` (28 MB), `~/.hermes/kanban.db` (tasks, archived, workspaces), `hermes_kanban_wt`, `~/.hermes/` backups (`config.yaml.bak-*`) | retention and cleanup rules; read-only SQL, never writes the DB |

### 2.3 `max-viz` (5 slices)

| Id | Scope | Focus |
|---|---|---|
| M01 | `src/` (genplan, viz, pie, panel, theme, studio, startup, overlay, statusbar, macros) | dead startup scripts, duplicates of pilot `adapters/max/agr_tools` |
| M02 | `tools/`, `icons/`, `fonts/`, `themes/`, `vendor/` | one-off tools, third-party files that should not be versioned |
| M03 | `docs/` (own `decisions.md`, `cases.md`, `backlog.md`, `PROJECT_STATE.md`, 4 `HANDOFF*`), `AGENTS.md`, `CLAUDE.md`, `GLOSSARY.md`, `README.md`, `.claude/`, `.github/`, `.gitignore` | a second documentation system next to pilot: merge, link or keep; boundary AGR Tools (pilot) vs Viz tools (max-viz) |
| M04 | `library/` (catalog, needs, tg, flora, maf, mat, `mask_scheme.json`) | overlap with pilot `library/` (flora, maf, materials) |
| M05 | `build/` (tracked part) + untracked `build/` 397 MB, `backups/` 42 MB, 20 worktrees | what is generated, retention |

### 2.4 Machine-readable slice map

The probe in this plan's PR body (`probe_slices.py`) reads this block; P10, H05 and M05 own untracked scope (`untracked`), so only their tracked
prefixes (if any) take part in the coverage check.

```json audit-slices
{
  "repos": [
    {"name": "pilot", "path": "C:/Users/artsafro/agr-pilot/AGR-DigitalTwin", "slices": [
      {"id": "P01", "prefixes": ["docs/", "standards/", "schemas/", "routes/", "GLOSSARY.md"]},
      {"id": "P02", "prefixes": ["docs/research/", "docs/experiments/", "docs/evidence/", "docs/methods/", "experiments/", "evals/", "benchmark/"]},
      {"id": "P03", "prefixes": ["src/"]},
      {"id": "P04", "prefixes": ["tools/"]},
      {"id": "P05", "prefixes": ["adapters/"]},
      {"id": "P06", "prefixes": ["jobs/"]},
      {"id": "P07", "prefixes": ["tests/", "test-polygon/"]},
      {"id": "P08", "prefixes": ["library/", "technical_library/", "assets/"]},
      {"id": "P09", "prefixes": ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", ".agents/", ".claude/", ".codex/", ".pi/", ".github/", "skills-lock.json", "lab-ci.toml", "pyproject.toml", "uv.lock", ".gitignore", ".gitattributes"]},
      {"id": "P10", "prefixes": [], "untracked": ["logs/", ".venv/", ".worktrees/", "jobs/*/outputs/", "data/", "C:/x/", "branches", "tags"]}
    ]},
    {"name": "hermes_kanban", "path": "C:/Users/artsafro/hermes_kanban", "slices": [
      {"id": "H01", "prefixes": ["profiles/"]},
      {"id": "H02", "prefixes": ["scripts/"]},
      {"id": "H03", "prefixes": ["docs/", "AGENTS.md", "CLAUDE.md", "README.md", "skills/", "experiments/", "tests/", ".gitignore", ".gitattributes"]},
      {"id": "H04", "prefixes": ["kpi/", "moltbook/", "night_queue.json", "self_queue.json", "suite_slots.json"]},
      {"id": "H05", "prefixes": [], "untracked": ["logs/", "~/.hermes/kanban.db", "~/.hermes/backups", "hermes_kanban_wt/"]}
    ]},
    {"name": "max-viz", "path": "C:/x/max-ui", "slices": [
      {"id": "M01", "prefixes": ["src/"]},
      {"id": "M02", "prefixes": ["tools/", "icons/", "fonts/", "themes/", "vendor/"]},
      {"id": "M03", "prefixes": ["docs/", "AGENTS.md", "CLAUDE.md", "GLOSSARY.md", "README.md", ".claude/", ".github/", ".gitignore"]},
      {"id": "M04", "prefixes": ["library/"]},
      {"id": "M05", "prefixes": ["build/"], "untracked": ["build/", "backups/", "worktrees"]}
    ]}
  ]
}
```

## 3. Shared slice template

Every slice card produces exactly two new files on its own branch and changes nothing else:
`docs/audit/2026-11/<repo>/<slice-id>.csv` and `docs/audit/2026-11/<repo>/<slice-id>.md` (in the audited repo).

### 3.1 Inventory CSV — one row per tracked file of the slice (untracked slices: one row per directory / branch / worktree)

| Column | Content |
|---|---|
| `path` | repo-relative path (untracked: absolute path, branch or worktree name) |
| `kind` | `doc`, `code`, `test`, `data`, `config`, `generated`, `binary`, `branch`, `worktree`, `dir` |
| `lines`, `bytes` | from the file at `audit_base` |
| `purpose` | one line, from the file's own header / docstring / first heading; `unknown` if none |
| `used_by` | count of `git grep -l` hits on the file name / module / skill name outside the file, plus up to 3 referrers |
| `last_change` | `git log -1 --format=%cs %h -- <path>` |
| `duplicate_of` | path(s) with the same blob SHA, or similarity ≥ 0.8 (`difflib.SequenceMatcher` ratio on text), or the same basename in another folder; empty if none |
| `flags` | any of `dead` (no referrer, not an entry point, not a test target), `oversized` (doc > 300 lines or > 25 KB; code > 800 lines), `fragmented` (≥ 3 docs < 40 lines on one topic in one folder), `contradicts:D<n>`, `stale` (no change for 30 d and refers to a removed path) |
| `proposal` | exactly one of `keep`, `merge`, `move`, `delete`, `archive` (remove from the tree, cite through a tag like `archive/2026-11`), `decide` (needs Artem) |
| `target` | for `merge` / `move`: destination path; empty otherwise |
| `evidence` | the command or quote that proves the proposal (e.g. `git grep -l foo.py → 0`, `D142 says X, file says Y`) |
| `risk` | `low` / `medium` / `high` (high: production route, DCC, user-accepted output, decisions) |

### 3.2 Report MD (≤ 250 lines)

1. Header: repo, slice id, `audit_base`, lane and model, tokens used (from the session/usage log or "not measured").
2. Coverage: tracked files in scope (`git ls-files <prefixes>` count) = CSV rows; untracked scope listed. A gap is
   a `drop list` with the reason per path; a slice with an unexplained gap is `partial`, never `complete`.
3. Findings, each with evidence: duplicates, dead files, oversized / fragmented docs, contradictions with
   `docs/decisions.md` (quote both sides, D-id), overlap with other slices or repos (named, not judged).
4. Proposals table (only rows whose proposal is not `keep`): path → proposal → target → evidence → risk.
5. Questions for Artem (`decide` rows), at most 5, each with a recommendation.
6. Metrics: files, lines, bytes in scope now → after the proposals; for docs also "tokens an agent reads before
   work" if the slice touches the reading path.

### 3.3 Rules for the slice agent

- Read-only: the branch diff against `audit_base` contains only the two added files
  (`git diff --name-status <audit_base>..HEAD` = two `A` lines under `docs/audit/2026-11/<repo>/`). No DCC, no
  network writes, no DB writes, no branch/worktree deletion.
- Measure with scripts, read files only where the scripted signal is ambiguous (heads, not whole files);
  `standards/` and `docs/agr/` are read through their README / INDEX only.
- A proposal that creates a new file or folder needs a line why merging into an existing one does not work.
- Stop at the token budget (§5): write what is done, mark the rest `not audited` in the drop list, status
  `partial`. Never guess a row.
- No issue or PR: push the branch, then `kanban_complete` with metadata `{branch, audit_base, csv, md,
  rows, tracked, status: complete|partial, tokens}`.

## 4. Merge step: slice results → one compaction plan per repo

One merge card per repo, parents = all slice cards of that repo (it starts when they are all done).

1. **Gate.** For each slice: branch exists; diff is exactly the two added files; CSV rows = `git ls-files` count of
   its prefixes at `audit_base` (or the gap is a drop list); every row has a `proposal` from the enum and a
   non-empty `evidence` when the proposal is not `keep`; status `complete`. A failing slice is re-filed once on a
   different lane; if it fails again, the plan lists it as `not audited` (never silently skipped).
2. **Collect.** `git merge --no-edit origin/<slice branch>` for every slice into the merge branch (no conflicts:
   each slice adds different files), then one combined `docs/audit/2026-11/<repo>/inventory.csv`.
3. **Reconcile.** Cross-slice pairs (`merge` target in another slice, a `delete` of a file another slice still
   counts as a referrer, duplicates across slices or repos) are resolved by evidence; an unresolved pair becomes a
   `decide` item. `decide` items of all slices are batched (≤ 5 questions per batch, with recommendations, as in
   `docs/agents/task-intake.md`).
4. **Package.** Proposals are grouped into work packages, each one future PR of one owner, ordered by risk:
   (a) delete dead / generated, (b) archive finished material through a tag + `docs/ARCHIVE.md` row, (c) merge
   duplicated docs and code, (d) move. Each package: paths, expected metrics delta (files, lines, MB, reading-path
   tokens), tests to run, rollback (`git restore --source <tag>`).
5. **Plan.** `docs/audit/2026-11/<repo>/PLAN.md` (≤ 300 lines): summary metrics now → after, packages, `decide`
   batch, repo verdicts for closing/archiving. One PR per repo; the PR is the approval surface.
6. **Approval.** Artem approves, rejects or edits each package in the PR. Only approved packages become
   implementation issues, filed by the orchestrator. After all packages land, the per-slice reports are removed
   from the tree and cited through the archive tag, so the audit itself does not add permanent fragmentation.
7. **Next round.** The second compaction (after "improve") reuses this template and the slice map, refreshed by
   the probe published in this plan's PR body (`probe_slices.py`: ≤ 10 slices, every tracked file in exactly one).

Order: pilot (P01–P10 in parallel, at most 10 agents), its merge card; then `hermes_kanban` (H01–H05) and its
merge; then `max-viz` (M01–M05) and its merge. Full suites are not needed for slice cards (no code changes).

## 5. Lanes and token budgets

Lanes available on the board today (`hermes_kanban/profiles/models.yaml`, `~/.hermes/profiles/`):
`dt-worker-deepseek` (deepseek-v4-pro), `dt-worker-cursor` (Cursor CLI, driver gpt-6-luna),
`dt-worker-codex` (gpt-6.1-sol), `dt-worker` (Claude), `dt-reviewer` (gpt-6.1-sol).
**Kimi has no lane yet**: provider `kimi-coding` needs `KIMI_API_KEY` and a `dt-worker-kimi` profile — Artem's
setup; until then its slice falls back to DeepSeek.

Budget = input tokens per card (every tool call resends the context, so the budget is a cap, not an estimate of
file size), output ≤ 30 k. Size basis: 1 KB of text ≈ 250 tokens; slices read scripted listings plus heads, not
whole files.

| Slice | Lane | Fallback | Budget (input) | Why |
|---|---|---|---|---|
| P01 rules/state docs | Codex | Claude | 400 k | contradictions with decisions need judgement |
| P02 research/experiments | DeepSeek | Cursor | 350 k | many files, mostly mechanical |
| P03 `src/` | Cursor | Codex | 250 k | import graph, code reading |
| P04 `tools/` | DeepSeek | Cursor | 300 k | #1296 rows already exist |
| P05 `adapters/` | Cursor | Codex | 250 k | MAXScript + Python, #1296 rows |
| P06 `jobs/` | DeepSeek | Cursor | 300 k | structure checks, #1296 rows |
| P07 tests | Kimi (trial) | DeepSeek | 350 k | large, mechanical; a fair first trial for a new lane |
| P08 libraries | Cursor | DeepSeek | 200 k | small |
| P09 agent surface | Claude | Codex | 200 k | instructions all agents read; error is costly |
| P10 hygiene | DeepSeek | Cursor | 150 k | scripted only |
| H01 profiles | Codex | Claude | 200 k | rule contradictions |
| H02 scripts + crons | DeepSeek | Cursor | 200 k | diff of two copies, cron map |
| H03 docs/tests | DeepSeek | Cursor | 150 k | small |
| H04 kpi/state | DeepSeek | Cursor | 150 k | generated files |
| H05 runtime | Cursor | DeepSeek | 150 k | read-only SQL on `kanban.db` |
| M01 `src/` | Cursor | Codex | 200 k | Max Python/MAXScript |
| M02 tools/assets | DeepSeek | Cursor | 120 k | small |
| M03 docs | Codex | Claude | 200 k | boundary with pilot docs |
| M04 library | DeepSeek | Cursor | 120 k | small |
| M05 build/backups | DeepSeek | Cursor | 80 k | scripted only |
| Merge pilot | Claude | Codex | 400 k | judgement, packaging |
| Merge hermes / max-viz | Codex | Claude | 250 k each | smaller |
| Review of each merge PR | `dt-reviewer` | — | 200 k each | evidence spot-check: 10 random rows per slice re-run |

Total ≈ 5.8 M input tokens for the whole audit (pilot 3.35 M including merge and review; hermes 1.3 M; max-viz
1.17 M). The lane per card is a proposal; the orchestrator may swap lanes by quota on the day.

## 6. How the orchestrator files the cards

After Artem's ok on this plan: one issue per slice from the drafts in this plan's PR body, labels
`ready-for-agent`, `audit`, `level:easy` (P01, P09, merges: `level:hard`); the card body carries the lane
(`assignee`), `audit_base`, the slice prefixes from §2.4, this template (§3) by link, the budget as
`max_runtime_seconds` and the stated input cap, and the line "No PR: push the branch and kanban_complete" which
overrides the default card policy. The merge card is created with `parents` = the slice cards.
