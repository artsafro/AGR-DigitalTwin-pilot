# Regression evals receipt census: last 30 pilot PRs (#789-#847)

Card t_b434280a. Report only, no code changes. Date 2026-11-04.

## Summary

- Verified by script over `gh pr list --repo artsafro/AGR-DigitalTwin-pilot --state all --limit 30` (PR #789..#847), regex copied from `src/twinqa/evals/receipt.py:8`.
- Of 24 code/test/docs-change PRs (excluding 6 research PRs, which have no receipt step), **9 (37.5%) ship a Regression evals line that `--check-receipt` cannot accept**: 6 say `n/a` / `not run`, 3 have no `## Author receipts` section at all.
- 15/24 match the receipt regex form (62.5%). The form is only the first gate: `--check-receipt` also re-reads the report and compares counts (see "Not measured").
- **0 of 30** PRs paste a `--check-handoff ... exit 0` line (only #789 even mentions the flag). The step is skipped by everyone, including the workers with a valid receipt.
- All 6 `n/a`/`not run` lines come from docs-only or test-only changes (`dt-worker-cursor` profile): the worker decides "no evals needed" and writes a free-text reason. Nothing in the card template allows that, and nothing stops it.
- Root cause at the template level: `issues_to_cards.py` FOOTER (cards created from issues) has `--check-receipt` but **no** `--check-handoff` text; only `agr_refill.py` RECEIPTS (L72) has it. RESEARCH_BODY and EXPERIMENT_BODY have no evals step at all.

## Findings

Table (all 30 PRs; class by regex on the `Regression evals:` line; `HO0` = body pastes `--check-handoff` exit 0).

| Class | Count | PRs |
|---|---|---|
| valid form (regex matches) | 15 | 847, 842, 837, 835, 833, 831, 822, 803, 802, 799, 798, 795, 794, 793, 791 |
| `n/a` / `not run` | 6 | 838, 828, 825, 824, 814, 801 |
| missing (no `## Author receipts`) | 9 | 846 (experiment), 806, 805 (improve); 845, 840, 839, 813, 812, 789 (research) |
| placeholder / other | 0 | - |
| `--check-handoff` exit 0 pasted | 0 / 30 | (#789 mentions the flag, no exit line) |

Rejected lines, verbatim: #838 `n/a: agr_tools tests only per card; not measured...`, #828 `not run (test-only change)`, #825 `n/a: docs-only change, not run`, #824 `n/a: test-only change, not run`, #814 `not run (docs-only change, no Python)`, #801 `not run (docs-only; no Claude transcript)`.

By card kind (kind from title/branch; cards themselves not read):

| Kind | PRs | valid | n/a / not run | missing | skip rate |
|---|---|---|---|---|---|
| improve / harness (code) | 23 | 15 | 6 | 2 (#805, #806) | 8/23 = 35% |
| experiment | 1 (#846) | 0 | 0 | 1 | 1/1 |
| research | 6 | - | - | 6 | not applicable (RESEARCH_BODY requires no receipt) |
| **all code-bearing** | 24 | 15 | 6 | 3 | **9/24 = 37.5%** |

By worker profile (PR body "profile" line; only some bodies carry it, `?` = not stated): `dt-worker-cursor` named in 17 bodies: 9 valid, 6 n/a (every rejected line above), research 2. Unattributed (`?`): 6 valid, 2 missing improve (#805, #806), plus the experiment #846 and 4 research. So the "not run" habit is entirely in the Cursor driver profile's PR bodies. Caveat: profile attribution is partial (13 bodies do not name it).

Cross-check of card body templates (read the code, verified):

- `agr_refill.py` L61-80 `RECEIPTS` (IMPROVE_BODY L142, ADOPT_BODY L399): has `--check-receipt` (paste exit 0) and `--check-handoff` (L72, "paste the exit 0 line in the PR"). The only place that does.
- `issues_to_cards.py` FOOTER (L29, used L186): same receipts block **without** the `--check-handoff` paragraph (`grep -c check-handoff` = 0). Cards made from issues never tell the worker to run it. The comment at `agr_refill.py:60` says "edit both"; they drifted.
- `RESEARCH_BODY` (L86) and `EXPERIMENT_BODY` (L151): no evals step, no `## Author receipts`. Acceptable for research (no code); for experiments that put a prototype in `experiments/<slug>/` the step is missing (#846 shows it).
- No template text allows `n/a` for Regression evals; `Probe: n/a: <reason>` is allowed, and the workers appear to have transferred that wording to the evals line.
- The "step" skipped: the one that comes after the full suite and before `review_requested` (run `--check-receipt`, save body, run `--check-handoff`). Every PR has the receipt line written before or without that step; no PR shows the paste.

## How it applies to this repository

- `src/twinqa/evals/receipt.py:8` already defines the form; `dt evals --check-handoff` exists, so the gap is process, not tooling.
- Reviewer side: `docs/agents/REVIEW_CHECKLIST.md` (and the reviewer card text in hermes_kanban) does not run `--check-handoff` on the PR body, so #838 was found by eye. A reviewer-run check makes the skip cost the author one round instead of depending on a reviewer's memory.
- Template side: `C:\Users\artsafro\hermes_kanban\scripts\issues_to_cards.py` FOOTER and `scripts\agr_refill.py` RECEIPTS (outside the pilot repo; edits go through hermes_kanban owner).

## Proposed next tasks

1. **Sync FOOTER with RECEIPTS and derive one from the other (S).** In hermes_kanban, make `issues_to_cards.py` import `RECEIPTS` from `agr_refill.py` (or both from one module) so the `--check-handoff` paragraph cannot drift. Acceptance pair: (a) a card generated from an issue contains the string `--check-handoff` (test fails today: 0 hits); (b) a test asserts FOOTER receipts text == RECEIPTS text. `Archive: no roadmap link` (process hardening, no open roadmap issue names it).
2. **Reviewer step: run `--check-handoff` on the PR body (S).** Add to the reviewer card/`REVIEW_CHECKLIST.md`: save the PR body, run `uv run dt evals --check-handoff <body> --sha <head> --output tmp/evals`; non-zero exit -> P2 "receipt/handoff not real", paste output. Acceptance pair: feeding the body of #838 (`Regression evals: n/a: agr_tools tests only`) gives exit 1 and a P2; feeding #847's body with a matching report gives exit 0. `Archive: no roadmap link`.
3. **State the docs-only/test-only rule explicitly (S).** Either (a) RECEIPTS says "docs/test-only changes still run the evals; all-not-measured with `no Claude transcript` is valid" (the six `n/a` PRs could then have passed with `0 passed / 0 failed / 10 not measured (no Claude transcript)`, as 15 others did), or (b) decide a documented `n/a: docs-only` form and teach the regex. Needs the user's choice (open question 1). Acceptance pair: the chosen form for a docs-only PR -> exit 0; `not run` -> exit 1. `Archive: no roadmap link`.

## Not measured

- I did not run `--check-receipt` against the 15 regex-valid lines: it needs each report file, and many paths are worktree-local (`\c\Users\...\tmp\evals`, `C:/x/t_74ff0bfd_evals/...`) which may be gone. The real reject rate is therefore >= 37.5%. Several paths look MSYS-mangled (`\c\Users\...`: #802, #837, #842), which may itself fail resolution.
- `--check-handoff` exit lines were searched with a regex over the body (`check-handoff` near `exit 0`); a differently worded paste would be missed, but only #789 contains the flag at all.
- Card kind inferred from title/branch, profile from the body; merged-vs-open state not analysed against the skip (open 21, merged 9 in the window).

## Open questions for the user

1. Docs-only/test-only PRs: must they still run the evals (all-not-measured is valid), or do you want an official `n/a` form?
2. Should hermes_kanban own the template fix (proposal 1), given the pilot repo cannot change it?
3. Experiment cards that add prototype code: add the `RECEIPTS` block to EXPERIMENT_BODY?

Sources: all verified by me (gh PR bodies via `gh pr list`, `src/twinqa/evals/receipt.py`, hermes_kanban `scripts/agr_refill.py`, `scripts/issues_to_cards.py`). No external sources.
