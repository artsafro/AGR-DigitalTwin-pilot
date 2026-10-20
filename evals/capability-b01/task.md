# Capability A: B01 from the repository alone

Status: WIP, blocked on an isolated Windows Codex sandbox. No accepted reference or
threshold has been established. Environment attempts are not a geometry result.

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

## Resume checklist

1. Prepare an operator-approved isolated CODEX_HOME with functional Windows sandbox
   state, without user instructions/memories, and an accessible Python/uv toolchain.
   Do not bypass sandbox policy or change machine settings in the worker.
2. Add dependency provisioning (`uv sync --locked` in the disposable worktree),
   recording the exact interpreter and setup log. The existing launcher does not yet
   provision this environment; avoid inheriting another worktree's editable install.
3. Run the fresh session; verify the actual model and etalon-self reports and retained
   transcript. Commit the first valid reference, its evidence hashes and a threshold
   selected only after that run. Add `test_reference` covering it.
4. Finish Windows command-shim, junction/alias, changing-input and stale-evidence
   probes; validate every acceptance-table row in `tmp/issue-390-pr.md`.
5. Run focused tests and ONE full suite through the task's suite-slot command on the
   frozen final code. Full suite has not been run on this WIP.
6. Generate the expected PROJECT_STATE diff in scratch and paste it in the PR;
   **post-merge regeneration per AGENTS.md:66-67**. Do not edit PROJECT_STATE on this
   branch. The generator already supports `evals/capability-b01/reference.json`.
