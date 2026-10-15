# Task workflow

Adapted from the AGR orchestration cycle (`docs/agr/` and the archive). Scale it to the
task: a one-line fix skips most steps; a multi-stage delivery uses all of them.

## Loop

Harness work (issues labelled `harness`) runs grilling -> to-spec -> to-tickets -> implement ->
code-review (user 2026-10-14 [D091]); production work runs the steps below.

0. **Card and recitation.** A task with an issue moves on the board (`docs/agents/KANBAN.md`): In progress
   when taken, Needs you when it waits on the user. Then recite the ticket ("Recitation" below)
   before any file is changed.
1. **Goal and discovery.** Read `docs/PROJECT_STATE.md`, the relevant `docs/domain/` file,
   the matching accepted case (`docs/cases.md`) and the real inputs. A script or MCP that
   exists is not working until there is current evidence (`CAPABILITIES.md` status).
2. **Questions.** Ask only what changes the result, inputs, architecture, acceptance,
   destructive actions or publication. Decide routine details yourself.
3. **Contract.** For multi-stage work write in `jobs/<JOB>/STATE.md` (or the PR): goal and
   acceptance, exact inputs/versions, profile (NPM-OKS, VPM-OKS, NPM-territory…), owner of
   each scene/port/export, outputs, mandatory checks, stop conditions, next step. "Model"
   alone does not define the profile — ask when it matters. A job contract starts with the
   Requirement section and the Context line (template below, "Job contract").
4. **Plan.** Stages, dependencies, reused tools, checks. An open decision blocks only the
   stages that depend on it.
5. **Execute** in narrow stages. Pure computation in `src/`, DCC calls in adapters/tools,
   object parameters in the job, manual decisions in a record with their source. Every
   rerun writes a new versioned output; keep manifests and hashes.
6. **Verify independently.** The executor's report, exit 0 or a child agent's summary is
   not evidence. Read the actual files back. Classify a failure (source / tool / code /
   test / contract), fix the cause, rerun the affected checks. A failed mandatory check is
   never turned into a pass by rewording. After two failures with the same cause, stop that
   path, save the state and propose the next step.
7. **Hand off.** Compare the result with the Requirement (the user's wording, profile and
   acceptance in the contract), item by item: met, not met, or changed by a later user decision
   (with its date or `D<n>`); report what is done, what was checked (commands, evidence paths)
   and what is open. On restart, read saved outputs and
   hashes before repeating any mutation (`run-evidence` skill).

## Recitation (#130)

The first step on a ticket, before any file is changed. Restate in the plan, one line per field, in the
agent's own words:

- **Requirement** - what the user asked, quoted, and the profile if a model is involved;
- **Specification** - each Acceptance item, Inputs and versions, Out of scope, Evidence the PR must bring;
- **Context** - the files and rules named, which are then read first.

A field that is empty or missing, or two fields that contradict each other, stop the task before any work:
name the field, move the card to Needs you and give the issue `needs-info` (`docs/agents/issue-tracker.md`,
"Ready gate"). Do not fill a field from a guess. A ticket written before the template (no Specification
section) is recited from what it has, the missing fields are named as missing, and the agent stops on them
like on an empty field.

## Job contract (#130)

`jobs/<ID>/STATE.md` opens with the contract. The Requirement section is copied once from the user and not
edited afterwards; a later decision is added below it with its date or `D<n>`, never written over it. The
handover (step 7, `/handover`) compares the result with this section item by item.

```markdown
# <ID> (<object name>) - <profile>, <date>

Status: <draft | built | accepted by the user (<date>) | ...>
Context: <files and rules read first: docs/domain/<file>, patterns/<id>, [D<n>], cases.md#<case>>

## Requirement

> <the user's wording, verbatim, in its language> (user, <date>)

- Profile: <NPM-OKS | VPM-OKS | NPM-territory | ...>
- Acceptance:
  - [ ] <checkable item>
- Later decisions: <date or D<n>: what changed> (none yet)

## Sources
...
```

## Subagents (Claude Code, user 2026-10-13 [D071])

The main agent keeps dumps, MaxScript output, benchmark runs and the pattern catalogue out of its own
context. It delegates them to the read-only subagents in `.claude/agents/`:

| Need | Subagent |
|---|---|
| Read a source scene or file: inventory, units, layers, sections at given heights, screenshots, slab and helper candidates | `source-inspector` |
| Is there a rule? (pattern, case, conflict, answered question) | `pattern-librarian` |
| Run benchmarks or tests and get a pass/fail table | `bench-runner` |
| Check a built model independently | `independent-checker` |
| A numeric question about an FBX or a dump (open edges, ids, heights, section areas) | `mesh-reader` |

Rules:
- Only the main agent writes code, commits and decides. No subagent may write to `src/`, `docs/` or `jobs/`,
  and none is created with write tools. Agent Teams are not enabled.
- After every engine run the main agent calls `independent-checker` before it reports "done".
- A subagent's result is data, not a decision. The main agent weighs it, and it asks the user only about the
  model or the object (`questions-only` rule).
- Disputed geometry: look first, then classify (user 2026-10-13 [D072]) - every group of a classifier's verdict, every
  question and every stop is shown isolated on the body (renders, three views, sizes) before a rule or a question.

## Triggers (user 2026-10-14 [D074])

An event makes a skill or subagent mandatory, not optional:

| Event | Mandatory |
|---|---|
| A new or updated source (FBX, Revit, Max, SketchUp, Blender) | skill `analyze-architectural-source` + subagent `source-inspector` |
| A first call to a DCC MCP (3ds Max, Blender, Revit) in the session | skill `3dsmax-mcp-dev` / `blender-mcp` / `revit-mcp` |
| The engine has built a model | subagent `independent-checker` |
| Before "done", a handover of a deliverable or sending it | skill `validate-delivery` |
| "Is there a rule for …?" (pattern, case, conflict) | subagent `pattern-librarian` |
| Benchmarks or the test suite must run | subagent `bench-runner` |
| A numeric question about an FBX or a dump | subagent `mesh-reader` |
| The user accepts a result | skill `experience-transfer` |

Hooks (Claude Code): `tools/hooks/skill_gate.py` (PreToolUse) denies a DCC MCP call in the main session until its
skill is loaded; `tools/hooks/usage_log.py` writes every subagent call, skill load and /command to
`logs/agent-usage.jsonl` (local, main checkout). `/takeover` ends with the 7-day counts, so what is never called
shows up. `py -3 tools/hooks/usage_log.py backfill --days N` fills the log from past transcripts (#109).

## Rule of three (user 2026-10-14 [D075])

A procedure repeated across a session or jobs becomes a reusable thing; what it becomes depends on its kind:

| Repeated | Becomes | When |
|---|---|---|
| Deterministic steps (same commands, same computation) | code: a `src/` module or a `tools/` CLI command | after the second repeat |
| A procedure that needs judgement | a skill (`.agents/skills/`) | after the second repeat |
| A user decision on a modelling question | a pattern (`docs/domain/patterns/`) | at the first decision that recurs |
| One-off work for one object | stays in `jobs/<ID>/` | - |

The agent only proposes: `/handover` writes repeats of the session to `docs/backlog.md` "Reuse proposals";
`/reuse-scan` (weekly) lists cross-job repeats with an effort estimate. Creating the code, skill or pattern is a
task of its own.

## Context rotation (Claude Code, user 2026-10-14 [D076])

A long session loses detail when it is compacted. Rotate instead, in the same worktree:

1. **When:** at a task boundary (PR opened, stage accepted), or when the context reaches about 40-50 % (the
   status line shows `ctx N%`), whichever comes first. Do not wait for auto-compaction. The UserPromptSubmit
   hook `tools/hooks/context_watch.py` measures it (the last response's `usage` in the transcript) and tells the
   agent once per session at 45 % to suggest `/handover` in one sentence, and at 65 % to urge it.
2. **`/handover`** (`.claude/commands/handover.md`): commit, a PR only at a task boundary (merge on the
   user's command), the transcript kept in `logs/transcripts/` (`tools/hooks/save_transcript.py`, its path in the
   handoff), `docs/HANDOFF.md` from `docs/HANDOFF.template.md`, `jobs/<ID>/STATE.md` for a job;
   `PROJECT_STATE.md` only on `main` after a merge. It ends with «Чекпоинт готов, можно /clear».
3. **`/clear`** in the same worktree. The SessionStart hook (`tools/hooks/session_context.py`) puts the branch,
   `git status --short`, the last 5 commits, open PRs and the handoff into the new context, with a warning when
   the handoff is behind HEAD, belongs to another branch or has the old format.
4. **«продолжай»** - the agent names the branch, commit and next step, then does it. **`/takeover`**
   (`.claude/commands/takeover.md`) - the full reconciliation of handoff, git and GitHub, a list of open items and
   a proposal; it waits for «да». The names avoid the built-ins `/checkpoint` (alias of `/rewind`) and
   `/resume` (session picker), and the `handoff` skills.

Compaction: a manual `/compact` with a stale handoff is blocked (`/compact force` passes). An automatic one is
never blocked (that can fail the request); after it the hook tells the agent to run the handover procedure
first. Each compaction is logged to `<git dir>/agr-compactions.log`.

Worktrees and chats: a new worktree only for a new task, from fresh `main`. A second chat in the same repo only
reads, or writes files that do not overlap with the first one's. `docs/HANDOFF.md` describes its own branch: at
a merge to `main` keep `main`'s handoff unless the merged branch's handoff is the one the next session needs.

## Memory map (#120)

Each kind of fact lives in one place; the others point to it.

| Fact | File |
|---|---|
| A dated user decision | `docs/decisions.md` (one line, `D<n>`), the full text where it applies |
| A modelling rule | `docs/domain/patterns/<id>.md` (index `patterns/INDEX.md`); regulation rules `docs/domain/*.md`, `standards/` |
| An accepted result or a lesson | `docs/cases.md` |
| Project state (goal, in production, harness, next step) | `docs/PROJECT_STATE.md` |
| An open question to the user | `jobs/<ID>/questions.md` (object); `docs/domain/conflicts.md` (source conflict); `docs/backlog.md` "Decisions for the user" |
| Run evidence | `jobs/<ID>/runs/` RunRecord (local), `jobs/<ID>/pipeline/` reports, `docs/deliveries/` |
| Object state | `jobs/<ID>/STATE.md` |
| Session state (branch, next step, what waits) | `docs/HANDOFF.md` of the branch |
| Session transcript | `logs/transcripts/` of the main checkout (local), named in the handoff |
| Unsolved work | `docs/backlog.md`, GitHub issues |

A rule question is looked up in the order of `AGENTS.md` ("Where things are"): decision log first.

## Project state (#119)

`docs/PROJECT_STATE.md` is state, not history: at most 80 lines, exactly the sections Goal, In production
(object -> version -> status -> open gates), Harness (what is green), Next step, Links
(`tests/test_project_state.py`). Edit it only on `main` after a merge, by replacing the sections the merge
changed; never append. The only history it keeps is the last PR number and the date on the `Last updated`
line; `git log --merges` and the PRs hold the rest. In a task branch state changes go into the handoff.

## Reports

Keep full arrays, scenes and logs in files. In a report give counts, statuses, up to five
errors and paths to full evidence. `AdapterReport` describes one operation, not readiness
of the whole object.

## Experience capture

When the user accepts a result ("принято", "круто получилось", …) capture it before the
stage ends with the `experience-transfer` skill: exact acceptance scope, inputs/versions and
hashes, code used, checks actually run, failures and fixes, reuse candidates. Add it to
`docs/cases.md`. Praise does not replace QA. A procedure becomes a general tool or skill
only after it works on a second representative object.

## Permission matrix

Single permission policy for all three agents (#127). `free` means read/inspect or local code
work within the task's own worktree; `versioned write` requires task authorization and a new
versioned output; `ask` requires the user's explicit authorization (a task may grant the exact
operation); `never` prohibits the action as described, even if a hook offers an override.
Roles in `ROLES.md` assign work, not extra permissions. More restrictive task policies win.

| Action class | Claude Code | Codex | Antigravity | Enforcement |
|---|---|---|---|---|
| Read files, inspect DCC, local tests, gh pr view / gh issue list | free | free | free | Read-only tools; confirm application/document before DCC calls |
| Edit task code/docs and commit in own worktree | free | free | free | Task scope and NAMING.md; pre-commit checks |
| Authorized DCC saves/exports to new versioned paths | versioned write | versioned write | versioned write | CAPABILITIES.md risk classes; DCC skill and output readback |
| Publish branch (git push) | ask | ask | ask | guard: `git push origin task/example` |
| Merge after review on the user's explicit command | ask | ask | ask | guard: `gh pr merge 127`; gate: [Merge authorization](WORKFLOW.md#gate-merge-authorization) |
| gh delete operations (issue, release, etc.) | ask | ask | ask | guard: `gh issue delete 127`; guard: `gh release delete v1` |
| All gh repo operations (including reads) | ask | ask | ask | guard: `gh repo view owner/repo`; guard: `gh repo delete owner/repo` |
| Destructive DCC tools or arbitrary DCC code | ask | ask | ask | gate: [DCC authorization](WORKFLOW.md#gate-dcc-authorization) |
| Install software or change machine settings | ask | ask | ask | guard: `winget install example`; guard: `setx EXAMPLE value` |
| Discard local work / recursive cleanup / rewrite history | ask | ask | ask | guard: `git reset --hard`; guard: `git clean -fd`; guard: `git rebase main` |
| Delete sources or accepted versions | never | never | never | gate: [Asset preservation](WORKFLOW.md#gate-asset-preservation) |
| Write over data/sources | never | never | never | gate: [Asset preservation](WORKFLOW.md#gate-asset-preservation) |
| Merge without the user's command (git or gh) | never | never | never | gate: [Merge authorization](WORKFLOW.md#gate-merge-authorization) |
| Change standards/ outside its procedure | never | never | never | gate: [Standards procedure](WORKFLOW.md#gate-standards-procedure) |
| Force push | never | never | never | guard: `git push --force origin task/example`; gate: [Publication review](WORKFLOW.md#gate-publication-review) |
| Write into another agent's worktree | never | never | never | gate: [Worktree ownership](WORKFLOW.md#gate-worktree-ownership) |
| Manual /compact over a stale handoff without force | never | never | never | gate: [PreCompact](../../tools/hooks/session_context.py#precompact) |

The guard (`.claude/hooks/guard.py`) asks; it is not a deny sandbox or an authorization
ledger. Its lexical shell rules can over-ask and do not interpret aliases, `gh api`, embedded
scripts or arbitrary MCP code. A guard confirmation cannot waive a `never` row. Named manual
gates below cover these semantic cases before execution and at review; do not claim they are
automatic enforcement. Claude Code hooks are working; Codex/Antigravity runtime enforcement
remains unvalidated (H1 in `CAPABILITIES.md`). The same policy applies even without hooks.
The PreCompact gate is Claude Code only; elsewhere follow the context-rotation procedure.
Automatic compaction and `/compact force` retain the exceptions in Context rotation.
`tests/test_guard_permissions.py` parses this table, exercises named shell probes and checks
that every restricted row resolves to a guard rule or an existing gate.

### Gate asset preservation

Manual pre-write gate, owned by the executing agent and checked by the reviewer: resolve
all target paths and sidecars; compare them with sources and user-accepted versions in the
job state. Reject deletion of either, and any write into `data/sources/`. Work from copies
and choose a new versioned destination; a save permission does not authorize an overwrite.
The guard's production-extension/delete checks only supplement this gate.

### Gate merge authorization

Manual pre-execution gate: require review and the user's command naming the merge. A task
approval to code, push or open a PR is not a merge command. Applies equally to `git merge`,
`gh pr merge`, UI and API routes. Without it stop; the gh guard prompt is not evidence that
the command was granted. Record the command in the handoff/PR when a merge is authorized.

### Gate standards procedure

Manual review gate: apply `standards/README.md`, "Changing a rule" (rule and traceability,
domain rationale/user conflict decision, updated hash lock). The profiles loader verifies
hashes, but a new hash alone does not prove that the procedure was followed. Reject a PR
that changes standards without this evidence.

### Gate publication review

Manual pre-push gate: inspect the exact destination/refspec and flags. Reject force pushes
(including `-f`, `--force-with-lease` and `+refspec`) regardless of the guard's confirmation.
For allowed publication record the user's task authorization and use a normal branch push.

### Gate worktree ownership

Manual pre-write gate: inspect `git worktree list`, current branch/status, resolved targets
and task ownership. Only the task's owner writes its worktree. Another agent may inspect it
read-only; never edit there via an absolute path, shell, script, MCP or symlink. The guard's
file boundary check is a supplementary ask, not proof of ownership.

### Gate DCC authorization

Before any mutation name the exact tool/operation and its risk class from
`CAPABILITIES.md#dcc-tool-risk-classes`. Require the user's task authorization for a
`versioned-write`; for `destructive` require explicit authorization for that exact mutation,
confirmed document/units/version and a preserved source copy. Apply Asset preservation and
Worktree ownership first; reject prohibited operations even with authorization. Save/export
to new versioned paths and read back geometry, UV, materials and transforms. Unknown or
arbitrary-code operations are destructive until their behavior is inspected. This is a
manual DCC skill/reviewer gate, not a generic MCP sandbox.

## Git

- Start independent work from fresh `main` in a new worktree; continue a task in its own
  worktree. Check existing worktrees, branch, base/head and dirty state before choosing.
- Commit successes and useful failed attempts with an honest status message.
- Permissions for publication, merge, deletion and history are defined only in the
  [Permission matrix](#permission-matrix); apply its named gates before executing.
- Remove a worktree only after its ignored outputs that matter are saved.
