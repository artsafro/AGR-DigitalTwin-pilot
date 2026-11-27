# tools/hygiene — pinned repo-hygiene (#1950)

`artsafro/repo-hygiene` runs on the pilot from one entry, `tools/hygiene/hygiene.py`; `scripts/hygiene.sh`,
`scripts/hygiene.ps1`, the Claude/Codex hooks and the PR workflow all call it. The workflow is staged as
`tools/hygiene/hygiene.workflow.yml` until someone with a `workflow`-scoped token moves it to
`.github/workflows/hygiene.yml` (`git mv`, nothing else changes).

- **Pin:** `PIN` in `hygiene.py` (a full commit, no submodule, nothing vendored). Bump it in its own PR.
- **Profile:** `docs/architecture/hygiene-profile.yaml`, owned by the pilot (no copy in repo-hygiene is used).
- **Tool location:** `HYGIENE_PROJECT=<local repo-hygiene clone>` (the pinned commit is checked out there as
  `.worktrees/pin-<sha12>`; run `uv sync --locked` in it once so hooks skip uv start-up). Without the variable
  `uvx --from git+https://github.com/artsafro/repo-hygiene@<PIN>` is used (needs read access to that repo).

```sh
scripts/hygiene.sh                  # new findings vs origin/main; exit 0 clean, 1 findings, 2 tool error
scripts/hygiene.sh --base <ref> --json
py -3 tools/hygiene/hygiene.py where
```

Hooks: SessionStart prints the one-door pointer; PreToolUse runs repo-hygiene's fast per-file check (duplicate
operation, stale pointer, 3D policy) only when Write/Edit/apply_patch touches a script or `.md` that is absent
from `origin/main`. It fails open when the tool is not configured; the PR check is the gate.

One owner per check (the pilot guard stays where it already owns the check):

| Check | Owner | repo-hygiene in the pilot profile |
|---|---|---|
| `.ignore` generated blocks | `tools/architecture/search_noise.py`, `duplicate_guard.py` | no `noise.hide/history/manage_block` |
| Doc ownership, plan status | `search_noise.py --check-docs` | no `ownership`, `plans` |
| Job code, route -> job code | `skeleton_guard.py`, `tests/test_live_route_imports.py` | no `jobs` |
| Trail commands `--help` | `tests/test_trail_commands_1895.py` | no `trail` |
| Archive row of a live file (import/config/test graph) | repo-hygiene `live-consumer` | `noise.archive` |
| Duplicate operation | `duplicate_guard.py` whole repo; repo-hygiene per file in the hook and PR diff | `operations` (subset) |
