# Autoresearch: merge-gate wall time (#1615)

Status: contract frozen; baseline pending. No speed-up or acceptance claimed.

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
| B0 | Unmodified `c62ceddd`; canonical n=4, idle slot | pending | pending | baseline pending |

No optimization has been implemented, retained or dropped yet. Baseline and final
comparison table and empty parity diff will be added only after real execution.
