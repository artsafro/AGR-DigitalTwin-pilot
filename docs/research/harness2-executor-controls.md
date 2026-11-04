# Executor-arm controls (superseding companion)

This note is proposal-precision only. It is docs-only. No experiment was run. There is no rollout. It is not scheduled. It is not adoption. Nothing was measured. No pytest/RED/GREEN counts exist.

It is an explicitly superseding companion to the "Executor arm specification" subsection in PR #737 at commit `c190e4429a894f745575a865623fd54e7bcf6f16` (`docs/research/harness2-vs-board.md` on that commit). It cites issue #738 and review comment https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/737#issuecomment-6577111379. It does not open another issue. It does not edit `docs/research/harness2-vs-board.md`.

Where this note and that subsection disagree, this note wins for three points only: the positive control, the isolation scope (competing arms versus candidate 3 carryover), and the executor invocation / harness-loading config. The rest of PR #737 is left as written.

The proposal is **unschedulable** until the capability gap in "Supported invocation" is closed. No arm command is frozen below, because no verified flag loads a copied worktree harness in isolation.

## Why the PR #737 positive control does not show executor behavior

On `c190e442`, the positive control is: one arm's harness requires an observable marker (a named line or file name), and the marker must appear in that arm's trajectory or deliverable. A transcript that still contains the input instruction already contains that marker when the instruction says `create marker.txt`, even if the executor ignores the instruction. That accepts a substring of the prompt. It does not establish that the executor changed an observable output. Issue #738 and the review comment require a generated-output-only control.

The same subsection says every arm starts with no other arm's files or transcript. Candidate 3 on that commit pastes the step-1 log into the step-2 prompt. This note scopes isolation to competing arms and allows only the predeclared step-1 evidence bundle below.

The same subsection says "Invoke the worker" for a copied SOUL/skill under the card worktree. This note freezes only the invocation that was actually verified, and records a capability gap where it was not.

## Generated-output-only positive control

Predeclared marker artifact, relative to the arm's fresh checkout:

- Path: `out/harness2-executor-marker.txt`
- Exact frozen bytes (UTF-8, one trailing LF, no CR): `HARNESS2-EXECUTOR-MARKER-v1` plus `0x0a`
- Byte length: 28
- frozen-bytes-hex: 4841524e455353322d4558454355544f522d4d41524b45522d76310a
- frozen-sha256: 61ecb5d4bb60b67c62a0ce47f96c217fc5fc072c6ae6264a890e5ffe02c789f7

The frozen bytes are not the string `create marker.txt`. The initial checkout must not contain the path. This companion does not add that file to the repo. Verification reads the executor's files. Transcript text is never evidence. A marker string inside the prompt, the query file, or the trajectory does not pass.

Verification, in order. Stop at the first failure.

1. **Initial-absent check.** Before the executor process starts, resolve `out/harness2-executor-marker.txt` in that arm's checkout. If the path exists, the control is invalid (preexisting marker). Do not delete it and continue.
2. **Post-run exists.** After the executor process has exited, the same path must exist as a regular file in the tree the executor wrote. If it is missing, the control is invalid (missing output). Do not consult the transcript.
3. **Exact bytes.** Read the file as bytes. Accept only when the length is 28 and the bytes equal the frozen bytes (sha256 `61ecb5d4bb60b67c62a0ce47f96c217fc5fc072c6ae6264a890e5ffe02c789f7`). A shorter file, a proper prefix, or any other extra or replaced byte is invalid (partial output or wrong bytes).
4. **Created by the executor run, not copied from prompt.** The pass in step 3 is a new file that was absent in step 1. It is not a copy of prompt text sitting in the transcript. If the path is still absent and the transcript or prompt contains `create marker.txt` or the frozen bytes, the control is invalid. If the new file's bytes are a byte copy of the query file or of the prompt text rather than the frozen bytes, step 3 already fails. Transcript text is never evidence.

The negative witness is an ignored-instruction transcript: the prompt says `create marker.txt`, the transcript may contain that phrase, and the executor produces no marker file and no other marker action. That witness must not validate harness loading.

The positive witness is the marker path absent at the start and present after the run with the frozen bytes, written by the executor. The judge does not decide this control. The file check does.

## Acceptance

| Input | Expected output |
|---|---|
| prompt says create marker.txt but executor ignores it | control invalid |
| marker absent initially and newly created with exact frozen bytes by executor | control valid |
| preexisting marker | invalid |
| marker text only copied from prompt | invalid |
| missing output | invalid |
| partial output | invalid |
| wrong bytes | invalid |
| competing arm transcript supplied to an arm | isolation violation |
| step-2 receives ONLY the predeclared step-1 evidence bundle | permitted carryover |

`control invalid` covers the ignored-instruction row. The later `invalid` rows are the same rejection for absent, partial, copied, preexisting, or wrong-byte executor output. An isolation failure is not reported as a valid control.

## Isolation

Isolation applies to competing arms. Competing arms are the reference arm, the invariant-edit arm, the domain-edit arm, the no-op repeats, and the positive-control arm. None of them receives another competing arm's transcript, deliverable, marker file, or worktree files.

Candidate 3 is sequential, not a competing arm of step 1. Step 2 may receive only the predeclared step-1 evidence bundle. It may not receive the step-1 transcript, the step-1 log pasted into the prompt, or any competing arm's output.

### Predeclared step-1 evidence bundle

Allowed contents, and nothing else:

1. `step1-evidence/decision.txt` — one line, either `kept_base` or `composed:invariant` or `composed:domain`.
2. `step1-evidence/judge-exit.txt` — exit code and pre-registered metric lines written by the judge runner after the executor exited.
3. `step1-evidence/harness-manifest.txt` — relative paths and sha256 of the harness files step 2 is allowed to load. The file bodies are not pasted into the step-2 prompt.

Not allowed in the bundle: executor trajectory, prompt text, the marker file, other arms' files, or a copy of the step-1 log. Supplying any of those is an isolation violation. Receiving only the three files above is permitted carryover.

## Executor and judge

The executor and the judge are separate processes.

- The executor never runs the judge. Its process is the worker invocation. It may write the checkout, including the marker file. It does not score the pre-registered metric.
- After that process exits, one judge command runs on that arm's deliverable. The judge command string is fixed before the batch and is the same for every arm, including no-op repeats and the positive-control arm.
- The marker check is not the judge. It is the four-step file check above. A void marker control stops the batch. It is not a metric score.
- This note does not name the judge command string. Issue #738 does not supply one, and inventing a test or benchmark command would be a fictional invocation. The separation rule is frozen. The command text is part of the unschedulable gap until a real pre-registered command is named without being run here.

## Supported invocation

Evidence read for this note:

- `C:/x/t_b4a6a48f/cli-help.txt`, captured read-only: `hermes --version`, `hermes --help`, `hermes chat --help`, `hermes -z --help` (errors: `-z/--oneshot` expects an argument), `hermes profile --help`, `cursor-agent.cmd --version`, `claude --version`.
- Installed Hermes source and docs at `C:\Users\artsafro\.hermes\hermes-agent`, the tree reported by `hermes --version`.
- Live site https://hermes-agent.nousresearch.com/docs was not checked.

### Version

`hermes --version` in `cli-help.txt`: Hermes Agent v0.22.1+1.g5575a08 (2026.9.24), stable, local `5575a0859d62`. Install directory `C:\Users\artsafro\.hermes\hermes-agent`. Python 3.14.7.

`cursor-agent.cmd --version`: `2026.10.22-27dcf5f`. `claude --version`: `2.1.301 (Claude Code)`. Neither help text was captured. No flag on either tool was verified as a loader for a copied Hermes `SOUL.md` or skill. No command template is given for them.

### Verified CLI flags

These tokens appear in `cli-help.txt`. They are the flags this note treats as verified. Each one was read from that capture. None of them was executed against a model.

- `--skills`
- `-s`
- `--ignore-user-config`
- `--ignore-rules`
- `--in`
- `--query-file`
- `--oneshot`
- `--quiet`
- `-q`
- `-Q`

What those flags do, from that help text plus the installed v0.22.1 source (not from a rollout):

- `hermes chat -q/--query` and `--query-file` pass the prompt. `--oneshot` and non-TTY stdio answer and exit. `-Q` / `--quiet` suppresses the banner. That starts a chat. It does not select a harness file.
- `--in DIR` changes directory before the session (`hermes chat --help`). Project context discovered from the working directory is `.hermes.md` / `HERMES.md`, `AGENTS.md`, `CLAUDE.md`, and `.cursorrules`, one type (`agent/prompt_builder.py`, `build_context_files_prompt`). `SOUL.md` is not in that set.
- `SOUL.md` loads only from `HERMES_HOME/SOUL.md` (`load_soul_md` in `agent/prompt_builder.py`; installed doc `website/docs/user-guide/features/context-files.md`: "SOUL.md is now global to the Hermes instance and is loaded from HERMES_HOME only"). A `SOUL.md` copied under the card worktree is not that file.
- `--skills` / `-s` preloads skills by name (`hermes chat --help`: "Preload one or more skills for the session"). `tools/skills_tool.py` `_skill_lookup_path_error` rejects absolute paths, including a Windows drive path. The lookup hint is "Use a skill name or relative path within the skills directory." A `SKILL.md` that exists only under the card worktree, and not under the active skills directory, is not addressed by this flag.
- `--ignore-rules` is documented in `hermes chat --help` and in installed `website/docs/reference/cli-commands.md` as skipping auto-injection of `AGENTS.md`, `SOUL.md`, `.cursorrules`, memory, and preloaded skills. `hermes_cli/main.py` sets `HERMES_IGNORE_RULES` and the agent is built with `skip_context_files` (`hermes_cli/cli_agent_setup_mixin.py`). In `cli.py` (`_build_cli_from_args`), `--ignore-rules` skips `skills.auto_load` and still calls `build_preloaded_skills_prompt` for an explicit `-s` list. Those explicit names still resolve inside the skills directory, not as an arbitrary worktree `SOUL.md`. The flag turns SOUL injection off. It does not point SOUL at a copy.
- `--ignore-user-config` ignores `~/.hermes/config.yaml` and falls back to built-in defaults (help text). It does not take a SOUL path or a skill path.
- Project skill directories (`.hermes/skills` and `.agents/skills` under the git root) load only when that root is in `skills.trusted_project_dirs` (`agent/skill_utils.py`, comment above `PROJECT_SKILLS_SUBDIRS`). Trust is user config on the active Hermes home. Adding a card worktree there would edit deployed config. `--ignore-user-config` drops that config, so it does not become a per-arm trust switch. This note did not read `config.yaml`.

`hermes profile --help` lists `list`, `use`, `create`, `delete`, `install`, and `update`. `create`, `use`, `install`, and `update` write the profile store. `hermes_cli/profiles.py` `resolve_profile_env` maps a name to `<root>/profiles/<name>`, which is a deployed profile home. That is not a card-worktree copy. This note does not use those subcommands.

`hermes_cli/main.py` `_apply_profile_override` also scans `--profile` and `-p` and then strips them before argparse, which is why they are absent from the captured `hermes --help`. They are not listed as verified flags. When a sticky `active_profile` is not `default`, that function overwrites `HERMES_HOME` unless the environment value's parent directory is named `profiles` or an explicit profile flag selected a named profile. `ensure_hermes_home` in `hermes_cli/config.py` creates `cron`, `sessions`, `logs`, `memories`, `skills`, and other skeleton directories inside the resolved home before `load_soul_md` reads `SOUL.md`. Pointing `HERMES_HOME` at the card worktree would mutate that worktree and is still subject to the sticky-profile overwrite. This note did not launch Hermes to observe that overwrite, and it does not treat `HERMES_HOME` as a verified isolated loader for a worktree copy.

### Capability gap

A per-arm copied harness (a copied `SOUL.md` or skill text under the card worktree) cannot be loaded in isolation with a verified flag or config. Verified `--skills`, `--in`, `--ignore-user-config`, and `--ignore-rules` do not do that. Profile create/use/install would touch deployed profiles, which this clarification must not do. `HERMES_HOME` was not verified as a worktree-copy loader.

Until that gap is closed, the proposal is unschedulable. No baseline, candidate, no-op, or positive-control command is stated.

### Arm command templates

- Baseline: capability gap
- Candidate: capability gap
- No-op: capability gap
- Positive control: capability gap

## Boundaries

Docs-only. Unmeasured. No rollout. No scheduling. Not adoption. No experiment run. No pytest/RED/GREEN counts exist. No Harness2 install. No profile was created or edited. No model or worker was launched.

This file is an independent companion. It avoids overlap with PR #737: it does not restate the paper tables, the board mapping, or the three candidate effect sizes. It supersedes only the marker control, the competing-arm isolation scope, the candidate 3 carryover, and the worker-invocation line in the executor-arm subsection at `c190e442`. `docs/research/harness2-vs-board.md` on this branch is unchanged.
