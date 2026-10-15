# pr-review-rounds (regression)

**What is checked.** The highest review round marked on a pull-request comment is at most 3. Expected:
`<= 3`. Measured: that highest number (0 when no comment is marked), with the round, url and first line of
each marker.

**Why.** `docs/agents/REVIEW_CHECKLIST.md` [D073] caps a review at 3 rounds. A fourth round means the merge
kept going past the ceiling.

**Evidence.** Save it before the run (the runner never calls `gh`):

```
gh pr view <branch> --json body,comments
```

into `<main checkout>/logs/pr/<branch slug>/view.json`. `comments` missing or not a list = not measured; the
error says to fetch with that command.

**Detection rule** (grader `twinqa.evals.pr_graders.pr_review_rounds`). Only the first non-empty line of a
comment counts; a quote further down never does. Leading `#`, `*`, `_`, `>` and spaces are stripped, then
the line matches `review round <N>` (optional `Codex`, optional comma) or `round <N> verdict`. Examples:
`## Codex review, round 2 of 2 (src/)`, `## Review round 1 — changes needed`, `**Codex review, round 3**`,
`**Round 1 verdict: ...**`. A first line that starts with `Codex review` or `review` but gives no round
number is unrecognized: the check is not measured, unless some other marker is already over the ceiling
(that still fails). The ceiling is 3.

**References.** Recorded 2026-10-15 with `gh pr view --json body,comments`, except the synthetic file.
`fixtures/four-rounds.synthetic.view.json` is SYNTHETIC: rounds 1–4, plus a comment that only quotes
`## Codex review, round 9` inside prose (that 9 must not count) -> fail, measured 4. `pilot-pr30` is
artsafro/AGR-DigitalTwin-pilot #30 -> pass, measured 2 (`## Review round 1 — changes needed`,
`## Review round 2 — clean`). `agr-pr76` is artsafro/AGR-DigitalTwin #76 -> pass, measured 0 (no review
comments were on the PR). `uv run dt evals --task pr-review-rounds --references` checks all three.
