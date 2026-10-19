# Why adopt PRs keep missing author evidence receipts and new-case markers

Research card t_5a4363b7, 2026-10-15. Pilot `main` at `8255c4b`. Sources are all internal (PRs, issues,
files at a given revision, one command I ran myself); no web source was needed. "Verified" means I read the file or ran
the command; "reviewer says" means I only quote a review comment.

## Summary

1. The three items (regression-eval receipt, generated-counterexample probe, `new-case` / pattern marker) are
   **missing from every author-side instruction the adopt and improve workers receive**: the `ADOPT_BODY` and
   `IMPROVE_BODY` card templates (`hermes_kanban/scripts/agr_refill.py:87-112, 291-322`) and the SOULs of
   dt-worker-cursor / -agy / -codex. The only place the items appear is `docs/agents/REVIEW_CHECKLIST.md:7-30`.
2. That file is **ambiguous about who must act**: line 3 addresses it to the reviewer ("Reviewer: any agent that is not the
   author"), `AGENTS.md:24` indexes it as "Review questions and how to run a Codex review", and `WORKFLOW.md` has
   0 matches for `dt evals`, `new-case` or the checklist. The author duties sit inside a document authors have no reason to open.
3. The reviewer SOUL tells the reviewer to apply that checklist (`profiles/dt-reviewer/SOUL.md:5`), so the
   reviewer checks items the author was never told about. The finding is P2/P3, it becomes an issue, the PR still
   merges, and no instruction changes. That is why it recurs: 8 of 8 adopt PRs (#98-#135) have 0
   regression-eval receipts and 0 `new-case` markers. 7 of them led to follow-up issues for these items.
4. When a card body *does* name the items (the follow-up cards for #99, #105, #111 -> PRs #133, #134, #146), the
   workers deliver them: 3/3. So the cause is **missing instructions, not ignored ones**.
5. A side cause for the eval receipt: the regression suite grades Claude Code transcripts (`evals/README.md:54`).
   On a Hermes-driven branch it returns `0 passed, 0 failed, 10 not measured; exit 2` (I ran it) and by default writes
   into the main checkout, outside the worker's worktree. The receipt is cheap but carries no signal, and that
   default output path conflicts with the worker rule "the worktree is the only place you write".
6. Proposals (user decides, nothing edited): put the three receipts into the card templates. Add a PR-body
   receipt grader. Move the author duties out of the reviewer checklist into an author section linked from
   `WORKFLOW.md`.

Filename note: the card text names `docs/research/adopt-evidence-receipts.md`, but its policy section names
`docs/research/adopt-pr-evidence-receipts.md`. I used the policy name, which the completion metadata also uses.

## Findings

### F1. Per-PR table

"Template" is the card body the worker received, i.e. the `agr_refill.py` constant that `create_topic` renders.
The PR bodies do not quote the card. The template line numbers are those of `agr_refill.py` at hermes_kanban HEAD `0f9ef59`.
`ADOPT_BODY` was last changed at 16:24 local (`7205b30`, scope wording only). The evidence items never appeared in any version
(`git log -L291,320`: 7205b30, af7ad5b, 7ac683f, e736443; none touches evidence items).

| PR (created, UTC) | Worker / writer | Missing item (review -> issue) | Card template: where the item is / is not | Pilot instruction at PR base |
|---|---|---|---|---|
| [#51](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/51) (09:27; "Improve", not adopt) | dt-worker-codex / gpt-6.1-sol | regression-eval report path + counts ([review](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/51#issuecomment-6188937733) -> [#52](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/52)) | `IMPROVE_BODY` 87-112: "Code changes need a regression or unit test and a green `uv run pytest -q`" (104); body = "proposals, what was verified, Agent trace" (109-110). No evals, no probe, no pattern | base `91795c0` has checklist 14-19 (evals, from `ca2c4b8`), **lacks** "Author counterexamples" 21-30 (added `354c959` 11:23 local); the reviewer did not raise the probe |
| [#98](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/98) (13:16) | dt-worker-cursor / Cursor grok-4.7-medium | `new-case` marker, author generated probe, regression evals (round 1 P3 -> [#99](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/99); repeated in round 2) | `ADOPT_BODY` 291-322: Acceptance table (309-310), tests "that reproduce the measured improvement" + full suite (313-314), PR body "what was adopted, numbers before/after, Agent trace, Closes" (318-319). No evals, no probe, no pattern | base `3cf7c93` contains both checklist sections (14-19, 21-30) and item 1 (7-9) |
| [#104](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/104) (13:29) | dt-worker-agy / gemini-3.8-flash-high | regression evals + generated-counterexample receipt ([review](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/104) P2 -> [#105](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/105)) | same `ADOPT_BODY`; the reviewer still called the PR "bounded new-case" itself, so no marker issue was filed | base `5ff8015` contains all |
| [#109](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/109) (13:51) | dt-worker-agy / gemini-3.8-flash-high | `new-case` marker, author beyond-matrix probe, regression evals ([review](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/109#issuecomment-6193798660) P3 -> [#111](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/111)) | same `ADOPT_BODY` | base `5ff8015` contains all |

The pattern did not stop at the four PRs named in the card. I verified by reading the review comments:

| PR | Writer | Review finding -> issue |
|---|---|---|
| [#115](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/115) Adopt #100 | agy | P2 regression-eval + generated probe (checklist 14-29) -> #119 |
| [#127](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/127) Adopt #101 | agy | P2 receipts + pattern/new-case -> #128 / #129 |
| [#135](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/135) Adopt #107 | agy | P2 regression-eval (14-19), P3 `new-case` (7-9) -> #136 / #137 |
| [#102](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/102), [#103](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/103) | agy / - | regression evals listed only as "not measured" in the Verification boundary, no issue |

I counted over the last 109 pilot PRs with a regex on the body (`gh pr list --state all --limit 120`; verified, approximate):

| Body contains | All PRs | Adopt PRs #98-#135 (8) | Follow-up PRs #133/#134/#146 |
|---|---|---|---|
| `logs/evals/runs` or `dt evals` | 9 | 0 | 3/3 (#133, #134, #146) |
| `invariant ->` / `N/N` / `seed` | 11 | 1 (#135, regex hit only) | 3/3 |
| `new-case` | 2 | 0 | 2/2 that concern a module (#133, #146) |

### F2. Author-side instructions: the requirement is missing

Verified by `grep -n -i -E 'dt evals|regression.eval|new-case|counterexample|brute|REVIEW_CHECKLIST'` over
`hermes_kanban/profiles` and `scripts/*.py`:

- `scripts/agr_refill.py` `ADOPT_BODY` (291-322) and `IMPROVE_BODY` (87-112): 0 hits. Line 104 says only "a
  regression or unit test and a green `uv run pytest -q`", so a worker reads "regression" as pytest.
- `profiles/dt-worker-cursor/SOUL.md`, `dt-worker-agy/SOUL.md`, `dt-worker-codex/SOUL.md`: 0 hits. Their evidence
  rules are "a regression test must fail before the fix and pass after" (agy SOUL:32) and the Agent trace block.
- `profiles/ACCEPTANCE_TABLE.md` (required for adopt cards, line 3): rows A/E/R only; no receipt rows.
- `scripts/issues_to_cards.py:49-52` (issue cards, not adopt) and `profiles/dt-worker-pi/SOUL.md:19-21` do require
  "one generated or brute-force probe ... `invariant -> probe -> N/N passed`". Neither mentions regression evals or `new-case`.
- Only `profiles/dt-reviewer/SOUL.md:5` points at `docs/agents/REVIEW_CHECKLIST.md`, and it points the reviewer there.

### F3. Pilot docs: the requirement is present but addressed to the reviewer (ambiguous)

- `docs/agents/REVIEW_CHECKLIST.md:3-5`: "Reviewer: any agent that is not the author ... Post the answer as a PR comment".
- Lines 7-9: item 1 asks the reviewer whether a module "is honestly marked `new-case`". No author action and no place
  (code docstring or PR body) is named. `new-case` appears elsewhere only in `docs/HARNESS_PLAN.md:304,328` (Russian,
  a planned hook) and nowhere in `WORKFLOW.md`, `AGENTS.md` or `docs/domain/patterns/INDEX.md` (verified by grep).
- Lines 14-19 put an author duty ("the author runs `uv run dt evals --suite regression` ... names in the PR the report
  path") inside reviewer question 3, "Did the checker or the tests pass ... run by the reviewer?".
- Lines 21-30 "Author counterexamples" are the clearest author text, but they are still only in this reviewer file.
- `AGENTS.md:24` routes readers to the file for "Review questions and how to run a Codex review". `docs/agents/WORKFLOW.md`
  has 0 hits for `dt evals`, `new-case` or `REVIEW_CHECKLIST` (verified), so the task loop an author follows never reaches it.

### F4. The regression-eval receipt has a practical contradiction for Hermes workers

I ran `uv run dt evals --suite regression` in this worktree on branch `docs/research-adopt-pr-evidence-receipts`.
It took a few seconds and printed `Report: C:\...\AGR-DigitalTwin\logs\evals\runs\20261015-183034-regression\report.json;
0 passed, 0 failed, 10 not measured; exit 2`. Every task reports "no evidence":

- the transcript graders look for `logs/transcripts/<branch>-pr*-<uuid>.jsonl`, which only Claude Code sessions produce
  (`evals/README.md:54`);
- the PR graders look for `logs/pr/<branch>/view.json`, which nothing in the Hermes flow writes.

The consequences:
- The receipt costs one command, but on Hermes branches its content is always "N not measured (no transcript)". The
  checklist accepts that (line 17-18: "named with its reason, never counted as a pass"), but authors are not told that an
  all-not-measured run is the expected, acceptable receipt.
- The checklist's merge criterion is "100 %" (line 17), and exit code 2 looks like a failure. An author who did run it could reasonably
  think it was not applicable. This is my inference: no PR body or comment records such a decision.
- The default `--output` is `<main>/logs/evals/runs/...`, in the main checkout. The worker SOULs say the worktree "is the only
  place you write". This is a soft contradiction; `--output` can redirect the report.

### F5. Why review does not fix it

`REVIEW_CHECKLIST.md:40-45` routes P2/P3 to issues, and the merge does not wait for them. Each recurrence produced a
per-PR follow-up card (#133, #134, #146), never a change to the template that caused it. `COORDINATION_RULES.md` records the
rule-21 lesson for harness cards (line 91, ledger line 167) but has no entry for this recurrence.

## How it applies to this repository

| File | Role in the cause |
|---|---|
| `C:\Users\artsafro\hermes_kanban\scripts\agr_refill.py:87-112, 291-322` | Adopt/improve card templates: no receipt items (primary cause) |
| `C:\Users\artsafro\hermes_kanban\profiles\dt-worker-{cursor,agy,codex}\SOUL.md` | No pointer to the author duties |
| `C:\Users\artsafro\hermes_kanban\profiles\ACCEPTANCE_TABLE.md` | Required for adopt cards; no receipt rows |
| `C:\Users\artsafro\hermes_kanban\scripts\issues_to_cards.py:49-52` | Has the probe item, as a model for the fix |
| `docs/agents/REVIEW_CHECKLIST.md:3-30` | Author duties written inside the reviewer checklist |
| `docs/agents/WORKFLOW.md`, `AGENTS.md:24` | No route from the author's task loop to those duties |
| `evals/README.md:52-64`, `src/twinqa/evals/` | Regression suite measures nothing on Hermes branches; default output outside the worktree |

## Proposed next tasks (proposals only; the user decides; no issues created)

Each proposal has acceptance as concrete input -> expected output pairs (COORDINATION_RULES rule 21).

### T1. Author receipts block in the adopt / improve / issue card templates (hermes_kanban) — value high, effort S

Add one bullet to `ADOPT_BODY`, `IMPROVE_BODY` and the issue-card body. It requires a `## Author receipts` section in
the PR body with three lines:
- `Pattern: <INDEX.md id> | new-case: <one-line scope>`, one line per new module;
- `Regression evals: <report path>; P passed / F failed / N not measured (<reason>)`, from
  `uv run dt evals --suite regression --output <worktree>/tmp/evals`;
- `Probe: <invariant> -> <command, seed or bounds> -> N/N`, or `Probe: n/a: <reason>`.

The bullet also says that an all-not-measured eval run with its reason is a valid receipt.

| Input | Expected output |
|---|---|
| `ADOPT_BODY.format(...)` for issue 93 | rendered text contains `## Author receipts`, `dt evals --suite regression`, `new-case`, `invariant ->` |
| `IMPROVE_BODY.format(...)` | same four strings |
| issue-card body from `issues_to_cards.py` | same four strings (probe line already present; evals + new-case added) |
| next 3 adopt PRs after the change | reviewer files 0 P2/P3 issues for missing receipts (measured over the next 3 adopt reviews) |

### T2. `pr-author-receipts` regression grader over the PR body (pilot, harness card) — value high, effort M

A procedural grader next to `pr_agent_trace` that reads `logs/pr/<branch>/view.json` and fails when the receipts are missing.
The worker writes that file with `gh pr view --json body,comments` before requesting review, so the reviewer stops
finding these items by hand. It needs an Acceptance table before the code (rule 21).

| Input (PR body) | Expected output |
|---|---|
| adopt PR body without a `Regression evals:` line | `fail`: "missing regression-eval receipt" |
| `Regression evals: logs/evals/runs/20261015-183034-regression/report.json; 0 passed, 0 failed, 10 not measured (no transcript)` | that line passes |
| `Regression evals: 10 passed` without a report path | `fail`: "no report path" |
| `Probe: n/a: deterministic lookup, no stated guarantee` | probe line passes |
| `Probe: count-once -> 10/10` without a command or seed | `fail`: "probe not reproducible" |
| diff adds `src/twinqa/geometry/component_volume.py`, body has no `Pattern:` / `new-case:` line for it | `fail`: "module without pattern or new-case" |
| docs-only PR (no new module, no stated guarantee) | `pass` with `Probe: n/a` and no `Pattern:` line required |

### T3. Author section in the pilot docs, linked from the task loop (pilot docs) — value medium, effort S

Move the author duties from `REVIEW_CHECKLIST.md:7-9, 14-19, 21-30` into a `## Before requesting review (author)`
section. Name where `new-case` goes (module docstring and PR body). Name the worktree-local `--output`. Say that an
all-not-measured run is acceptable, which needs the user's decision Q1. Link the section from `WORKFLOW.md` and the
`AGENTS.md:24` row. The reviewer questions keep only "check the receipt".

| Input | Expected output |
|---|---|
| `grep -n "dt evals" docs/agents/WORKFLOW.md` | ≥ 1 hit, pointing to the author section |
| `grep -n "new-case" docs/agents/WORKFLOW.md` | ≥ 1 hit, naming the docstring + PR body location |
| `AGENTS.md` "Where things are" row for the checklist | names author receipts as well as review questions |
| `uv run pytest -q tests/test_docs*` (or the doc-link test that exists) | green; no broken anchors |

## Open questions for the user

1. Is a regression-eval run with `0 passed, 0 failed, N not measured (no transcript)` and exit 2 an acceptable receipt for
   Hermes-driven branches? The alternative is a separate eval scope for Hermes workers (e.g. PR-body graders only),
   because the transcript graders can never measure them.
2. Where should the `new-case` marker live: in the module docstring, the PR body, or both? The checklist does not say.
3. Should the eval report go to the worktree (`--output <worktree>/tmp/evals`) or stay in the main checkout's `logs/`?
   The default output writes outside the worker's worktree.
4. Should P2/P3 findings that recur 3 or more times be routed to a template change (hermes_kanban) instead of one follow-up issue per PR?
5. Side finding, outside this card: `WORKFLOW.md:219-221` says the Agent trace block is generated by `agent_trace.py` and
   "never written by hand", but every Hermes PR body above writes it by hand with "not measured" fields.

## Sources (verified unless marked)

1. PR #51 body + review: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/51 ; issue #52
2. PR #98 body + reviews 1-2: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/98 ; issue #99
3. PR #104 body + review: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/104 ; issue #105
4. PR #109 body + review: https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/109 ; issue #111
5. Reviews of PRs #102, #103, #115, #127, #135 (issues #108, #119, #128, #129, #136, #137, numbers taken from the comments)
6. `gh pr list --state all --limit 120` body regex counts (F1)
7. `docs/agents/REVIEW_CHECKLIST.md` at `8255c4b`; its history `ca2c4b8`, `354c959`; ancestry of PR bases `91795c0`, `3cf7c93`, `5ff8015`
8. `docs/agents/WORKFLOW.md`, `AGENTS.md`, `evals/README.md`, `docs/HARNESS_PLAN.md` at `8255c4b`
9. `hermes_kanban/scripts/agr_refill.py` (HEAD `0f9ef59`) and its `git log -L`; `scripts/issues_to_cards.py`
10. `hermes_kanban/profiles/{dt-worker-cursor,dt-worker-agy,dt-worker-codex,dt-worker-pi,dt-reviewer}/SOUL.md`, `ACCEPTANCE_TABLE.md`, `COORDINATION_RULES.md`
11. My run: `uv run dt evals --suite regression` -> `0 passed, 0 failed, 10 not measured; exit 2`
