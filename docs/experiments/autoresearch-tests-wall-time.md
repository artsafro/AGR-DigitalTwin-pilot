# Issue 116: full test-suite wall time

## Final daytime verdict: INCONCLUSIVE — noisy-day run

Operator decision **2026-10-15 18:05**, task `t_6d268dff`: stop full-suite
measurements; **no valid A/B pairs**. This supersedes the 17:10 iteration window.
The task's daytime experiment is finalized as INCONCLUSIVE, not a performance
acceptance or rejection. Machine contention/stale controls invalidate all historical
timing comparisons. No median, speedup, confidence or token/cost total is available.
No issue closure or label change was performed or is claimed.

Continuation branch: `experiment/autoresearch-tests-wall-time`, inspected HEAD
`5ff8015`. Production, configuration and tests are unchanged. The inherited report
recorded `origin/main` at `2e61c73`; that is not a newly measured baseline.

The requested detached baseline worktree `C:/x/t_6d268dff-baseline` is outside this
worktree. The higher-priority harness forbids accessing or creating it. No external
baseline was inspected, created or modified. This blocks the paired experiment, not
merely its reporting. An in-worktree substitute would change the operator's protocol
and was not silently used. Harness permission for the baseline or operator approval of
an in-worktree alternative is required.

### Candidate preservation audit

`git status --short`, unstaged/staged diffs, branch history, reflog and
`git log --all` were inspected. The only working-tree change on entry was this
untracked report; `src/dt_ai/spec/floors.py` matches HEAD and contains the original
all-pairs matching implementation. Its latest reachable file commit is `ca26b4f`,
not a task optimization. HEAD/reflog contain no task candidate commit. A read-only
scan of 83 unreachable commit subjects found no floors/batching/autoresearch/task-116
candidate; this is not proof that no unidentified Git blob exists.

Available `.auto/` work contains `test_floor_matching_performance.py` and a historical
opening-index description in `log.jsonl`, but no recoverable floors candidate source
or patch. `candidate-mesh.py` and `original-mesh.py` concern section batching in
`src/dt_ai/spec/mesh.py`, not `floors.py`; they were not substituted. No candidate
was reconstructed or invented during finalization. Retaining a committed floors
candidate cannot be verified from the available identified work. Commits are
forbidden in this Pi harness; the driver must commit the report and, if an exact
floors artifact is later recovered, preserve that candidate on this branch only,
**not merged**.

## Paired protocol retained for the night handoff (not run today)

Primary metric: full command wall seconds, lower is better. Execute sequential A/B
pairs, minimum three pairs, alternating AB/BA (ABBA repeating), baseline A and candidate B.
Both use exactly:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_6d268dff-ar -m "not blender and not dcc"
```

Keep only when candidate median is at least 3% faster than same-session baseline median,
all guards pass, and a confirming rerun also meets the 3% requirement (confidence >=2
when available). Record every raw command wall time. **New raw A/B times: none; pairs:
0/3.** Old numbers below are historical evidence only, not acceptance references.

Guards remain failed=0, passed>=2321, skipped<=9, deselected<=12; no deletion/renaming,
weakened assertions, new skips/marks/xfails, or changed production output bytes. Scope:
conftests, fixture caching/scope, pytest options, equivalent setup and output-identical
pure performance changes. No new dependencies, uv.lock, CI, hooks, data, DCC,
`src/twinqa/geometry/checks.py`, or `src/twinqa/evals` changes.

The inherited `.auto/prompt.md` and `.auto/log.jsonl` preserve the earlier 17:10
override, blocker and verification records. They are ignored by Git and were not
updated during finalization; this tracked-path report carries the superseding 18:05
decision. `log_experiment` automatically commits/reverts, forbidden by the harness;
no auto-commit/revert tool was invoked.

## Historical `.auto/log.jsonl` ledger and operator-referenced timeout

Commit identifies source base, not a committed candidate. Sentinel zero is not a timing.

| Record | Commit | Seconds | Passed / skipped / deselected | Status | Description |
| --- | --- | ---: | --- | --- | --- |
| 1 | 5ff8015 | 298.86 | 2321 / 9 / 12 | historical baseline | Unchanged suite with diagnostic `--durations=30`; pytest duration, not clean command-wall reference; cold venv excluded. |
| 2 | 5ff8015 | 0 sentinel | not run | crash | Tool rejected direct command because measure.sh required; no tests ran. |
| 3 | 5ff8015 | 275.60 | 2323 / 9 / 12 | historical discard | Batch section interpolation/rounding and Shapely construction; pytest 274.10s; original comparison against supplied 247–265s is now invalid. |
| 4 | 5ff8015 | 295.80 | 2331 / 9 / 12 | historical discard | Finite-float opening x-index; pytest 294.17s; RED 1 failed/9 passed, GREEN affected 29 passed; original timing comparison now invalid. Inventory 2330 original +10 probes, 89 hashes, 12 output hashes reported passing. |
| override | — | — | — | operator_override | Fresh sequential pairs, >=3% median gain and confirmation, 60-minute window; unchanged guards; old timing comparisons invalid. |
| blocked | 5ff8015 | — | not run | blocked | External baseline prohibited; candidate identity ambiguous; no raw paired times. References discarded run 4 as the floors.py artifact, not as an accepted identity. |
| RED verification | 5ff8015 | 0.49 pytest | 1 passed, 1 failed | red | Inherited section probe expected 1 round call, observed 128; production unchanged. |
| full verification | 5ff8015 | no final duration | incomplete | timeout | Required correctness command stopped at the 400s timeout, not a passing benchmark. |
| guard verification | 5ff8015 | — | — | pass | Original inventory 2330/2330, original hashes 89/89, generated production hashes 12/12; zero candidate test additions installed. |
| Operator-referenced baseline timeout | not independently identified | >600s, incomplete | unknown | invalid / timeout | Baseline stopped at 84%, as referenced in the finalization instruction/comments; no local raw log or final summary recovered. This is a lower bound, not a completed timing or A/B control. |

All timings above are historical and **invalid for acceptance/comparison**. The
previously supplied 247–265s baseline range was also invalidated; it is not a new
measurement. Do not compute paired statistics from these records.

## Inherited RED, GREEN and invariant evidence (not rerun at finalization)

Previously recorded RED command (unchanged production):

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_6d268dff .auto/test_section_batching.py
```

Final line: **1 failed, 1 passed in 0.49s**. Expected operation-count failure: 128
`np.round` calls instead of 1; output equality passed. This is a mechanism probe for
section batching, not a discovered functional regression. No new regression was invented,
installed or left failing in `tests/`. No current GREEN claim: no candidate was applied.

The inherited output probe uses seed 116, 250 random triangles plus exhaustive vertex
heights {-1,0,1}, degenerate and reversed copies (331 triangles), seven planes, two input
representations, independent scalar ordered-WKB oracle, mutation and empty-input checks.

The inherited verifier expected ten now-absent discarded regression nodes. The earlier audit
recorded executing that verifier with **only its additions set changed to empty in memory**, matching
the actual unchanged tree. Original snapshot and verifier file were not rewritten. It still
requires exact original inventory, original file hashes and production output hashes.

| Invariant | Probe | Previously recorded result |
| --- | --- | --- |
| No removed/renamed original tests | Exact selected original node inventory | 2330/2330 |
| No weakened original assertions/functions/marks | Original Python test file SHA-256 | 89/89 |
| Production serialized identity | 3 synthetic prism widths x 4 opening depths; spec JSON plus report JSON versus saved hashes | 12/12 |
| Ordered section geometry and input representation | Generated/exhaustive triangles, seven planes, two forms, scalar WKB oracle | 14/14 |
| Inputs unchanged; empty input | Byte snapshots; empty input | 7/7; 1/1 |
| No production/configuration/test edits | Git status/diff inspection | unchanged |
| Failed=0, passes>=2321, skips<=9, deselections<=12 | Required full-suite run | unverified: timed out |
| >=3% gain and confirming gain | Fresh paired benchmark and confirmation | not run: 0/3 pairs |

Finite probes are not universal equivalence proofs. For the present delivered state,
production code and dependencies are unchanged. No finite probe is used to accept an
unmeasured optimization.

## Required correctness verification (not benchmark measurements)

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_6d268dff
```

The inherited verification **timed out after 400 seconds; no final pytest summary exists**.
Its last displayed progress was 92%, followed by 35 dots. Do not infer final pass/failure counts from progress. This
uses the harness basetemp, not the primary benchmark basetemp, and is not a baseline.

During this report finalization, the higher-priority harness required the same
correctness command once more, with a 400s timeout. It also timed out: last labelled
progress 80%, followed by 60 dots. Final tool line: `Command timed out after 400 seconds`.
There is no final pytest summary, no complete pass/fail count and no correctness pass.
This mandatory check was not an A/B measurement; no additional experiment measurements
were attempted, and valid pairs remain **0**.

Pi sandbox constraints: work only inside the current worktree, no external baseline
access/creation, and the mandated test invocation limited to 400s. The >600s baseline
observation belongs to the operator-referenced prior run, not this sandbox invocation.
Neither timeout establishes a completed suite duration or diagnoses the noise source.

The inherited report also recorded a previous unchanged verification:
`2321 passed, 9 skipped, 12 deselected, 1 warning in 301.21s (0:05:01)`.
That is historical correctness evidence only, not this continuation's final result or an
acceptance baseline. Warning: intentional duplicate ZIP-member fixture.

## Noise, forbidden/deferred ideas and remaining work

Contention is the operator's reason for invalidating earlier comparisons. The current
400s timeout further prevents assuming old machine conditions; its cause was not diagnosed.
No significance/confidence or speedup is claimed. Python 3.14.7/Windows environment and
uv-managed dependencies are inherited setup; no new dependency or DCC use.

| Idea | Expected gain/evidence | Decision |
| --- | --- | --- |
| Section batching | 128-to-1 rounding calls in mechanism probe; valid paired gain unknown | Candidate identity must be clarified before remeasurement |
| Floors opening matching index | Sparse matching mechanism; valid full-suite paired gain unknown | Historical discard comparison invalid; remains unmeasured under override |
| Delete tests, weaken assertions, add skips/exclusions | Apparent gain equals omitted work, not measured | Forbidden |
| New parallelism dependency, lockfile, CI, hooks | Resource-dependent gain not measured | Outside scope |
| Change precision/order/serialization | No output-identical gain measured | Forbidden unless byte identity maintained |
| Cache/broaden mutable fixture scope | Setup gain unknown; isolation risk | Deferred; requires independent isolation probes |

## Night rerun handoff — 03:00

Resume at **03:00 (next night after the 2026-10-15 decision)** from
`experiment/autoresearch-tests-wall-time`, not from a merge into main. This is a handoff,
not a claim that a scheduled job was created or that a rerun has happened.

1. Read this report and verify branch HEAD/status before changing anything. Recover and
   identify the exact floors candidate if available; do not substitute mesh batching or
   recreate a candidate from timings. Preserve any recovered candidate in a branch-only
   driver commit, clearly marked unaccepted.
2. Resolve the external-baseline sandbox restriction and 400s execution limit before
   measurement. Do not bypass either; arrange an operator-authorized compatible runner.
3. Under quiet conditions, use fresh same-session sequential alternating A/B controls
   (minimum three valid pairs), exact matching commands and raw logs. Historical numbers
   and either timeout are not controls. Apply the original guards and >=3% median-gain
   plus confirming-rerun requirements only to new valid evidence.
4. Record actual raw times/counts and candidate/baseline revisions; if measurements remain
   incomplete, keep INCONCLUSIVE. No token totals are available. Issue status/labels and
   merge remain separate operator actions.

Finalization changed only this report. Candidate preservation is unresolved because no
exact floors implementation/patch was recovered; committing is delegated to the driver.
The daytime outcome remains **INCONCLUSIVE**, not issue completion.
