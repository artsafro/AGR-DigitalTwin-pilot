# Capability A: B01 from the repository alone

Status: WIP, blocked on repository-only context isolation. OS sandbox is explicitly
waived by the user for this eval; host user skills are still being loaded. No accepted
repository-only reference or threshold exists. Environment attempts are not readiness.

## Inputs and invocation

Local etalon (not committed):
`C:/Users/artsafro/AGR-DigitalTwin/data/benchmark/bench-b01-box/etalon.fbx`.
Its SHA256 must match `benchmark/bench-b01-box/etalon.json` before a session starts.
The launcher resolves `main` once to a commit and makes a detached disposable worktree.
For this pilot use `--ref origin/main` after fetching; no branch is moved.

```text
uv run python tools/qa/capability_b01.py --agent codex --model gpt-6.1-sol --ref origin/main --etalon C:/Users/artsafro/AGR-DigitalTwin/data/benchmark/bench-b01-box/etalon.fbx --run-dir C:/x/capability-evals/<new-run>
uv run dt evals --suite capability --main C:/x/capability-evals/<new-run> --output <new-eval-output>
```

Built-in commands (recorded verbatim in each attempt report):

- Codex: `codex --no-daemon exec --ephemeral --ignore-user-config --json -c windows.sandbox="elevated" --sandbox workspace-write --add-dir <run> --model <model> <prompt>`.
  Windows sandbox config is omitted on other operating systems. A private CODEX_HOME
  inherits authentication only, not user AGENTS, memories, sessions or configuration;
  authentication and the private home are removed during cleanup.
- Claude: `claude -p --output-format stream-json --verbose [--model <model>] <prompt>`.
  The Claude lane is paused; it has not been reference-tested. Stream JSON is retained
  but is not a complete Claude session transcript for procedural grading.
- DeepSeek: `--agent deepseek --command-json '["<installed-cli>","<its-options>","{prompt}"]'`.
  No DeepSeek CLI is installed on this host. Supply its actual argv explicitly rather
  than assuming an executable/protocol. Available placeholders are `{prompt}`, `{run}`,
  `{worktree}`, `{etalon}` and `{output}`. No shell template is evaluated.

Outputs live outside the repository: raw `transcript.jsonl`, `stderr.log`, `prompt.txt`,
`benchmark/`, `evals-capability/report.json`, `evals-procedural/report.json` and
`reference.json` (an attempt record, not automatically an accepted baseline).
Existing run directories are rejected; results are never reused. The launcher does
not run the full pytest suite and therefore needs no suite slot.

## Grading

`capability_b01` requires exactly the current ten benchmark checks in both model
and etalon-self reports (20 checks total), with consistent aggregate statuses.
Empty/partial/duplicate/unknown/nonfinite evidence fails. Missing files remain not
measured through `dt evals`. The readiness boolean also requires session success,
unchanged protected inputs/HEAD, procedural success and cleanup.

Native Codex events are passed unchanged to the existing Claude-only procedural
graders. Unsupported/missing transcript evidence is **not measured**, never pass;
no synthetic Claude transcript is manufactured. Full readiness is not established
by benchmark success alone. A future native transcript adapter is not implemented.

## Environment attempts (2026-10-20)

All attempts used origin/main `6e9f3faa22d0e05889c01e46ce15805ed9168a99`, Codex CLI
0.160.1, model `gpt-6.1-sol`, and the hash-verified user FBX. Evidence remains under
`C:/x/capability-evals/t_fd239f23-reference-v00N/`.

| Attempt | Actual outcome | Benchmark tasks P/F/N | Procedural P/F/N |
|---|---|---|---|
| v001 | npm .cmd quoting rejected prompt; fixed double command-line quoting | 0/0/1 | 0/0/10 |
| v002 | no Windows sandbox config after ignoring user config; reads blocked by policy | 0/0/1 | 0/0/10 |
| v003 | explicit existing elevated sandbox, standard home; etalon read by Blender 5.1.2, Python lacks numpy/pydantic, uv not visible | 0/0/1 | 0/0/10 |
| v004 | isolated home to exclude user AGENTS; elevated sandbox setup children hang before reads | 0/0/1 | 0/0/10 |

v003 is **not repository-only evidence** because standard CODEX_HOME loads user
instructions. v004 was stopped by terminating only its owned CLI process tree after
turn completion; cleanup removed its worktree, private home and temporary credentials.
No benchmark report or green result was fabricated. Source inputs were unchanged.

## Prepared-home attempts (2026-10-20, user-approved no OS sandbox)

The operator supplied `C:/x/codex-eval-home` with authentication and minimal config.
`--codex-home` uses that directory without copying/deleting it; stdin is DEVNULL.
The limitation is context-only isolation, `danger-full-access`, **no OS sandbox**.
Do not interpret this as filesystem access confinement.

| Attempt | Actual outcome | Benchmark tasks P/F/N | Procedural P/F/N |
|---|---|---|---|
| v005 | B01 runner exit 0, 10/10 model + 10/10 etalon-self; invalid as repository-only: reads user codex-work skills | 1/0/0 | 0/0/10 |
| v006 | same external user skill reads despite skip_host_skill_discovery, memories/plugins disabled; benchmark reports generated under benchmark/run-v001, not required report paths | 0/0/1 | 0/0/10 |

Both native transcripts contain successful `Get-Content` of
`C:/Users/artsafro/.agents/skills/codex-work-route/SKILL.md` and
`C:/Users/artsafro/.agents/skills/codex-work-loop/SKILL.md`.
Thus a clean CODEX_HOME is insufficient on CLI 0.160.1. Two failures of this cause:
no third session was started, and no user skill/config file was moved or edited.
Both sessions exited 0 and their worktrees were removed; both references have
`passed=false`, `cleanup=true`, protected inputs/HEAD unchanged.
The prepared operator home is intentionally retained and belongs to the operator.
Evidence: `C:/x/capability-evals/t_fd239f23-reference-v005/` and `...-v006/`.

v005 used `codex --no-daemon exec --ephemeral --json --model gpt-6.1-sol <prompt>`.
v006 added `--enable skip_host_skill_discovery --disable memories --disable plugins`.
The built-in command now also requests those context features, but their presence
is not proof of isolation. Audit actual transcript paths before accepting a run.
v005 automatically provisioned its own `.venv` via the repository's `uv run`:
22 packages installed, editable project location was the disposable checkout.
Its standard runner extracted spec v0.6 from the etalon, exported/read back FBX
with Blender 5.1.2; it did not edit tracked specs/checkers/tolerances.
The geometry success is real, but cannot satisfy the repository-only acceptance.

## Resume checklist

1. Operator: provide a runtime that excludes host `.agents/skills` discovery/reads
   without moving or deleting the user's files, or explicitly decide whether those
   external skills are allowed (a weaker acceptance than repository-alone).
   The no-OS-sandbox waiver is already accepted; do not ask for it again.
2. Keep dependencies local to the disposable checkout (`uv sync --locked`, or the
   repository's automatic `uv run` provisioning); retain setup evidence and avoid
   inheriting another worktree's editable install.
3. Run the fresh session; verify the actual model and etalon-self reports and retained
   transcript. Commit the first valid reference, its evidence hashes and a threshold
   selected only after that run. Add `test_reference` covering it.
4. Remaining probes: Windows command shim and complete acceptance-table reconciliation
   in `tmp/issue-390-pr.md`. Current focused run: **162 passed** across capability,
   evals, evals PR and project-state tests; includes junction, fresh-process CLI,
   stale-run, HEAD/protected-input changes, invalid timeout and prepared-home guards.
   RED: 8993433 adds prepared-home/stdin test; later home-alias and host-feature
   regressions also observed failing before their fixes.
5. Run ONE full suite through the task's suite-slot command on the frozen final code.
   Full suite has not been run on this WIP; no PR has been opened.
6. Generate the expected PROJECT_STATE diff in scratch and paste it in the PR;
   **post-merge regeneration per AGENTS.md:66-67**. Do not edit PROJECT_STATE on this
   branch. The generator already supports `evals/capability-b01/reference.json`.
