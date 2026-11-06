# Kanban task t_9e27c5ff: #968 AC08 kernel: invariants relative to the source (no new violators), rerun the 19 ops and the L4 gates

Issue artsafro/AGR-DigitalTwin-pilot#968: AC08 kernel: invariants relative to the source (no new violators), rerun the 19 ops and the L4 gates
Labels: ready-for-agent, level:hard
URL: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/968

## Requirement
Artem 2026-11-05 («да» to the recommendation): on AC08 the kernel invariants are judged RELATIVE TO THE SOURCE - an operation passes when it adds no new violators; what the source already violates (3107 px back faces, the open borders) is recorded as a pre-existing baseline («было до нас»), not a failure of the operation. A repair operation (flip back faces / close borders) is a separate later item, not a first step: it must not change the accepted geometry now. Record this as the next free decision id in `docs/decisions.md` and cite it.

## Specification
### Acceptance
- [ ] Invariant checks take a baseline from the source (per invariant: the set of violating faces/edges/pixels) and report per op: baseline, after, NEW violators; pass = zero new violators and UV/material preservation as before.
- [ ] Rerun the #752 19-op set on AC08 through `jobs/TEC26-OKS/AC08/l4-e2e-v001/run_e2e.py` (#891): the table shows applied N/19 with the reason for every op still refused.
- [ ] Rerun the full #753 gate table (export->readback, delivered compare, album slide 49, SINTEZ) with the new semantics; numbers before/after next to each other.
- [ ] Tests: a synthetic source with a pre-existing violator - an op that keeps it passes, an op that adds one fails, naming the new element.
- [ ] Separate follow-up issue drafted (not done) for the repair op (flip/close), marked waits-artem.
### Inputs and versions
Pilot main at the start sha; AC08 source FBX and dumps from #891 (Drive `753-ac08-l4-e2e/`).
### Out of scope
Changing the AC08 source geometry; the repair operation itself.
### Evidence the PR must bring
Before/after tables, the op list with verdicts, test lines, Drive paths with hashes.

## Context
#752, #753, PR #891 (merged), readiness evaluator blockers 1-2 (areas 3 and 11).

---
## Card policy (Hermes Kanban pilot)

- Source issue: artsafro/AGR-DigitalTwin-pilot#968. Repository you work in: `C:\Users\artsafro\agr-pilot\AGR-DigitalTwin` (remote `origin` =
  https://github.com/artsafro/AGR-DigitalTwin-pilot). Base branch: `main`. Your branch: `improve/issue-968-ac08-kernel-invariants-relative-to-the-s` (already checked out in your
  worktree). Read `AGENTS.md`, `docs/PROJECT_STATE.md` and the matching `docs/domain/` file first, and follow
  `C:\Users\artsafro\hermes_kanban\profiles\COORDINATION_RULES.md` (ownership, overlaps, races, quotas).
  Thin drivers (dt-worker-cursor/-agy/-pi): the CLI you drive reads these files and runs the suite; your
  SOUL's short form of the rules is what you read.
- First check whether `origin/main` already meets the acceptance (COORDINATION_RULES 29). If it does,
  finish with `kanban_complete` citing the commit/PR and the test that proves it; no PR.
- Allowed: commit on your branch, `git push -u origin improve/issue-968-ac08-kernel-invariants-relative-to-the-s`, one pull request:
  `gh pr create --repo artsafro/AGR-DigitalTwin-pilot --base main --head improve/issue-968-ac08-kernel-invariants-relative-to-the-s --title "<title> (#968)" --body-file <file>`.
  The PR body ends with `Closes #968` (an issue whose acceptance says it closes nothing, e.g. an integration
  issue, ends with `Refs #968` instead) and contains the "Agent trace" block from
  `docs/agents/WORKFLOW.md`. Review requests go to the `dt-reviewer` profile via
  `kanban_request_review(summary=..., reviewer="dt-reviewer")`.
- Forbidden: `gh pr merge`, any push to `main`, `--force`, history rewrites, large changes outside the
  issue's scope, creating issues in artsafro/AGR-DigitalTwin-pilot. Side findings: an issue in artsafro/AGR-DigitalTwin-pilot (search for a duplicate
  first) with its URL in the PR description, section "Out of scope".
  Small fixes needed for the acceptance criteria are allowed and listed under "Out-of-scope fixes";
  environment problems are self-repaired first (COORDINATION_RULES.md rules 10-12).
  An acceptance point of the issue that you do not deliver is NOT "Out of scope": deliver it or
  `kanban_block` with the reason.
- Before the review: for every guarantee the issue states ("never", "once", "at most", "<= weld_m", ...)
  write one generated or brute-force probe besides the issue's own examples and list
  `invariant -> probe -> N/N passed` in the PR. Add fail-closed probes: empty, partial, unsupported,
  NaN/inf and exactly-at-threshold input must give fail or an error, never pass/not_run; an output path that
  resolves to an input must exit nonzero and write nothing. An unmapped key, slot or material is an error
  naming it, never a default or the first entry; every input element ends in the output or in a reported
  drop list with its reason; no two of input, output, report and temp (`.partial`) paths are the same file,
  and nothing deletes an input. After a review round, the new regression test
  covers the fixed case combined with the earlier fixes. (Reviewers found every P1 so far with such probes.)
- Hostile self-review before review_requested (COORDINATION rule 50): witnesses for path aliases, duplicated
  input, state changing during the run, clobbered temp names, fresh-process CLI, failing statuses taken as pass,
  stale receipts; list `class -> witness -> result` in the PR and fix failures before asking for review.
- Author receipts (COORDINATION_RULES 28): the PR body has a `## Author receipts` section with three lines:
  `Pattern: <docs/domain/patterns/INDEX.md id> | new-case: <one-line scope>` per new module (the new-case
  marker also goes into the module docstring; `Pattern: n/a` when no module is added). Before review_requested
  list the new modules (`git diff --name-only --diff-filter=A origin/main...HEAD -- '*.py'`) and check EACH has
  the pattern id or the literal `new-case` both in its module docstring and in the PR body (pilot #365);
  `Regression evals: <report path>; P passed / F failed / N not measured (<reason>)` from
  `uv run dt evals --suite regression --output <worktree>/tmp/evals` (all-not-measured with exit 2 and the reason
  "no Claude transcript" is a valid receipt on Hermes branches); before review_requested run
  `uv run dt evals --check-receipt "<that exact line>" --output <worktree>/tmp/evals` and paste its exit 0 -
  exit 1 means the receipt is not real (placeholder, pytest count, wrong counts): rerun the evals, never edit the line;
  `Probe: <invariant> -> <command, seed or bounds> -> N/N`, or `Probe: n/a: <reason>`.
- Harness cards (graders/evals, gates, guards, hooks, agent procedures): write the "Acceptance table"
  (acceptance point -> concrete input -> expected output -> test name, edge rows for event order, resets,
  repeats, empty input) in the PR body BEFORE the code; every row is a test (COORDINATION_RULES.md rule 21;
  template: C:\Users\artsafro\hermes_kanban\profiles\ACCEPTANCE_TABLE.md).
- Git: prove RED with a tests-first commit or a throwaway worktree
  (`git worktree add --detach $TMPDIR/prev <sha>`). Never `git stash`: the stash is shared by all worktrees.
- Tests: `uv sync` once, then
  `python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card <card id> -- env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/<card id>`
  (the FULL suite always through suite_slot.py: at most 2 full suites run on this PC at once, COORDINATION rule 43).
  ONE full suite per PR (rule 49): on the head of the FIRST review request; after changes_requested run only the
  affected tests + the new regressions unless the rework touches shared files (conftest, pyproject, uv.lock).
  Waiting for a slot: start it with terminal background=true and wait with process_manage.
  A regression test must fail on the commit before the fix and pass after it. Report the numbers.
  "0 failed" excludes a failure that also fails on `origin/main` and has an open owner issue/PR: do not fix
  it, do not block on it; list it with the owner under "Out of scope" (COORDINATION_RULES 11).
- Blocked on a decision about the model, the data, or a conflict in `docs/domain/conflicts.md`:
  call `kanban_block` with the exact question and what you tried. Do not guess, do not ask in the PR.
- Runtime cap: 120m. Card-scope failures: up to 3 different repair attempts without asking (COORDINATION_RULES 56); block only for a user decision or an out-of-scope failure (DCC, access, missing data), with the evidence.
- Hand-off: before `kanban_request_review` everything is committed and pushed; metadata carries `branch`,
  `base`, `commit`, `pr`, `changed_files`, `verified`, `open_items`, `next_steps` so the next worker can
  continue from your branch.
