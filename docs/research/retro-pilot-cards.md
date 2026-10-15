# Retro: cards solved on the Hermes board `agr-pilot` (2026-10-15)

Research card `t_93f33f81`. Status: notes, not decisions. Every proposal is a candidate for the user.

**Inputs (read by me, read-only):** the board database
`~/.hermes/kanban/boards/agr-pilot/kanban.db` (13 cards, 30 runs, all comments and events; the
`hermes kanban` CLI is refused inside a worker, so I read SQLite in `mode=ro`), PRs #1-#8 of
`artsafro/AGR-DigitalTwin-pilot` with their bodies and review comments (`gh pr view N --comments`),
the SOUL files in `C:\Users\artsafro\hermes_kanban\profiles\*`, `profiles/models.yaml`,
`scripts/issues_to_cards.py`, the `hermes_kanban` git log, and `docs/agents/{WORKFLOW,REVIEW_CHECKLIST,KANBAN}.md`
of this repository. Marks: **[verified]** = I ran a command or read the code/data;
**[source]** = an outside source claims it (URL given).

## Summary

1. 8 cards reached `done` (PRs #1-#8, all open, none merged); 6/8 passed review in round 1. Two
   cards needed extra rounds: #109 (PR #2, 3 rounds, 4 P1) and #21 (PR #7, 2 rounds, 1 P1).
   All 5 P1 were found the same way: the reviewer wrote a **synthetic counterexample against an
   invariant stated in the issue**, which the author had not probed. One was a requirement moved to
   "Out of scope".
2. All 4 non-done cards stopped on **tooling, not on the task**: agy UTF-8 crash (2 cards, 4 runs, 0
   edits), Cursor hooks under bash (fixed by `cursor-run.ps1`), a parent link created after the child
   (fixed in `issues_to_cards.py`). One legitimate `needs_input` block (#101 → D093) worked as designed.
3. The worker instructions **contradict the card footer** on three points (`Closes` vs `Refs`,
   `gh issue create` vs "no issues in source", reviewer "P2/P3 → issues"); the footer won every time.
   The "Agent trace" block that SOUL and footer require **does not exist** in `docs/agents/WORKFLOW.md`
   (#124 open); 8 PRs improvised 8 different traces.
4. The full suite is **not green on this machine**: 4 `test_kpp1_export_safety` failures caused by the
   inherited `MSYS_NO_PATHCONV=1`/`MSYS2_ARG_CONV_EXCL=*`. 7 of 8 PRs re-diagnosed it; Codex
   workers reported 0 failed (env workaround), Claude workers 4 failed — the numbers are not comparable.
5. Rules added mid-night (metadata contract 02:00, milestone comments 02:10) were followed 100 % by
   every later run; the first batch (01:49-01:52) had neither. Written rules work; the gaps are
   where no rule exists or two rules disagree.
6. Ten small proposals below (SOULs, footer, `docs/agents/`, tests), each with its evidence.

## Findings

### F1. Every extra review round = an issue invariant the author did not attack [verified]

| Card / PR | Round | P1 (reviewer quote, shortened) | Kind |
|---|---|---|---|
| `t_b273026a` / PR #2 (#109) | 1 | "one live row suppresses unrelated historical events in the same session … historical agent rows **0, expected 1**" | idempotency/dedup edge |
| | 1 | "distinct events collapse after timestamp truncation … **1 new / 1 already logged, expected 2 new**" | identity precision |
| | 1 | "worktrees outside the main-checkout slug are silently omitted … listing external worktrees as out of scope does not satisfy that requirement" | **scope reduction disguised as "Out of scope"** |
| | 2 | "live-overlap reconciliation bypasses exact-event deduplication … 2 counts instead of 1" | dedup edge, introduced by the round-1 fix |
| `t_403fc01e` / PR #7 (#21) | 1 | "`openings.py:198-200` skips a rejected pair if **either** end is paired … **0 unresolved breaks** … violates #21's explicit unresolved-diagnostic requirement" | silent skip vs a stated guarantee |

The reviewer's round-1-clean verdicts on the other 6 PRs carry the same instrument: "2000/2000 synthetic
graphs match exhaustive oracle" (PR #3), "64/64 boundary/winding probes" (PR #4), "1000/1000 synthetic
oracle cases" (PR #5), "49/49 synthetic build probes" (PR #6), "36/36 synthetic probes" (PR #8). The
authors of the clean PRs had already run brute-force/oracle comparisons themselves (e.g. #101 comment:
"Matches brute force on 300 random sets"; #23 9 regressions). The authors of PR #2 and #7 listed only
the issue's examples as regressions. Cost of the missed probes: 3 extra worker runs (384 + 476 + 235 s)
and 3 reviewer runs (~120-180 s each), plus wall time 01:52 → 02:19 for #109.

The round-2 P1 of #109 was created by the round-1 fix: the worker added three regressions, one per
finding, but no property over the combined behaviour (the reviewer's round-2 probe combined
"duplicate + live overlap").

External context: property-based testing finds counterexamples by generating inputs against a stated
property; Anthropic reports an agent writing such properties found real bugs in widely used Python
packages [source: https://www.anthropic.com/research/property-based-testing,
https://arxiv.org/html/2510.09907v1]. The reviewer here is already doing exactly that by hand.

### F2. Instructions contradict each other; the footer silently wins [verified]

| Topic | `profiles/dt-worker/SOUL.md` | `issues_to_cards.py` FOOTER | What happened |
|---|---|---|---|
| PR closing line | line 11: "description ends with `Closes #<issue>`" | line 38: "ends with `Refs {source}#{number}`" | 8/8 PRs end with `Refs …`, 0 with `Closes` (`gh pr view N --json body`) |
| Side findings | line 13: "go to a new GitHub issue (`gh issue create`)" | line 42: "creating issues in {source}" forbidden, "go into the PR description, section Out of scope" | 8/8 PRs have "Out of scope"; and see F1: a real requirement was parked there |
| Reviewer P2/P3 | `dt-reviewer/SOUL.md` line 15: "P2 and P3 become GitHub issues" | (no rule for the reviewer) | no P2/P3 yet; the first one will hit the conflict |
| Test command | line 12: `uv run pytest -q` | line 43: `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t-{n}` | footer used; SOUL also says "they override the defaults" — fine, but redundant |

The SOULs of `dt-worker-agy` and `dt-worker-cursor` already say "ends with the line the card names",
which is the right fix; `dt-worker/SOUL.md` was not updated. There is no `dt-worker-codex` SOUL file in
`profiles/` (`models.yaml`: "same worker SOUL as dt-worker").

### F3. The "Agent trace" block is required but undefined [verified]

`grep -i trace docs/agents/WORKFLOW.md` → no match. Issue
artsafro/AGR-DigitalTwin#124 "Observability: Agent trace block in the handoff and the PR body" is OPEN.
PR #1: "`docs/agents/WORKFLOW.md` has no "Agent trace" template yet (#124 is pending)"; PR #3 and PR #8
say the same. The 8 traces carry different fields (tool counts in #1; skills + retries in #3; an
incident report in #5; TDD order in #8), so they cannot be aggregated.

### F4. The full suite is red by environment, and each worker rediscovers it [verified]

I ran in this worktree: `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t-retro tests/test_kpp1_export_safety.py`
→ **4 failed, 23 passed, 1 skipped**; the same with `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL`
→ **27 passed, 1 skipped**. The Hermes terminal exports `MSYS_NO_PATHCONV=1`, `MSYS2_ARG_CONV_EXCL=*`
(seen in my env), and the test's bash subprocess then turns `C:/x/...` into `C:\c\x\...` (PR #1 summary).
MSYS2 documents `MSYS2_ARG_CONV_EXCL` as the switch that excludes arguments from path conversion
[source: https://www.msys2.org/docs/filesystem-paths/]; `MSYS_NO_PATHCONV` is the Git-for-Windows
equivalent [source: https://stackoverflow.com/questions/71341356/how-can-i-suppress-path-expansion-in-the-git-for-windows-bash].

Reports diverge: Claude workers "1337 passed, 4 skipped, 4 failed" (#21), "1341 passed, 5 failed" (#101);
Codex workers "1355 passed, 4 skipped" after `env -u …` (#102, #28). The reviewer runs only affected tests
(REVIEW_CHECKLIST §3) and says so: "Full-suite counts in the author handoff were not re-run" (PR #7 round 2).
So a **new** failure in an environment-sensitive test would hide inside "4 pre-existing". A second
environment-sensitive test: `tests/test_subagents.py` "fails only with uncommitted edits in the worktree
(Stop hook reads git status)" (`t_b273026a` run 13; counted in #101's "5 failed").

### F5. RED-before-fix is proven four different ways; one leaked across worktrees [verified]

Methods seen: tests-first commit (#21: `07b20eb` tests red, `d71ef1e` fix); old module loaded from
`git show <sha>:file` into the process (#102, #28, reviewer); old hook copied to scratch (#109 reviewer);
`git stash` / `stash pop` (#101). PR #5 trace: "a `git stash` / `stash pop` while checking base failures
briefly applied another worktree's stash (the stash list is shared across worktrees)". I verified that
`git rev-parse --git-path refs/stash` in this worktree resolves to the common
`AGR-DigitalTwin/.git/refs/stash`. Other agent harnesses ban `git stash` in worktrees for exactly this
reason [source: https://github.com/stablyai/orca/issues/13695,
https://github.com/gsd-build/get-shit-done/commit/ddd490a5e8ddb40637f4d53a82ff0dbfbb7562d8].
`REVIEW_CHECKLIST.md` already documents `git worktree add --detach <dir>/prev <commit>` for reviewers, but
not for authors.

### F6. Tool-failure blocks loop through the board without new information [verified]

`t_c9980b81` (#103): run 23 agy crash → orchestrator comment "agy re-checked … works; the UTF-8 crash looks
one-off. Retry" → run 26 crash again (ASCII retry too) → `block_loop_detected` → `auto-decomposer`
"Specified — updated title, body and promoted to todo" → run 28: "Automatic re-specification provided
neither … No third agy call made." `t_6f811afa` (#22) hit the same crash in its first run. 4 agy runs,
0 edits. The worker behaved correctly (two-failure rule); the board did not: a re-spec of the **card text**
cannot fix a **tool** failure, and the card stayed on the broken profile. A read-only agy prompt succeeding
was taken as proof the write path works; the worker itself noted "read-only agy success did not establish
the implementation path works".

`t_e4bcca30` (#105): Cursor "reports success but nothing changed" pattern — caught only because the worker
checked; now in SOUL line 18 and solved by `scripts/cursor-run.ps1`. The block reason was precise and
actionable ("make cursor-agent run hooks under PowerShell … or turn the hooks off for Cursor") — good
model for transient blocks.

### F7. A missing parent link made a child run from the wrong base [verified]

`t_be60e4ed` (#24) comment: "Parent branch origin/fix/extractor-opening-kinked-wall does not exist …
card has no linked parent — working from main, PR base main." It was reclaimed manually
("created before its parent link (#22); must wait for #22"). The script is fixed (lines 138-142, link at
create), but the worker rule has no stop: a body naming a parent branch that does not exist on `origin`
should be a `dependency` block, not a silent switch to `main`.

### F8. Rules added during the night were followed at once [verified]

`hermes_kanban` git log: `23a70f3 02:00` hand-off metadata contract, `5fa0829 02:10` milestone comments.
Runs 1-4 (started 01:49-01:52) lack `branch/base/verified/open_items/next_steps` and have 0 card comments
(`t_3d8c2f68`, `t_7354c497`, `t_2d6cb157`); every review hand-off after 02:00 has all 8 metadata keys,
and the cards started after 02:10 have 5 comments each. Reviewer behaviour was uniform from the start:
verdict posted **and read back**, numbers, pre-fix replay, no branch edits, no merge (8/8).

### F9. Smaller observations [verified]

- CI never ran: "CI cannot start due to account billing lock" (PR #1, #3, #4, #5, #8 reviews); "GitHub
  build failed with no job steps" (PR #7). Every reviewer re-states it; the local suite is the only gate.
- Stacked PR #6 (base `fix/checker-weld-distance`) works as designed, but its merge now depends on PR #5;
  8 open PRs wait for the user's merge command with no merge-order note.
- Issue text vs data: #109 "issue's quoted counts (12/6) vs found 3/2" — the worker disclosed it in Out of
  scope and the reviewer accepted it. Fine, but it is a spec-accuracy item for the issue author.
- Language: Codex runs write summaries in Russian, Claude runs in English. D088 allows Russian to the
  user; the SOULs say "identifiers in English". Not a failure, just inconsistent hand-offs.

## How it applies to this repository

| Finding | Files |
|---|---|
| F1 adversarial probes | `docs/agents/REVIEW_CHECKLIST.md` (§2 Invention), `.agents/skills/` TDD/implement skill (+ `.claude/skills/` copy via `tools/sync_skills.py`), `C:\Users\artsafro\hermes_kanban\profiles\dt-worker*/SOUL.md` |
| F1 scope reduction | FOOTER in `C:\Users\artsafro\hermes_kanban\scripts\issues_to_cards.py` (line 42) |
| F2 contradictions | `profiles/dt-worker/SOUL.md` lines 11, 13; `profiles/dt-reviewer/SOUL.md` line 15; FOOTER lines 38, 42 |
| F3 Agent trace | `docs/agents/WORKFLOW.md` (new section), issue #124 |
| F4 env-red suite | `tests/test_kpp1_export_safety.py` (subprocess env), `tests/test_subagents.py`; FOOTER line 43 |
| F5 RED method | `docs/agents/WORKFLOW.md` §Git, `docs/agents/REVIEW_CHECKLIST.md` (move the throwaway-worktree recipe to a shared place) |
| F6 tool loops | `hermes_kanban` orchestration skill / `agr_refill.py`; `profiles/dt-worker-agy/SOUL.md` lines 31-34 |
| F7 parent branch | `profiles/dt-worker*/SOUL.md` "Parents" rule; FOOTER `PARENT_LINE` |

## Proposed next tasks

1. **SOUL + footer: one source of truth for PR/issue conventions.** Remove `Closes #<issue>` and
   `gh issue create` from `dt-worker/SOUL.md`, replace with "the closing line and where side findings go are
   named by the card" (as the agy/cursor SOULs already do); in `dt-reviewer/SOUL.md` say "P2/P3 go where the
   card says (pilot: a section 'Follow-ups' in the review comment)". Add a `dt-worker-codex` SOUL or a note
   that it reads `dt-worker/SOUL.md`. Evidence: F2. Value high (removes a guaranteed future conflict),
   effort ~15 min.

2. **Footer: "Out of scope" cannot hold an issue requirement.** Add to FOOTER line 42: "An acceptance
   point of the issue that you do not deliver is not Out of scope: deliver it or `kanban_block` with the
   reason." Evidence: PR #2 round 1, "listing external worktrees as out of scope does not satisfy that
   requirement". Value medium-high (one of 5 P1), effort 5 min.

3. **Author-side counterexample step before review.** Add one rule to the worker SOULs and the project
   implement/TDD skill: "For every guarantee the issue states (never dropped silently, counted once,
   ≤ weld_m …) write one generated/brute-force probe besides the issue's examples, and list
   `invariant → probe → N/N` in the PR". After a review round, the new regression must cover the
   combination of the fixed case with the previous fixes. Evidence: F1 (5/5 P1 found by reviewer probes;
   the clean PRs' authors already had oracle checks). Value high (would have saved 3 worker + 3 reviewer
   runs), effort ~30 min (text) .

4. **Fix the environment-red tests.** `tests/test_kpp1_export_safety.py`: build the bash subprocess env
   without `MSYS_NO_PATHCONV` / `MSYS2_ARG_CONV_EXCL` (or pass POSIX paths); `tests/test_subagents.py`:
   isolate from the worktree's `git status` (temp repo). Until merged, the footer's test line uses
   `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest …` so every worker reports comparable,
   green numbers. Evidence: F4, my run 4 failed → 27 passed. Value high (a real regression could hide in
   "4 pre-existing"), effort ~1 h (code issue in the source repo, `harness` label).

5. **Agent trace template (= #124).** Define the block in `docs/agents/WORKFLOW.md` with fixed fields:
   card id, profile, model (and delegated tool + model for agy/Cursor), commit range, RED evidence
   (method + numbers), full-suite numbers + env, review rounds, incidents, not measured. Evidence: F3,
   8 different traces. Value medium, effort ~30 min.

6. **RED-before-fix recipe for authors; ban `git stash` in worktrees.** One paragraph in
   `docs/agents/WORKFLOW.md` §Git: prove RED by a tests-first commit or a detached throwaway worktree
   (`git worktree add --detach $TMPDIR/prev <sha>`), never `git stash` (shared `refs/stash`). Same line in
   the SOULs. Evidence: F5, PR #5 incident. Value medium (cross-worktree data loss risk), effort 10 min.

7. **Missing parent branch = dependency block.** SOUL "Parents" rule + `PARENT_LINE`: "If
   `origin/<parent branch>` does not exist, `kanban_block(kind="dependency")`; never fall back to main."
   Evidence: F7, `t_be60e4ed`. Value medium, effort 5 min.

8. **Tool-failure blocks: reroute, don't re-specify.** In the orchestration skill / `agr_refill.py`: a card
   with `block_loop_detected` on a `transient` tool error is not sent to auto-decomposer; it is reassigned to
   another worker profile (or parked until a write-path smoke test of the tool passes — read-only success is
   not enough). Evidence: F6, `t_c9980b81` runs 23/26/28. Value medium (4 wasted runs per night), effort
   ~30 min.

9. **Review comment: fixed "Verification boundary" line.** Reviewers already write it by hand ("Full-suite
   counts in the author handoff were not re-run"; CI billing lock). Put it in `REVIEW_CHECKLIST.md` so it is
   always present and machine-greppable for the morning report. Evidence: F4/F9. Value low-medium, effort
   10 min.

10. **Merge-order note for stacked PRs.** The morning report (`scripts/morning-report.ps1`) lists open PRs
    with base ≠ `main` and the order to merge (PR #5 before #6). Evidence: F9. Value low-medium, effort
    ~20 min.

## Open questions for the user

1. Pilot side findings and reviewer P2/P3: keep them in the PR ("Out of scope" / "Follow-ups") or allow
   `gh issue create` in `artsafro/AGR-DigitalTwin-pilot`? (Decides proposal 1.)
2. Until the kpp1 test is fixed, may the footer prescribe `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL`
   for the test run, or should the Hermes terminal stop exporting these variables (machine setting)?
3. agy cards `t_c9980b81` (#103) and `t_6f811afa` (#22): reassign to `dt-worker` / `dt-worker-codex`, or
   wait for an agy fix?
4. Should the author's counterexample step (proposal 3) be mandatory for every `src/`/hooks card, or only for
   issues that state a guarantee ("never", "once", "≤")?
5. The CI billing lock: is it expected to stay for the pilot? If yes, the "CI not green" sentence can become a
   fixed footer fact instead of being re-checked in every review.
