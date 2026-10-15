# pr-agent-trace (regression)

**What is checked.** The pull request body contains an `## Agent trace` block with all ten fields
(Sessions, Written by, Subagents, Skills, Commands, Hook denials, Retries, Context at handover, Duration,
Commits). Expected: `present, 10 fields`. Measured: that, `absent`, or `incomplete: missing [...]`.

**Why.** The block is how the next session sees what this one actually did (#124). A body without it, or with
an unfilled `<placeholder>`, hands over nothing. `not measured (...)` is a real value: the block was generated
and the fact could not be read.

**Evidence.** Save it before the run (the runner never calls `gh`):

```
gh pr view <branch> --json body,comments
```

into `<main checkout>/logs/pr/<branch slug>/view.json`. None found = not measured, exit 2; the error names
that command.

**Detection rule** (grader `twinqa.evals.pr_graders.pr_agent_trace`). A line equal to `## Agent trace` opens
the span; the span continues over blank lines, `- ` field lines, a lone `-`, and lines that start with `<`
(the same span as `tools/hooks/agent_trace.py`). Every field appears as `- <Field>: <value>` with a non-empty
value that does not start with `<`. Every view must pass.

**References.** Recorded 2026-10-15 with `gh pr view --json body,comments` (bytes kept as fetched).
`agr-pr76` is artsafro/AGR-DigitalTwin #76 -> fail (no Agent trace). `pilot-pr30` is
artsafro/AGR-DigitalTwin-pilot #30 -> pass (all ten fields). `uv run dt evals --task pr-agent-trace --references`
checks the grader against both.
