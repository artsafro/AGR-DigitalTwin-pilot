# How often do self_queue items duplicate ready-for-agent issues?

Card t_8ffe3b63. Read-only measurement, 2026-11-04. All numbers below were measured by me (scripts in `C:/x/m*.py`, board DB opened `mode=ro`, `gh issue view`, `gh api .../timeline`, `gh pr view --json files`). No outside sources.

## Summary

- Duplicate fix-target pairs found: **2** (#871 and #782). Both ended with two independent PRs on the same files for one issue.
- Denominator: 387 non-research cards made by `agr_refill` (improve/hypothesis/adopt), 184 of them mention some `#N`, 92 mention an `#N` that also has an issue card. Reading each one, only 2 are a real "same fix" duplicate; the rest are context mentions ("do not touch #480", "completed #101", triage batch cards, hypothesis numbers). Rate: 2 / 387 = 0.5 % of cards, 2 / 290 issue cards = 0.7 %. Low, but each one costs a full worker run plus a review.
- Time lost (run seconds of the card whose PR was not the one merged): #871 = 4966 s (83 min, PR #902 closed unmerged); #782 = 10128 s (169 min, PR #798 still OPEN, #799 merged). Total about **252 min**. The merged side also ran, so the pair cost about 2x: 9205 s + 13674 s = 22879 s (381 min) for two fixes of one issue each.
- Common cause: the self_queue item cites an issue that is NOT yet `ready-for-agent`. The improve card is created first; the triage then labels the issue and `issues_to_cards.py` creates a second card for it. Nothing checks "an open card or PR already fixes #N".
- Risk now: the live `self_queue.json` has 234 items, 193 distinct `#N`, and **10 open `ready-for-agent` issues** are cited by 7 queued items (list below). They will duplicate unless handled.
- Smallest rules: (A) `issues_to_cards.py` skips an issue that an open/done improve card or open PR already cites as its fix; (B) `agr_refill.py` drops/defers a queue item whose "Fix #N" target is open and `ready-for-agent`, or turns it into `after`-chained card. One of them is enough for both pairs; A covers both timings seen.

## Findings

### The two duplicates (verified)

| Issue | Improve card (self_queue) | Issue card | Issue labeled `ready-for-agent` | PRs | Overlapping files | Run seconds |
|---|---|---|---|---|---|---|
| #871 (lock `until` ignores call timeout) | t_0900162f, slug `agr-mcp-lock-until-covers-call-timeout`, created 13:14 UTC, 5 h before the label | t_9e233148, created 19:06 UTC (20 min after the label) | 18:46 UTC | #894 (improve/..., opened 19:37 UTC, MERGED 20:47) and #902 (issue card, opened 20:26 UTC, CLOSED unmerged) | all 4: `src/agr_mcp/locks.py`, `src/agr_mcp/server.py`, `src/agr_mcp/tools.py`, `tests/agr_mcp/test_agr_mcp.py` | 4239 (merged) + 4966 (wasted) |
| #782 (`test_run_record` flaky under load) | t_e8a807bd, created 09:38 UTC, 11 min before the label | t_6151b13d, created 09:59 UTC (10 min after the label) | 09:49 UTC | #798 (improve/..., OPEN) and #799 (issue card, MERGED, closed the issue 11-04 01:57) | `tests/test_run_record.py` (both PRs change only this file) | 10128 (open, wasted) + 3546 (merged) |

Both improve cards were created while the issue was still unlabeled (the issue existed, e.g. #871 was opened 12:13 UTC from the PR #870 review; the planner turned the review finding into a queue item, the triage labeled it later). The improve task text says "Fix issues #871 ... " / "Address existing pilot issue #782", so the intent to fix the issue is explicit and parseable.

Not duplicates, checked: #738 (improve t_b4a6a48f -> PR #742 changes `docs/research/harness2-executor-controls.md`; issue card -> PR #750 changes other files; sequential follow-up), #101/#117/#201/#353/#462/#480/#650/#69/#592/#868 (the improve text only mentions them as context or "do not touch").

### Why the existing guards miss it

- `agr_refill.py` (read, `C:/Users/artsafro/hermes_kanban/scripts/agr_refill.py`) has no code-level check of queue items against issues; the only guard is the planner prompt (lines ~290, 320: "never plan what an open or done card already covers"). `issue_labels` (l.445) is used for the queue/issue chain, not for self_queue items.
- `issues_to_cards.py` makes one card per `ready-for-agent` issue; it does not look at improve cards or PRs that cite the issue.
- GitHub shows the problem only late: the cross-reference of the second PR appears on the issue 49 min (#871) / 20 min (#782) after the first, too late to stop the second worker.

### Live exposure (verified on 2026-11-04 evening)

Open + `ready-for-agent` issues cited by queued items: #843, #844 (`agr-tools-duplicate-matid-list-not-last-wins`), #848 (`agr-tools-wrap-to-duplicated-matid-unmeasurable`), #855, #856 (`agr-tools-wrap-target-missing-slot-and-ambiguous-msg`), #861 (`agr-tools-ui-scope-keeps-selection-row-selects-components`), #862 (`agr-tools-ui-reqs-match-suite-json`), #865, #866 (`body-gn-point-domain-test-tmp-path-own-snap`), #897 (`agr-tools-qt-tests-run-in-uv-suite`). Some of them already have fix PRs (#847, #854, #849, #869, #874 per today's triage), so these items are stale or duplicate right now. 861/862/897 carry `block:max-tools`, which keeps the issue cards from being dispatched to ordinary workers, so a duplicate is less likely there.

## How it applies to this repository

- `C:/Users/artsafro/hermes_kanban/scripts/issues_to_cards.py` (not edited): place for rule A.
- `C:/Users/artsafro/hermes_kanban/scripts/agr_refill.py` (not edited): place for rule B (before `create_topic`, ~l.779) and the planner prompt (~l.290).
- No change in this repository except this report.

## Proposed next tasks

1. **issues_to_cards: skip an issue already fixed by an open improve card or PR** - Before creating a card for `ready-for-agent` issue N, skip (and log once) if an open/running/done non-issue card body matches `Fix(es)? issues? #N|Address .* issue #N`, or `gh pr list --search "#N in:body" --state open` returns a PR whose head starts with `improve/` or `fix/`. Input: the #871 and #782 timelines above -> expected pairs: 2/2 prevented (tests with those two card bodies as fixtures). Value M / effort S. Archive: no roadmap link.
2. **agr_refill: gate self_queue items on cited fix targets** - When an item's task has `Fix|Address ... #N` and `#N` is open + `ready-for-agent` (or has an issue card), drop it from the queue (to `taken` with reason `covered-by-issue-N`) instead of creating the card. Input: current `self_queue.json` -> expected output: the 7 slugs above listed (verify each against its open PR first), 0 for the other 227 items. Value M / effort S. Archive: no roadmap link.
3. **Planner prompt + queue schema: `fixes: [N]` field** - Make the planner write the fixed issue numbers in a structured field, so rules 1-2 do not depend on regex over prose. Value S / effort S. Archive: no roadmap link.
4. **One-off cleanup** - Close PR #798 (same file as merged #799) and review the 7 queue slugs against PRs #847, #849, #854, #869, #874. Owner: operator. Value S / effort S. Archive: no roadmap link.

## Open questions for the user

1. May a self_queue improve card that cites an unlabeled issue keep running (and the later label be ignored), or should the issue card win? Rules 1-2 make the improve card win; the alternative is to cancel the improve card when the label appears.
2. Should PR #798 (open, duplicate of merged #799) be closed by the operator now?
3. Is the rate (2 in 387) high enough to justify the work, or is a weekly report of such pairs enough?

## Not measured

- Wasted time counts run seconds from `task_runs`, which includes retries and rework rounds, so it is an upper bound for a clean first run.
- Pairs where the same issue was fixed by two cards that do not name it in the text were not searched.
- Hypothesis/adopt numbers `#N` are experiment ids, not issues, and were excluded by reading.
