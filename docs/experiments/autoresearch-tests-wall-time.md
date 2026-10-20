# Issue 116: full test-suite wall time

## Round 2 final driver attempt — 2026-10-20 — INCONCLUSIVE

This section supersedes the continuation and historical verdicts below. The
20:46 orchestrator instruction explicitly permits an INCONCLUSIVE finish if the
board does not drain within the runtime cap. **No optimization is delivered, no
speedup is demonstrated, and no slot/worker setting is recommended.**

### Protocol and revision

- Driver: Hermes `dt-worker-codex`, replacing Pi by the 13:38 instruction; this
  attempt did not run Pi or a Codex autoresearch optimization controller.
- Fetched `origin`; fast-forwarded this task branch from `3c7c54a` to pinned
  `8d5c8987dbd46343176ca5af9d1791c864a86217` before measurements. HEAD remained
  pinned throughout. PR #148 is merged but reports INCONCLUSIVE, not acceptance.
- `uv sync`: resolved 23 packages, audited 22; existing xdist is installed.
  No dependency, lockfile, source, test, fixture or pytest configuration changed.
- Approved fixed matrix: three single-process baselines, then `-n 2/4/8
  --dist loadfile`, then best-setting confirmation. All full-suite attempts use
  `python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card t_806659ab`.
  The 20:46 exception permits repetition/xdist only for this benchmark, with no
  other holder when starting xdist and a maximum of eight workers.
- Timing would measure the pytest command **inside** the acquired slot separately
  from wrapper/queue wall time, recording holder snapshots every ten seconds.
  Intended pytest arguments were `-q -p no:cacheprovider
  --basetemp=C:/x/t_806659ab-ar -m "not blender and not dcc" --durations=20`.
  The child environment removes `MSYS_NO_PATHCONV` and `MSYS2_ARG_CONV_EXCL`.
  No pytest child was actually started.

### Run ledger (this driver attempt)

| Run | Commit | Suite seconds | Passed / skipped / deselected / failed | Status | Description |
| --- | --- | --- | --- | --- | --- |
| B1 | `8d5c898` | unavailable | unavailable | queue-only, cancelled | First baseline waited at least 4680 s; never acquired a slot. |
| B2, B3 | `8d5c898` | unavailable | unavailable | not launched | B1 never completed. |
| N2, N4, N8 | `8d5c898` | unavailable | unavailable | not launched | No complete baseline; board did not drain. |
| Confirmation | `8d5c898` | unavailable | unavailable | not launched | No eligible candidate. |

The background process was `proc_3c3968b91064` (driver PID 831916).
`process_manage` reported 4709 s uptime before termination; the last runner line
was `suite_slot: waiting for a free slot (2 busy, 4680 s, queue position 4)`.
Queue positions ranged from 2 to 4 in the observed runner output. This is
**queue delay, not a 4680-second suite result**. The process was stopped to reserve
handoff time inside the card's 90-minute execution budget. Readback confirmed
`driver_alive False`, no own queue tickets, and no holder belonging to this card.
No CLI process was launched and no shared lock was deleted.

Holder observations (not a complete concurrency trace):

| Observation | Live other holders | Other recorded state |
| --- | --- | --- |
| Before launch | `t_76200be5`, `t_cf746008` | configured slot count 2 |
| About 15 min queued | `t_76200be5`, `t_9907a0c1` | queue position 4 |
| About 38 min queued | `merge20261020k`, `t_fd239f23` | queue position 2 |
| 22:03 local and after stopping | `t_5be38fb0`, `merge20261020l`, `orch392` | live holder files 0, 1, 2 |

A slot-3 record for `t_76200be5`, PID 745464, was present but its PID was dead
on every inspected snapshot. It was left untouched. The third live holder in the
last snapshot is reported as observed, not silently folded into the configured
two-slot statement. No benchmark ran, so none can be classified as uncontended.
Windows `0xC0000142` errors are **not measured**, not zero, for every matrix row.

Completed baselines **0/3**; candidate executions **0**; confirmations **0**.
Baseline median, final median, >=10% median gain and exact count parity are all
**unavailable**. The report does not substitute older suites or collection counts.

### Verification and author boundary

- `git diff --check`: passed. Source/test/config inventory identity against pinned
  main is checked separately before publication; this PR changes only this report.
- `uv run dt evals --suite regression --output tmp/evals`: **0 passed / 0 failed /
  10 not measured**, exit 2. Missing Claude transcript and PR snapshot evidence;
  local receipt: `tmp/evals/report.json`. No fabricated transcript was supplied.
- RED/GREEN regression: n/a for this documentation-only result; no performance
  change was selected or implemented. This is not a claim that the optimization
  acceptance tests passed. No mandatory numerical/fail-closed guarantee was added.
- Hostile review: empty/missing timing evidence, incomplete summaries and queue
  durations remain unavailable; historical results are not reused after HEAD
  changes; no output aliases a production input; no production writer was added.
- CI: not run (billing lock).

### Tool verdict, cost and deferred ideas

The prior Pi attempt recorded 3 bursts, 39 turns, 58 tool calls and 2741 s;
usage reported on this card was input 155866, output 11157, cacheRead 596864,
total 763887 tokens. Those are **prior-attempt** figures, not this driver's usage.
This driver's token total is unavailable. Pi's 400 s command cap prevented earlier
complete measurements; this driver removed that cap by using a background process,
but shared queue starvation still prevented the first baseline. Autonomous
keep/revert quality and noise-retention frequency therefore remain unevaluated:
no candidate was kept, and that is not evidence of a successful noise filter.

| Deferred idea | Expected gain | Disposition |
| --- | --- | --- |
| Existing xdist 2/4/8, loadfile | unknown; no candidate measurement | authorized but not launched |
| Cache slow immutable fixture data | unknown; no durations obtained | needs isolation/parity probes first |
| New dependency, CI/hooks/lockfile changes | unknown | not permitted; none added |
| Omit tests or weaken checks | apparent gain is omitted work | forbidden, not attempted |

Next action is operational, not a guessed performance recommendation: arrange a
truly drained benchmark window, pin its then-current main, and execute the matrix.
This PR publishes the failed measurement attempt only; it does not satisfy the
original performance acceptance or authorize configuration changes.

---

## Continuation: t_806659ab — INCONCLUSIVE, shared slots busy

This section supersedes all earlier status/verdict text below. Acceptance remains
three completed origin/main baselines, >=10% candidate median gain, exact count
parity and a confirming rerun. **Acceptance is not demonstrated; no code candidate
was applied or retained.**

### Baseline identity and current-main check

On continuation entry, only this report was modified. Both HEAD and origin/main
were `3c7c54a1723aed2b30c84a0064c780544c8138f5`; production/tests/configuration
were unchanged. The existing report contains no accepted >=10% comparison.
During the two slot waits, origin/main moved to
`eed5074a3fad597fce5608ea832dccbd0edaf527`, while HEAD stayed pinned. This agent
performed no fetch, checkout, branch change, commit or ref update. The new ref adds
`tests/test_cli_dispatch.py` and extends `tests/test_ground_recipes.py` relative to
HEAD. Therefore no measurement of the *new* main or parity against it is claimed.
A new baseline decision is required before further comparison.

### Every continuation run and recovered artifact

Native Windows `python` successfully invoked the driver-specified runner. It is
**not missing**. Every continuation full-suite attempt used this prefix:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card t_806659ab --
```

| Run | Command after runner prefix | Result / final line | Valid baseline? |
| --- | --- | --- | --- |
| Recovered B1 | exact invocation/timing not recoverable from artifact | `.auto/baseline-1.log`: slot acquired, progress through 46%, no summary | no |
| Recovered B2 | exact invocation/timing not recoverable from artifact | `.auto/baseline-2.log`: slot acquired, progress through 45%, no summary | no |
| Recovered B3 | exact invocation/timing not recoverable from artifact | `.auto/baseline-3.log`: slot acquired, progress through 29%, no summary | no |
| B4 | benchmark command below | timeout after 400s, entirely waiting; last runner line `suite_slot: waiting for a free slot (2 busy, 360 s)` | no |
| H2 | mandatory correctness command below | timeout after 400s, entirely waiting; last runner line `suite_slot: waiting for a free slot (2 busy, 360 s)` | no |
| C1 | benchmark selection with `--collect-only` (not a full-suite execution) | `6808/6868 tests collected (60 deselected) in 1.72s` | no |

Benchmark command:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_806659ab-ar -m "not blender and not dcc"
```

Mandatory correctness command (H2, bash timeout 400 seconds):

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_806659ab
```

Final tool line for both B4 and H2: **`Command timed out after 400 seconds`**.
Pytest never started in either. Queue wait is not suite wall time; passed, skipped,
deselected and failed counts are unavailable, not zero. Completed baseline **0/3**;
candidate runs **0**; final confirmations **0**; median/gain **unavailable**.
No slot locks were removed and no uncoordinated full suite was substituted.

### Invariant -> probe -> result

| Invariant | Probe | Result |
| --- | --- | --- |
| No removed tests, changed assertions/marks, source/config/lock edits relative to pinned HEAD | Enumerate every tracked `src`, `tests`, `pyproject.toml`, `uv.lock` path; compare Git content hashes against `git ls-tree -r HEAD`, assert equal inventories | **288/288** |
| >=10% confirmed gain and exact suite parity | Require completed slotted baselines/candidate/confirmation before keeping | **0 candidates kept**; acceptance blocked |
| Byte-identical production outputs | No production change; runtime equivalence probe not performed | not measured |

A first per-file identity probe timed out after 30s without a verdict; a batched
hash probe then completed 288/288. RED affected tests **not run**; GREEN affected
tests **not run**. No regression test or generated behavior probe was invented for
an unselected optimization. These requirements remain undone, not waived.

### Tool, tokens, disallowed ideas and next action

`PI_EXTENSIONS=npm:pi-autoresearch@1.9.0` is present; `.auto/` is locally ignored.
A config already exists, so it was not initialized twice. Autoresearch tools are
exposed, correcting the earlier tool-availability claim. However `log_experiment`
automatically commits/reverts, explicitly forbidden by this harness. No such tool
was invoked; results and ASI were appended manually to `.auto/log.jsonl`. Verdict:
**end-to-end autonomous optimization not evaluated**; shared-slot waiting prevented
measurement, and the automatic Git lifecycle is incompatible with this run's policy.
Token/cost totals are unavailable, not zero. No >=10% speedup is claimed.

Disallowed ideas and expected gains are listed below; none was attempted. Removing
work would gain time proportional to removed work but violates parity. Dependencies,
CI/hooks/data/DCC and excluded production modules remain off limits; gain unknown.
Promising deferred ideas are also recorded in `.auto/ideas.md`; no numerical gain
estimate is supported by this continuation.

Next: arrange shared-slot availability and authorize the baseline ref after the
observed origin/main movement. Then complete 3 clean baselines, profile, prove RED,
apply one in-scope candidate with generated equivalence probes, measure >=10% median
gain and confirm exact parity. Only this report is a tracked change.

---

## Superseded initial attempt: t_806659ab — no optimization retained

This section supersedes historical acceptance thresholds below: the current request
requires **>=10% median gain**, three baseline measurements and a confirming rerun
with exact passed/skipped/deselected/failed parity. Historical 3% criteria do not apply.

### Initial origin/main acceptance check

`HEAD` and the locally available `origin/main` both resolve to
`3c7c54a1723aed2b30c84a0064c780544c8138f5`; the initial tracked diff is empty.
No fetch was performed, so remote freshness is not asserted. The inherited report
contains no valid accepted baseline/candidate comparison. Therefore current main
**does not have demonstrated acceptance**; that is not proof it cannot be faster.

`PI_EXTENSIONS=npm:pi-autoresearch@1.9.0` is already present in this Pi session.
`.auto/prompt.md` and `.auto/log.jsonl` record the local program and outcome;
`.auto/` is already locally ignored by the repository's `info/exclude` (line 7).
The shared exclude file is outside this worktree and was not modified.

### Blocking prerequisites and tool verdict

The initial attempt incorrectly inferred runner unavailability from worktree/PATH
searches. The driver verified the external runner path; the continuation above
successfully invoked it. That earlier inference is invalid. No replacement local
lock was invented.

**Earlier tool verdict (corrected above): not evaluated for autonomous optimization.**
The requested extension selector and autoresearch tools are present. No extension
installation, nested agent, auto-commit/revert, or undocumented extension API was used.
Token consumption and cost are **unavailable**, not zero; no token total is claimed.

### Every new full-suite run

| Run | Source | Command | Result | Use |
| --- | --- | --- | --- | --- |
| H1 | unchanged `3c7c54a` | mandatory harness command below | timeout at 400s; last labelled progress 40%, then 15 dots; at least one `F` displayed; no final pytest counts | incomplete correctness verification, not a baseline |

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_806659ab
```

Final tool line: **`Command timed out after 400 seconds`**. The run created a local
`.venv` with CPython 3.14.7 and installed the existing locked environment (22 packages);
no dependency declaration or lockfile changed. The failing node was not identified
by the truncated quiet progress, so no cause is asserted or unrelated fix attempted.
This run was required by the higher-priority harness, directly without suite_slot.py;
that is an explicit protocol exception, not a valid slotted measurement. It also uses
the harness marker defaults and basetemp, not the benchmark's exact command.

Requested benchmark command, **not run**:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_806659ab-ar -m "not blender and not dcc"
```

Baseline: **0/3 completed**. Candidates: **0**. Final confirmations: **0**.
There is no median or gain. RED/GREEN affected-test runs: **not performed**;
there is no selected fix or new regression test. H1 is neither a valid RED regression
nor GREEN. In particular, failed=0 has not been established.

### Invariants and probes

A byte-identity probe enumerated `git ls-files src tests pyproject.toml uv.lock`,
compared each current `git hash-object --stdin-paths` value against `git ls-files -s`,
and asserted equal inventory lengths and no mismatches: **288/288**. This can be
repeated with `git diff --exit-code origin/main -- src tests pyproject.toml uv.lock`
and the same file enumeration (the index equals origin/main for these paths).

| Invariant | Probe | Result |
| --- | --- | --- |
| No source/test/config/lock modification, removed tests, weakened assertions or new marks | Complete tracked-file content identity against unchanged base index | 288/288 |
| Production output byte equivalence after optimization | n/a: no candidate or production changes; no runtime output comparison performed | not measured |
| Fail closed without a shared suite slot or valid timing evidence | No experimental launch or kept candidate after prerequisite discovery | 0 experiments; 0 kept |
| Exact suite count parity and >=10% confirmed gain | Slotted baseline/candidate/confirmation | blocked; 0/3 baseline |

No new behavioral guarantee is introduced, so no generated regression probe was
invented for unchanged production. Required candidate RED/GREEN and generated
output-equivalence probes remain **undone**, not waived.

### Disallowed/deferred ideas and expected gain

| Idea | Expected gain | Disposition |
| --- | --- | --- |
| Remove/rename tests, weaken assertions, add skips/marks/xfails | Proportional to omitted work; not measured | forbidden; invalid parity |
| Add dependencies or change lockfile, CI, hooks, data or DCC | unknown; no trustworthy estimate | forbidden by scope |
| Optimize `src/twinqa/geometry/checks.py` or `src/twinqa/evals` | unknown; not profiled | forbidden by scope |
| Parallel execution using existing xdist | resource/serialization dependent; unknown | not attempted without shared slot and parity/output probes |
| Cache or broaden mutable fixtures; section batching; opening index | unknown full-suite gain; historical times invalid | deferred, no candidate retained |
| Substitute local lock for shared suite_slot.py | no legitimate performance gain | rejected: cannot coordinate other workers |

Superseded next action: obtain a free shared slot;
then measure three clean baseline runs, investigate any baseline failures, select
an in-scope candidate, prove RED, add generated equivalence probes, and measure
candidate plus confirmation. Do not use historical timings or the incomplete H1
as a baseline. Only this report is a tracked change; no commit/push was performed.

---

## Historical record (not current acceptance evidence)

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
