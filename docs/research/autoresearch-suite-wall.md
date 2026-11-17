# Autoresearch: merge-gate wall time (#1615)

Status: contract frozen; first baseline rejected (environment failure); repaired baseline pending.
No speed-up or acceptance claimed.

## Frozen contract (before optimization)

- Baseline source: `origin/main` at start of this resumed run,
  `c62cedddde111b8732c6ea48dafc34946d9dc992`. One writing worktree:
  `t_82b1bc95`, branch `improve/issue-1615-autoresearch-round-2-full-test-suite-wal`.
- Scope: test setup/fixtures, redundant subprocess work and measured slow paths;
  observational harness snapshots in this directory. Delivered packages untouched.
- Metric: elapsed `perf_counter` seconds around the **whole exact merge-gate
  subprocess**, excluding slot/idle wait. Queue time is reported separately.
- Canonical command, read from the live `merge_batch.py` on 2026-11-17:

  ```text
  uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_82b1bc95-wall-baseline-001 -m "not blender and not dcc and not acad and not perf and not job and not max and not panel_texture and not native_max" -rf -n 4
  ```

  Only basetemp changes per invocation. The existing merge command already uses
  four workers; this is NOT a new xdist policy or selection change. Research-only
  observation is loaded via `PYTEST_PLUGINS`, with the same observer for every run;
  it records controller phase reports and all workers' selected IDs without changing
  collection, scheduling, outcomes or assertions. Child-process inheritance is
  cleared after startup so nested pytest cannot overwrite the evidence.
- Every measurement goes through
  `python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card t_82b1bc95 -- ...`.
  No runner/CI/coordination policy edits. Never run concurrently with a merge batch.
- Scheduling: wait for all live merge-chain/batch processes and foreign suite holders
  to drain before requesting a slot. Inside the slot, require no foreign live holder;
  monitor while running. Contamination is an invalid measurement, not a slow/fast
  success. Preserve its log; stop only the owned command tree.
- Orchestrator clarification on this card, 2026-11-17 06:00: measurement-only
  exception to rule 68; one own idle baseline, one run per candidate, then two
  additional final confirmations. This supersedes three baseline runs in the original
  issue. Final evidence remains three final runs and their median. Historical batch
  receipts describe variability only; they are not interchangeable baseline samples.
- Keep only >=5% wall reduction versus the previous retained result with exact
  selected-node/outcome parity. No deselection, skips, weaker checks/tolerances,
  hidden markers, test deletion or modified production inputs. Observe/propose/log;
  retained changes require a normal PR/review, never automatic merge.
- Stop at <=1800 seconds, 8 cumulative measurement/experiment hours, or three
  consecutive rounds below 2% gain (both raw and retained gain). Confirm target on
  all three final measurements; report their median, no discarded outliers.
- Parity: every worker's sorted selected-ID list must agree; each selected ID must
  have a complete terminal outcome. No duplicate phases, missing teardown, failed,
  error, xpassed or unknown outcome may pass. Compare sorted `(nodeid, outcome)`
  lists against baseline; empty diff required. Also retain phase records, counts,
  source SHA before/after, argv, package versions and SHA-256 manifests.
- Resume protocol: one detached observer-only run writes immutable evidence under
  `C:/x/autoresearch-suite-wall/`. Record PID and output path here/on the card, then
  block while measuring; orchestrator resumes the card when the JSON exists.
  Never launch another measurement before verifying the recorded process exited.

## Historical context (not baseline/parity proof)

Actual `hermes_kanban/kpi/manual_merge_2026111*.json` receipts read on 2026-11-17:

| Receipt | Tested SHA (prefix) | Passed | Pytest wall seconds | Workers |
| --- | --- | ---: | ---: | ---: |
| `manual_merge_20261116p1595.json` | `02bf03a4` | 27125 | 1557.23 | 4 |
| `manual_merge_20261116q.json` | `ddb23e8c` | 26594 | 3517.21 | 4 |
| `manual_merge_20261116x1476.json` | `84fb0f25` | 26728 | 5015.81 | 4 |
| `manual_merge_20261116s.json` | `c62ceddd` | 27218 | 1961.42 | 4 |

These are **different node counts and different revisions**, not the same frozen
corpus. They suggest contention but do not establish its causal effect or prove
speed-up. The original request's 58:37 is pytest's summary duration, whereas this
contract measures the entire command including uv/startup/collection/teardown.

## Acceptance/probe plan (before harness implementation)

| Requirement | Concrete input | Expected | Probe |
| --- | --- | --- | --- |
| Real xdist IDs/outcomes | Generated pass/skip/xfail module, n=2 | Complete per-worker equal selection; exact outcomes | `probe_observer.py` |
| No evidence clobber | Existing events/output file | Nonzero; original bytes unchanged | `probe_observer.py` |
| Nested subprocess isolation | Test launches a fresh pytest | Outer ledger contains only outer nodes | `probe_observer.py` |
| Fail closed | Empty/partial/duplicate/unknown/nonfinite report | Reject, never pass | `probe_observer.py` |
| Frozen parity | Baseline vs changed outcome/selection | Nonempty diff/rejection | `probe_observer.py` |
| No merge overlap | Live merge chain or foreign slot holder | Wait before launch; invalidate/abort if contaminated | runner preflight + live sampling |
| No stale source | HEAD or tracked content changes during run | Invalid; keep raw evidence | runner source snapshots |

## Round log

| Round | Hypothesis / source | Metric | Parity | Decision |
| --- | --- | --- | --- | --- |
| B0 (`baseline-001`) | Unmodified test corpus from `c62ceddd`; harness HEAD `1c713b04` | 1667.3542925 s; exit 1; 27212 passed / 193 skipped / 6 failed | rejected | invalid: detached PATH selected Windows WSL bash, not Git Bash |
| B1 (`baseline-002`) | Same test corpus, command and observer; repair subprocess PATH only | pending | pending | replacement baseline pending |

B0 is below 1800 seconds as an **invalid observation only**, not a target success,
retained optimization, or parity reference. No optimization has been implemented,
retained or dropped yet. Baseline/final table and parity diff require valid execution.

### B0 diagnosis and environment-only repair (2026-11-17)

- Receipt: `C:/x/autoresearch-suite-wall/baseline-001.json`, `valid=false`,
  exit 1; source SHA and source signature unchanged. Raw evidence is preserved;
  its artifact hashes are in the receipt (a small copy is committed alongside this note).
- All six failures are `tests/test_session_context.py::test_rotation_command_from_subdirectory`
  bash variants: `C:/Windows/system32/bash.EXE` emits
  `Bash/Service/CreateInstance/CreateVm/HCS/HCS_E_HYPERV_NOT_INSTALLED`
  (confirmed by fresh `--version`, UTF-16LE decoded stdout).
  PowerShell variants pass. Prior launcher/interpreter/inside PIDs
  `1114028`, `1114164`, `1124180` are absent in a fresh Win32 process query.
- `git diff origin/main HEAD -- tests/test_session_context.py .claude/commands/handover.md
  .claude/commands/takeover.md tools/hooks/session_context.py` is empty.
- Own detached probe checkout `tmp/main-probe` at `origin/main=f4ac0fb1`:
  same 12-node command with System32 first on PATH reproduces **6 failed / 6 passed**
  in 60.13 s; normal Git Bash PATH yields **12 passed** in 66.36 s.
  Logs: `tmp/main-badpath.log`; successful command output on card.
- Affected command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
  --basetemp=C:/x/t_82b1bc95-main-goodpath
  tmp/main-probe/tests/test_session_context.py::test_rotation_command_from_subdirectory`.
  Bad-PATH reproduction runs the same selector in `tmp/main-probe`, unique
  `--basetemp=C:/x/t_82b1bc95-main-badpath`, subprocess PATH prefixed with System32.
- SELF-FIX: B1 launch uses a process-local PATH prefix
  `C:/Users/artsafro/.hermes/tools/git-2.53.0+3-win32-x64/usr/bin` before invoking
  the unchanged runner. No global setting, project test, assertion, marker, merge
  command or policy is modified. This is an environment repair, not a measured
  speed-up. B0 remains invalid; B1 becomes the baseline only if all frozen checks pass.
- The exact launch request, executable version/path preflight and WMI result are
  preserved in this worktree's ignored `tmp/baseline-002-launch*` files. B1 uses
  exclusive `baseline-002.*` evidence names and the same drained-slot guard.
- First B1 launcher PID `1127800` exited before creating a runner claim or starting
  pytest: PowerShell `Get-Command` returned multiple PATH matches, and the preflight
  correctly refused the array. Repaired discovery with `Select-Object -First 1`;
  retain the first WMI result, relaunch with console output redirected for diagnosis.
  This is a launcher repair, not a second measured run or discarded timing.

## Frozen observer and resume instructions

Audit snapshots: `autoresearch-suite-wall-harness/*.py.txt` (raw bytes preserved by
local `.gitattributes`). Executable copies live only in this worktree's ignored
`tmp/wall_harness/`; copy each snapshot there, dropping `.txt`, to reproduce.
This extends #1227's controller-only recording approach for the **existing xdist
merge gate**; its serial CPU observer cannot itself record the four-worker run.
No autonomous controller, automatic commit/revert, or merge loop is initialized.

- RED before implementation: `uv run python tmp/wall_harness/probe_observer.py`,
  exit 1, two `ModuleNotFoundError` errors. The regression snapshot and contract
  were committed first as `48b4fb55`.
- Harness check: `uv run python -m unittest discover -s tmp/wall_harness -p 'probe_*.py' -v`:
  6 tests passed; includes real generated n=2 pytest, nested fresh-process pytest,
  stale-output/alias refusal, malformed records, dead/live/partial slot files,
  process-query failure, and untracked source mutation.
- First implementation check exposed an invalid synthetic witness: two workers
  with identical selection are required, not an error. Corrected the witness to
  unequal selections; no observer rule or project assertion was relaxed.
- The runner waits for no live suite holders or merge chain/batch, plus <=10%
  whole-host CPU over a 20-second preflight sample. It records this sample and wait
  separately from command wall time. During the command it samples live holders
  every five seconds and checks source stability; sampled contamination fails closed.
  This is an observer, not a machine-wide scheduler lock: the orchestrator must
  reserve the drained window so another caller cannot start a merge concurrently.
- Launch **one** `measure.py baseline-001` detached from the worktree's own venv,
  via Win32_Process.Create. It exclusively creates `baseline-001.claim.json` and
  `baseline-001.runner.log`, waits for idle, enters suite_slot, then writes
  `baseline-001.json` (including `valid`, versions, SHA, wall, hashes and counts).
  The command never modifies project files. Process IDs are recorded in the claim,
  launch receipt, inside claim and card comment; do not edit this tracked log while
  measurement is running (source-drift checks intentionally reject that).
- Resume only when `C:/x/autoresearch-suite-wall/baseline-001.json` exists and the
  claimed process has exited. Read `valid` before any metric claim. A failed or
  contaminated run remains evidence, not an accepted baseline; use a new run name
  after diagnosing it. A launch error remains in the runner log/claim; never reuse
  or overwrite the name. Baseline-001 is a **pending** run, not a passing result.

