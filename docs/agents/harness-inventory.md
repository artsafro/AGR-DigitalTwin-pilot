# Harness inventory

Single owner of the harness components: every hook, permission list, guard rule set, command, subagent and git
hook, with the failure it prevents, its evidence and status, and the rules for re-examining them. Tool and MCP
route status: `docs/agents/CAPABILITIES.md`. The behaviour rules these components enforce (task loop, triggers,
subagents, context rotation, permission matrix): `docs/agents/WORKFLOW.md`.

## Re-examination rules (#129)

"Components" below lists every hook, permission list, guard rule set, command, subagent and git hook with the
failure it prevents, the evidence that the failure happened, the date it was last verified and the eval that
covers it (`tests/test_harness_inventory.py`).

- Re-examine the whole inventory at a model change (a new model or a new major version of the agent app), and the
  new row when a component is added: its row lands in the same PR as the component. Not on a calendar; the weekly
  run belongs to the capability evals.
- At a re-examination: refresh "Last verified" from a live run or the component's tests, and check whether the
  failure still happens with the new model (the covering eval, the usage log).
- A component with no evidence and no eval is proposed to the user for removal in the PR or the handoff; it is
  removed only on the user's word.
- Re-measure the rule-layer size ("Rule-layer size" below, same command) at a model change. Retrieval
  tooling (an index, a vector store) is reconsidered only when the size passes the 200k-token threshold.

## Components (#129)

One row per component (#129): every hook command in `.claude/settings.json` and in the subagents' frontmatter, every
permission list, guard rule set, command, subagent and git hook. **Evidence** is a case, PR or issue where the failure
really happened; `none` = a precaution only (the decision that made it is named). **Last verified** = the last date it
was seen working: `live` (a real session, named) or `pytest` (its suite green on that date). **Eval** = tasks under
`evals/` that would catch the stated failure, or `none`; for protection rows, a task must test the component's
rejection behavior to count. Indirect procedural signals are listed separately below, not as covering evals.
Rules for re-examining it: "Re-examination rules" above. `tests/test_harness_inventory.py` fails when a hook, command, subagent or git hook has no row
or an eval id is no task.

| Component | Kind | Failure it prevents | Evidence it happened | Last verified | Eval |
|---|---|---|---|---|---|
| `.claude/hooks/guard.py` | PreToolUse hook via `pretool.py` (Bash, PowerShell, Write, Edit, NotebookEdit), "ask" | a destructive, outward or asset-corrupting action without the user's word | PR #142: the app isolation hook refused a Write into another worktree (real handover transcript); not component-specific evidence for project guard | never (project-guard verification unknown; component-specific run required) | none |
| `.pi/extensions/agr-guard.ts` + `tools/hooks/pi_guard_adapter.py` | Pi `tool_call` bridge (bash, powershell, write, edit), fail closed | Pi skips Claude hooks; headless ask/deny and hook failures must block | #58: Windows third-party hook adapter passed an unexpanded project path | 2026-10-15 live via `pi-run.sh` + nested smoke driver (`tests/fixtures/pi_guard_smoke.ts`): status allowed, reset blocked; pytest `tests/test_pi_guard_adapter.py` + `tests/test_pi_guard_contract.py` (installed-Pi parity); exact `edits[]` preview; special Pi paths and fuzzy-only edits block (use native/relative paths and exact text); opt in with `PI_EXTENSIONS=.pi/extensions/agr-guard.ts`, wrapper wiring deferred | none |
| guard rule set `SHELL_RULES` | guard rule set | push, `reset --hard`, `clean`, forced branch delete, discarded changes, history rewrite, LFS migrate, deletes of sources or production assets, recursive delete, installs, system changes | none (precaution, carried over from DigitalTwinProject) | never (no test) | none |
| guard rule set `PRODUCTION_EXT` | guard rule set (Write, Edit) | a text write over a production asset (`.fbx`, `.max`, `.blend`, `.png`, ...) | none (precaution) | never (no test) | none |
| guard rule set `ALLOWED_WRITE_ROOTS` | guard rule set (Write, Edit) | a write outside the project and the allowed folders, e.g. into another worktree | PR #142: the app isolation hook refused the foreign-worktree Write; not component-specific evidence for this rule set | never (rule-set verification unknown; component-specific run required) | none |
| `permissions.allow` | `.claude/settings.json` list | a routine read-only git, test or `dt` call stops the session for a confirmation | none (convenience) | never (no test) | none |
| `permissions.ask` | `.claude/settings.json` list | push, `reset --hard`, `clean`, `branch -D` without the user's word (duplicates `SHELL_RULES`) | none (precaution) | never (no test) | none |
| `permissions.deny` | `.claude/settings.json` list | secrets in `.env` read into the context | none (precaution) | never (no test) | none |
| `.claude/hooks/pipeline_gate.py` | PreToolUse hook via `pretool.py` (Bash, PowerShell, Write, Edit), deny | a job status above draft without spec, extractor report and checker report; a job script without an engine gap | case alina-bld (`docs/cases.md`): no spec, no checker report, build script left only as `.pyc` | 2026-10-15 pytest (`tests/test_pipeline_gate.py`) | none |
| `.claude/hooks/pretool.py` | PreToolUse dispatcher (Bash, PowerShell, Write, Edit, NotebookEdit): runs guard and pipeline gate in one process, one output (deny > ask > none) | a decision of one part lost or doubled; two interpreter starts per tool call | none (performance; repo hygiene phase 4) | 2026-11-05 pytest (`tests/test_hook_dispatchers.py`) | none |
| `tools/hooks/skill_gate.py` | PreToolUse hook (DCC MCP), deny | a 3ds Max / Blender / Revit MCP call before its skill is loaded | none (precaution, [D074], PR #107) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `tools/hooks/session_context.py start` | SessionStart hook | a session after `/clear` or compaction starts without branch, state and handoff, or on a stale / foreign handoff | none (precaution, [D076], PR #107) | 2026-10-15 pytest (`tests/test_session_context.py`); live 2026-10-14 in `claude -p` | none |
| `tools/hooks/session_context.py precompact` | PreCompact hook | a manual `/compact` over a stale handoff loses the session state | none (precaution, [D076]) | 2026-10-15 pytest (`tests/test_session_context.py`) | none |
| `tools/hooks/prompt_hooks.py` | UserPromptSubmit dispatcher: runs `context_watch.py`, `usage_log.py prompt` and the acceptance nudge in one process, prints their notes | a part's failure hiding the other; two interpreter starts per prompt; an accepted result with no `experience-transfer` | #1036: experience-transfer skipped after ~10 acceptances on 2026-11-04/05 | 2026-11-05 pytest (`tests/test_hook_dispatchers.py`) | none |
| `tools/retro/condense_transcript.py` | script of `/retro` | a retro reads megabytes of tool output, or each agent rewrites its own condenser | #1039: five agents wrote five condensers on 2026-11-05 | 2026-11-05 pytest (`tests/test_condense_transcript.py`) | none |
| `.claude/commands/retro.md` | command `/retro`; step 7a of `/handover` | the user's corrections are never recorded and repeat in the next session | #1039; `docs/retros/2026-11-05-sessions-retro-04-05.md` | never as a command; the 2026-11-05 retro followed its steps by hand | none |
| `tools/hooks/context_watch.py` | UserPromptSubmit hook via `prompt_hooks.py` | the session runs into auto-compaction without a handover (45 % / 65 % notes) | none (precaution, [D076]) | 2026-10-15 pytest (`tests/test_context_watch.py`) | none |
| `tools/hooks/usage_log.py prompt` | UserPromptSubmit hook via `prompt_hooks.py` | an unused `/command` stays invisible (no 7-day counts at `/takeover`) | none (precaution, [D074]) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `tools/hooks/usage_log.py post` | PostToolUse hook (Agent, Task, Skill) | an unused subagent or skill stays invisible; the usage-log evidence for evals | none (precaution, [D074]) | 2026-10-15 pytest (`tests/test_usage_hooks.py`) | none |
| `.claude/hooks/subagents.py start` | SubagentStart hook | a subagent forgets it is read-only; no `git status` snapshot for the stop check | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py stop` | SubagentStop hook | tracked files changed by a subagent go unnamed; `independent-checker` ends without a verdict table | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py guard` | PreToolUse hook in all five subagents, deny | a plain Bash write from a read-only subagent | none (precaution, [D071]) | 2026-10-15 pytest (`tests/test_subagents.py`) | none |
| `.claude/hooks/subagents.py deny-geometry` | PreToolUse hook in `independent-checker`, deny | the checker reads how the model was built and confirms it instead of checking | #117: the engine's own "11/11 checks passed" on a wrong model | 2026-10-15 pytest (`tests/test_subagents.py`); live 2026-10-13 (PR #86) | none |
| `tools/hooks/save_transcript.py` | script of `/handover` | the session transcript is lost at `/clear`, so evals have no evidence | #121 (no transcripts kept before it) | 2026-10-15 live (PR #140, by nonce); pytest (`tests/test_save_transcript.py`) | none |
| `.claude/commands/handover.md` | command `/handover` | session state lost at a context rotation | none (precaution, [D076]) | 2026-10-14 live in `claude -p` (PR #107) | none |
| `.claude/commands/takeover.md` | command `/takeover` | a new session starts from a handoff that disagrees with git and GitHub | none (precaution, [D076]) | 2026-10-14 live in `claude -p` (PR #107) | none |
| `.claude/commands/reuse-scan.md` | command `/reuse-scan` | repeated procedures never become code, a skill or a pattern | none (precaution, [D075]) | 2026-10-15 pytest of `tools/reuse_candidates.py` (`tests/test_usage_hooks.py`) | none |
| `.claude/agents/source-inspector.md` | subagent, read only | work on an uninspected source (scale, levels, dropped parts); a scene dump in the main context | none recorded | 2026-10-13 live (PR #86, B01 `etalon.max`) | `source-inspected` |
| `.claude/agents/pattern-librarian.md` | subagent, read only | a rule question asked again or a new rule invented where one exists | none recorded | 2026-10-13 live (PR #86) | `routine-question` |
| `.claude/agents/bench-runner.md` | subagent, read only | raw benchmark and test logs in the main context | none (precaution, [D071]) | 2026-10-13 live (PR #86, B01 9/9) | none |
| `.claude/agents/independent-checker.md` | subagent, read only | "done" reported from the engine's own output | #117 | 2026-10-13 live (PR #86, B01 model) | `engine-checked` |
| `.claude/agents/mesh-reader.md` | subagent, read only | a mesh dump read into the main context | none (precaution, [D071]) | never (not test-called) | none |
| `tools/git-hooks/pre-commit` | git pre-commit (every agent) | a commit that skips linking or the pipeline gate; fail-open when the root or the gate is missing | case alina-bld (the gate it runs); fail-open versions were found in review of PR #79, not in use | 2026-10-13 live (manual blocked commit) | none |
| `tools/git-hooks/link_large_files.py` | git pre-commit step | a new file over 50 MB committed into history | none recorded | 2026-10-06 live (60 MB file) | none |
| `tools/git-hooks/pipeline_gate.py` | git pre-commit step, delivery gate | as `.claude/hooks/pipeline_gate.py`, for every agent; a commit on an auto-named branch; a `.pyc` without its `.py` at delivery | case alina-bld | 2026-10-15 pytest (`tests/test_pipeline_gate.py`) | `branch-name` |
| `tools/git-hooks/branch_names.py` | rule module of the gate and the SessionStart hook | a commit on an auto-generated worktree branch | `claude/npm-models-school-kpp-ec9ced` (`evals/branch-name/task.md`), [D078] | 2026-10-15 pytest (`tests/test_branch_names.py`) | `branch-name` |

**Indirect procedural signals** (not component behavior coverage):
- `no-hook-denial`: `.claude/hooks/guard.py`, `SHELL_RULES`, `PRODUCTION_EXT`, `ALLOWED_WRITE_ROOTS`,
  `permissions.ask`, `tools/hooks/skill_gate.py`, `.claude/hooks/subagents.py guard`,
  `.claude/hooks/subagents.py deny-geometry`. It detects agent attempts refused by hooks, not whether
  unauthorized actions are rejected. Its [task definition](../../evals/no-hook-denial/task.md) excludes
  accepted calls and non-blocking hook failures: a fail-open guard can pass.
- `dcc-skill-loaded`: `tools/hooks/skill_gate.py`; checks skill ordering in the transcript, not the gate's
  rejection behavior. See its [task definition](../../evals/dcc-skill-loaded/task.md).

These mappings must not be used alone as proof that a protection is tested in removal decisions.
`Eval = none` records missing behavior-specific eval coverage, not absence of the dated pytest runs above.
No guard deletion is authorized; hooks, permissions and rule sets remain unchanged. The candidates below
are not expanded by this coverage correction; re-examination requires component-specific evidence and user approval.

Removal candidates by the rule (no evidence, no eval): `permissions.allow`, `permissions.deny`, the hooks
`session_context.py`, `context_watch.py`, `usage_log.py`, `subagents.py start` / `stop`, the three commands,
`bench-runner`, `mesh-reader`, `link_large_files.py`. They are proposed to the user, not removed.

## Rule-layer size

- Measured 2026-10-15 at commit 32813c6: **141k tokens** (564 970 characters / 4; an estimate, not a tokenizer
  count). Scope as in the spec: Markdown, YAML and JSON at the root (top level only), `docs/agents`, `docs/domain`,
  `docs/adr`, `.agents/skills`, `standards/` and the plan / state files (`PROJECT_STATE`, `backlog`, `cases`, `pipeline`,
  `HANDOFF`, `decisions`; in 2026-10-15 also `archive/2026-11:docs/HARNESS_PLAN.md` (historical), now out of the tree).
  Out of it: `docs/agr`, `jobs`, `technical_library`.
- Command (Git Bash, from the repository root; divide by four):
  `{ find . -maxdepth 1 -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' \); find docs/agents docs/domain docs/adr .agents/skills standards -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.json' \); ls docs/PROJECT_STATE.md docs/backlog.md docs/cases.md docs/pipeline.md docs/HANDOFF.md docs/decisions.md; } | tr '\n' '\0' | xargs -0 cat | wc -c`
- Threshold: **200k tokens**. Below it the agent loads the relevant file whole; no semantic index, no vector store,
  no BM25. Retrieval tooling is reconsidered only when a measurement passes 200k.

## Guard hook status — `.claude/hooks/guard.py`

- Claude Code: CONFIGURED (PreToolUse in `.claude/settings.json`, run in-process by `.claude/hooks/pretool.py`); project-guard live verification
  unknown. PR #142's foreign-worktree Write was refused by the app isolation hook, not proven to be
  refused by this project hook. A component-specific run is required; the hook and rules remain enabled.
- Antigravity: CONFIGURED (`.agents/hooks.json` → `guard.cmd`; Antigravity-side run not validated).
- Codex: CONFIGURED (`.codex/hooks.json`; payload and "ask" support not validated — backlog H1).

## Context rotation hooks (Claude Code, PR #107)

Behaviour rule: `docs/agents/WORKFLOW.md`, "Context rotation"; triggers: same file, "Triggers".
- Status: WORKING (2026-10-14, live in `claude -p`; desktop and interactive CLI not checked).
- `tools/hooks/session_context.py`: SessionStart (`startup|clear|compact`) passes branch, status, last commits,
  open PRs and `docs/HANDOFF.md` (warnings when stale / foreign / old format); PreCompact blocks a manual
  `/compact` with a stale handoff (`/compact force` passes), logs auto ones to `<git dir>/agr-compactions.log`.
- `tools/hooks/context_watch.py`: UserPromptSubmit (with `usage_log.py prompt`, one process: `tools/hooks/prompt_hooks.py`), context share from the transcript's last `usage`; tells the
  agent once per session at 45 % and 65 %. Context % on screen: the user-level status line (`ctx N%`).
- `tools/hooks/skill_gate.py`: PreToolUse on DCC MCP tools (3ds Max, Blender, Revit) denies the call in the
  main session until `3dsmax-mcp-dev` / `blender-mcp` / `revit-mcp` is loaded.
- `tools/hooks/usage_log.py`: PostToolUse on Agent / Skill and UserPromptSubmit `/commands` ->
  `logs/agent-usage.jsonl` in the main checkout (git-ignored); `stats --days N`; `backfill --days N` (#109) adds
  past usage from the transcripts of this repository and its registered worktrees (idempotent; skips calls the hooks logged).
- `tools/hooks/save_transcript.py` (#121): `/handover` copies the session transcript to `logs/transcripts/
  <branch>-pr<N>-<session>.jsonl` in the main checkout (git-ignored), never over an existing copy; the handoff's
  `Transcript:` line names it and `session_context.py` prints it. The session is proven by a nonce: the agent's Bash call
  is in its own transcript before it runs, so the one transcript holding the nonce is the caller's; never file times.
  Status: WORKING (2026-10-15, PR #140): found the live desktop session by its nonce; not yet run inside a real
  /handover.
- Commands: `/handover`, `/takeover` (ends with 7-day usage), `/reuse-scan` (+ `tools/reuse_candidates.py`).
- Tests: `tests/test_session_context.py`, `tests/test_context_watch.py`, `tests/test_usage_hooks.py`, `tests/test_hook_dispatchers.py`,
  `tests/test_save_transcript.py`.
- Agent trace (#124): `/handover` generates the `## Agent trace` block with `tools/hooks/agent_trace.py` from the
  usage log and the transcript, and writes it into the handoff and the PR body. Fixed fields: Sessions, Written by,
  Subagents, Skills, Commands, Hook denials, Retries, Context at handover, Duration, Commits. Never written by hand.
- `tools/hooks/skill_gate.py` and `tools/hooks/usage_log.py` enforce and log the triggers of
  `docs/agents/WORKFLOW.md`, "Triggers": `/takeover` ends with the 7-day counts, so what is never called shows up;
  `py -3 tools/hooks/usage_log.py backfill --days N` fills the log from past transcripts (#109).

## Subagents — `.claude/agents/` (Claude Code, read only)

When to call each one: `docs/agents/WORKFLOW.md`, "Subagents" and "Triggers".
Hooks: `.claude/hooks/subagents.py` (SubagentStart reminder and a `git status` snapshot for all five;
SubagentStop blocks until changed tracked files are named, and for `independent-checker` without a verdict table;
PreToolUse `guard` denies plain Bash writes in all five, `deny-geometry` denies `src/dt_ai/geometry/` to the
checker). Note: the desktop app did not load project subagents from this worktree; `claude -p` in it did. Tests: `tests/test_subagents.py`.
- `source-inspector` — VERIFIED (2026-10-13, PR #86): B01 `etalon.max` inventory, 4 objects (B01_ETALON + 3 LEVEL_), read from the file header without opening it over another scene.
- `pattern-librarian` — VERIFIED (2026-10-13, PR #86): "plane flush with the facade" -> C24 / `opening-plane` (and OD1); tools Read, Grep, Glob only.
- `bench-runner` — VERIFIED (2026-10-13, PR #86): B01 9/9 etalon self and model, a per-check table, the spec diff.
- `independent-checker` — VERIFIED (2026-10-13, PR #86): B01 model, a check / expected / measured / pass-fail table; reading `src/dt_ai/geometry/` denied by its hook.
- `mesh-reader` — CONFIGURED (PR #86); not yet test-called.

## Pipeline gate

- Status: WORKING (2026-10-13): installed in `.git/hooks/pre-commit` on this machine (#79 version); a commit
  of `Pipeline status: built` without `pipeline/` is blocked (manual test).
- `tools/git-hooks/pipeline_gate.py --staged` (pre-commit, every agent) and `--job jobs/<JOB>` (delivery):
  `Pipeline status` above draft needs `pipeline/spec.json` + `spec.report.json` + `check.json`; new job
  scripts name an engine gap `EG<n>`; delivery needs a committed `.py` for every `.pyc`;
  attempts limit (pipeline/state.json, #128) (historical `archive/2026-11:docs/HARNESS_PLAN.md` §16; current rule: `docs/agents/WORKFLOW.md`). Claude Code also blocks such writes at PreToolUse
  (`.claude/hooks/pipeline_gate.py`, permission "deny"), and runs of a locked job (Bash/PowerShell runner
  commands; `dt` itself refuses with exit 2). Run interception is partial (known bypasses: #144); the
  guaranteed part is the write/status/commit gate.
- Limit (user 2026-10-12 [D064], #79): a compromised environment is not covered, for example a fake `py` on PATH.
