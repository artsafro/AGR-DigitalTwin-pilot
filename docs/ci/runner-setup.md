# Self-hosted CI runner (execution PC)

[D222] — the repository is private (since 2026-11-04), so a self-hosted GitHub Actions runner is allowed.
A light non-DCC test run runs per pull request; the full suite before merge stays the local `merge_batch`
receipt (`hermes_kanban/scripts/agr_automerge.py` and `hermes_kanban/skills/agr-kanban-orchestration/scripts/merge_batch.py`).
Revises [D122] (which said no self-hosted runner on a public repository).

## Workflow

`.github/workflows/python-app.yml` runs on `pull_request` (and `workflow_dispatch`) on a self-hosted
Windows runner with labels `self-hosted, windows, agr`. It runs the non-DCC suite:

```
uv run pytest -q -m "not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max"
```

The explicit `-m` replaces the `pyproject.toml` `addopts` `-m` (which lacks `not native_max`) and matches
the merge-gate exclusion. It excludes the DCC / Max / perf markers, serializes runs with `concurrency`
(one job at a time), and skips fork PRs via the job guard
`github.event.pull_request.head.repo.full_name == github.repository`, so untrusted fork code never runs on
the self-hosted runner.

## Runner registration (the orchestrator registers it as a Windows service)

1. Get a registration token (requires a token with runner-management scope; the worker `gh` PAT does not
   have it and returns 403):

   ```bash
   gh api -X POST repos/artsafro/AGR-DigitalTwin-pilot/actions/runners/registration-token --jq .token
   ```

2. Download the runner for the PC OS/arch (win-x64) from https://github.com/actions/runner/releases and
   unpack it to e.g. `C:/actions-runner`.
3. Configure and register it:

   ```bash
   cd C:/actions-runner
   ./config.cmd --url https://github.com/artsafro/AGR-DigitalTwin-pilot --token <TOKEN> --name agr-exec-pc --labels self-hosted,windows,agr --runasservice
   ```

4. Install and start it as a service:

   ```bash
   ./svc.cmd install
   ./svc.cmd start
   ```

5. Verify: repo Settings → Actions → Runners shows the runner Idle; the next PR run goes green.
