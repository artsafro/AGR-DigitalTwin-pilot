# pr-numeric-literals (regression)

**What is checked.** No new numeric literal in the engine (`src/dt_ai/`) or the delivery checker
(`src/twinqa/`) without a reference. Expected: 0. Measured: the count, with file, line, literal and the line
text. `src/twinqa/evals/` is this harness, not the delivery checker, and is not scanned.

**Why.** PR #76 added `STRAY_EMBED_MAX_M = 0.5` and other thresholds that no decision and no tolerances file
named. An invented number becomes a rule the sources do not support (lesson of that PR).

**Evidence.** Save both before the run (the runner never calls `gh`):

```
gh pr view <branch> --json body,comments
gh pr diff <branch>
```

into `<main checkout>/logs/pr/<branch slug>/view.json` and `diff.patch`. The body is part of the reference
rule: missing, the check is not measured unless a failure was already found in the diff.

**Detection rule** (grader `twinqa.evals.pr_graders.pr_numeric_literals`). Added lines of in-scope `.py` files
only. The scanner walks each hunk's new side and skips comments and string literals (a hunk starts outside a
string). `0`, `1` and `2` in any spelling are exempt (identities, halves `/ 2`, xy slices `[:, :2]`, rounding digits; PR #76
showed `2` only in those roles). A value that also occurs on a removed code line of the same
file was moved. Referenced means a decision-log id (`D` and one to four digits, as in `[D073]`) or the word
`tolerances` on that added line; or the same numeric value on a PR-body line or any added line that also
carries such a reference; or the same value added in a file whose path contains `tolerances`.

**References.** Recorded 2026-10-15 (`gh pr view --json body,comments`, `gh pr diff`; bytes kept as fetched).
`agr-pr76` is artsafro/AGR-DigitalTwin #76 -> fail (`STRAY_EMBED_MAX_M = 0.5` in `src/twinqa/geometry/checks.py`
among the hits). `pilot-pr30` is artsafro/AGR-DigitalTwin-pilot #30 -> pass (the diff does not touch
`src/dt_ai/` or `src/twinqa/`). `uv run dt evals --task pr-numeric-literals --references` checks both.
