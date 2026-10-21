# Capability B: closed ticket to a local PR-ready branch

Suite: `capability`. Grader: `capability_ticket`. Shared launcher:
`tools/qa/capability_b01.py` (eval A), now with `--ticket <pilot issue number>`.
This is an evaluation, not permission for the evaluated session to publish anything.

## Reference input and known answer

Pilot #111, **Component volume: document new-case and author evidence boundary**,
was CLOSED with `documentation`, `ready-for-agent`, `level:simple` labels before
launch. The parent fetches issue metadata with `gh issue view --json`; it rejects
open, unlabelled, non-doc/test, empty and malformed tickets before allocating output.
The frozen input is `reference/ticket.json`. No solution/PR text is supplied to the
child. Known answer: pilot PR #146, commit
`f3fa7d450804e55f1158eaccbd17381eb4b165ea`.

Replay base: `fab1fdd74a07b30f2caccf88135938f2338ab0a0`, the known-answer commit's
first parent, not today's already-solved main. This base already contains the
component-volume evidence tests; their documentation regression fails before the
replay change. The child must use that checkout's instructions and dependencies.
The current launcher and graders run in the parent, not from the historical tree.

## Actual first run [D159]

The operator explicitly extended D158 to eval B: prepared
`CODEX_HOME=C:/x/codex-eval-home`, **no OS sandbox**, external user skills allowed
and recorded. Context label: **repository + user skills**, never repository-only.
A separate Windows account/VM for a truly repository-only run remains a **later
follow-up**; do not provision it in this task.

```bash
uv run python tools/qa/capability_b01.py --agent codex --model gpt-6.1-sol --ref fab1fdd74a07b30f2caccf88135938f2338ab0a0 --ticket 111 --run-dir C:/x/capability-evals/t_dad8c227-reference-v001 --codex-home C:/x/codex-eval-home --isolation 'repository + user skills; no OS sandbox; D159' --timeout 1800 --command-json '["codex","--no-daemon","exec","--ephemeral","--json","--enable","skip_host_skill_discovery","--disable","memories","--disable","plugins","--model","gpt-6.1-sol","{prompt}"]'
```

Commands for all supported agents are the eval A commands in
[`../capability-b01/task.md`](../capability-b01/task.md#inputs-and-invocation).
Codex uses `codex exec`; Claude remains paused and has no second reference.
DeepSeek requires its actual installed argv through `--command-json`; no CLI
protocol is invented. Placeholders additionally include `{body}` (PR Markdown).
There is no second launcher. Default Codex invocation still requests its OS
sandbox; this reference uses only the explicitly approved prepared-home command.

- Codex CLI **0.160.1**, model **gpt-6.1-sol**; session exit **0**;
  launcher elapsed **161.512 s** (descriptive, not a performance guarantee).
- Branch `harness/capability-ticket-111-cb5ef7cd5110`; solution head
  `187a27fe16e55052e02757502f717f446b6984d8`; committed, clean worktree.
- Child reports RED **1 failed**, GREEN **449 passed** focused tests. The actual
  command output is retained in the local diff's added evidence files. These are
  child-session results, not the implementer's full-suite receipt.
- Local PR artifact result: **3/4 structural checks**, aggregate
  **0 passed / 1 failed / 0 not measured**. Trace, numeric-reference rule and named
  branch/nonempty diff pass. The receipt-field check fails: the body discusses
  probes and scope but lacks literal `Pattern:` and `Probe:` receipt fields.
- Procedural/review graders: **0 passed / 0 failed / 10 not measured**.
  Native Codex stdout is retained unchanged; Claude-only parsers cannot classify
  it. No synthetic transcript, empty comment list or zero-review claim is created.
- Overall **passed=false / not ready**. This is the first **negative reference**,
  not a successful capability claim. Do not amend its answer or rerun the agent
  merely to make the baseline green.
- Actually loaded external skills: **codex-work-route**, **codex-work-review**.
  The route read succeeds before a combined command's denied GitHub lookup exits
  1 (its frontmatter is visible in stdout); the review read exits 0.
  **codex-work-engineering**, **codex-work-loop** are named only. Scope: native
  parent transcript; nested contexts are not separately captured.
- No push, real PR or full-suite command appears in the executed native commands.
  An initial read-only `gh issue view` attempt was denied; the child then reads
  the local ticket/prompt. No successful GitHub operation is claimed.
- Original protected tracked inputs, benchmark/jobs inventory unchanged;
  worktree and its temporary branch removed successfully. Prepared home retained.

## Grading and post-reference threshold

Structural checks are specification assertions, not learned performance cutoffs:
Agent trace (existing PR grader), numeric references (existing PR grader reading
local `git diff`), naming/nonempty diff, and lexical Author receipt fields. The
receipt check verifies presence only, **not truth, provenance or issue correctness**.
Review-round count remains unmeasured without actual review evidence; it is not
inferred from a Markdown body. Existing PR graders also accept `body` paths directly
instead of recorded `pr` JSON; their normal recorded-gh behavior is unchanged.

Selected **after** the reference: future full readiness requires **4/4 local
checks**, procedural **0 failed / 0 not measured**, session exit 0, a clean
committed solution, unchanged protected inputs and successful cleanup. The first
3/4 result does **not** lower the threshold. No latency/token limit is inferred
from one sample. The existing review ceiling remains <=3, not a new threshold.

```bash
uv run dt evals --task capability-ticket --main C:/x/capability-evals/<run> --output <new-output>
uv run dt evals --suite capability --main C:/x/capability-evals/<run> --output <new-suite-output>
```

The task accepts `--evidence body=<body.md> --evidence diff=<local.diff>
--evidence branch=<branch.txt>` overrides. `--suite capability` also selects eval A;
absent B01 geometry reports in a ticket-only run are not measured, not a failure
of ticket artifact discovery. Missing body/diff/branch evidence is not measured
with a named error; unreadable/unsupported/empty evidence never becomes pass.

## Artifacts, integrity and publication boundary

The launcher creates a unique external run directory and a clean disposable
worktree, pre-names a `harness/capability-ticket-<issue>-<random>` branch, retains
`pr-body.md`, `local.diff`, `branch.txt`, issue metadata, raw native transcript,
stderr, prompt, grader reports and `reference.json`, then removes worktree/branch.
The child may commit locally but is forbidden to push or open a real PR. Focused
tests need no suite slot; the full suite is prohibited in the child prompt.

Git protocol/pushurl and GH_HOST overrides defend against accidental publication;
they are process-local and do not modify shared remote configuration. **Without
an OS sandbox they are not a security boundary against a hostile child that
clears environment overrides.** The launcher never invokes push or PR creation.

Existing run directories and overlaps with either checkout or prepared home are
rejected. Launcher-owned post-child files use exclusive creation: a pre-created
file, symlink or hardlink cannot redirect the launcher's write onto an input.
Finalization errors still run worktree cleanup; no existing output is overwritten.
Before/after snapshots detect protected-file edits, deletion and newly added
protected paths; they cannot detect an edit restored between snapshots. The first
reference predates the added-path/exclusive-write hardening; no retroactive
stronger integrity claim is made for it.

`reference/launch.json` is the original unmodified attempt record. The separate
committed `reference.json` records limitations, post-run threshold and hashes of
the actual committed artifacts. Raw transcripts remain outside git under the run
path; their hashes are retained. `test_ticket_reference` checks hashes and regrades
the frozen local artifacts to the same **3/4 FAIL**, not a fabricated successful
answer. Regrades use new output directories and do not launch another agent.

`PROJECT_STATE.md`: **post-merge regeneration per AGENTS.md**. The generator now
includes eval B and its negative/unmeasured result; this branch provides a scratch
expected diff in the PR, not a forbidden edit to generated state on a task branch.
