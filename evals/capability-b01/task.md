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

## Prepared-home attempts (2026-10-20, user-approved no OS sandbox) [D158]

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

## Private-profile probe (2026-10-20)

One additional operator-authorized cheap probe used a detached origin/main checkout
and the prepared CODEX_HOME, with HOME and USERPROFILE redirected to the empty
`C:/x/codex-eval-home/userprofile`, HOMEDRIVE/HOMEPATH redirected consistently,
and APPDATA/LOCALAPPDATA under that profile. No user files were copied or moved.
The command retained `skip_host_skill_discovery`, memories/plugins disabled and
stdin DEVNULL. Prompt: `list the skills you have`.

The session exited 0 but its native agent message still listed `codex-work-route`,
`codex-work-engineering`, `codex-work-loop` and `codex-work-review`, alongside other
non-repository skills. This proves context contamination remains; the probe does
not establish which Windows home-resolution mechanism caused it or that skill
files were read in this particular session. No full reference v007 was launched.
Its disposable worktree was removed and registration cleanup succeeded.
Evidence: `C:/x/capability-evals/t_fd239f23-profile-probe-v007/`
(`transcript.jsonl`, `stderr.log`, `probe.json`, including exact argv/environment).
No further environment variants are authorized: accept external user skills as a
recorded limitation, or provide a separate Windows account/VM.

## Historical resume checklist (superseded by the accepted reference below)

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

## Accepted reference: v007 (2026-10-20)

The user accepted host skill discovery as a recorded limitation on this card [D158].
This reference measures **repository + user skills**, NOT repository-only.
It uses prepared `CODEX_HOME=C:/x/codex-eval-home`, `danger-full-access`,
**no OS sandbox**, stdin DEVNULL. A separate Windows account/VM for a genuinely
repository-only reference remains follow-up work; do not set it up as part of #390.

Exact invocation (the full expanded argv is also in `reference.json`):

```text
uv run python tools/qa/capability_b01.py --agent codex --model gpt-6.1-sol --ref origin/main --etalon C:/Users/artsafro/AGR-DigitalTwin/data/benchmark/bench-b01-box/etalon.fbx --run-dir C:/x/capability-evals/t_fd239f23-reference-v007 --codex-home C:/x/codex-eval-home --isolation "repository + user skills; no OS sandbox; user-approved 2026-10-20" --command-json '["codex","--no-daemon","exec","--ephemeral","--json","--enable","skip_host_skill_discovery","--disable","memories","--disable","plugins","--model","gpt-6.1-sol","{prompt}"]' # [D158]
```

- Input: origin/main `8d5c8987dbd46343176ca5af9d1791c864a86217`;
  Codex CLI 0.160.1; model gpt-6.1-sol; Blender 5.1.2.
- Session exit 0; measured duration 141.573 seconds; detached worktree removed,
  protected benchmark/jobs/etalon and HEAD unchanged.
- Model: **10/10**; etalon-self: **10/10**; additional independent FBX readback:
  **10/10**. Extractor questions: 0; model triangles: 282.
- External skills actually read successfully: `codex-work-route`,
  `codex-work-loop` (item_4), `codex-work-review` (item_19).
  `codex-work-engineering` is named in the retained stream but has no observed read.
  These are every external skill named/loaded in the native parent transcript;
  subagent internal context is not separately captured.
- Procedural graders: **0 passed / 0 failed / 10 not measured**: native Codex
  events are unsupported by the existing Claude-only graders. **Readiness=false**;
  this is neither procedural success nor NPM/VPM delivery acceptance.

The session chose versioned `benchmark/run-v001/` plus `benchmark/check-v001/`.
The initial launcher expected root-level reports and recorded 0/0/1; that record
remains untouched. After RED/GREEN regressions for native layout and CLI metadata,
`dt evals --suite capability` regraded the SAME retained artifacts (no new session,
no edits to reports/checkers/specs): **1 passed / 0 failed / 0 not measured** in
`evals-capability-v003/report.json`. Earlier regrades remain preserved.
The task now discovers versioned reports, requires one model/etalon pair in the
same directory, rejects duplicate pairs/aliased inputs, and validates every
supplementary report too; supplementary failures cannot disappear behind 20/20.

### Threshold selected after the reference

Benchmark success requires **20/20** mandatory model + etalon-self checks and
all checks in any supplementary report; no failed/unmeasured checks, partial,
nonfinite, duplicate or unsupported evidence. Individual numeric equality limits
are the benchmark runner's existing semantics, not a new geometry tolerance.
Full capability readiness additionally requires procedural **0 failed / 0 not
measured**, session exit 0, unchanged protected inputs/HEAD and successful cleanup.
The reference passes the benchmark threshold but NOT full readiness. There is no
latency/token threshold: one sample does not establish a distribution.

Committed `reference.json` retains exact argv, versions, limitations, counts,
post-run threshold and SHA256s. `reference/` retains the actual machine reports;
raw transcripts, FBX and etalon stay outside git under the run/input paths above.
`test_reference` verifies the committed evidence hashes and all report counts.

Review hardening: new launches snapshot every tracked checkout input, including
checker code, specs and tolerances, before the session and compare bytes afterward
using the original path set even if the child changes the index. A mutation records
`changed_evaluation_inputs` and a named diagnostic, sets
`protected_inputs_unchanged=false`, and invalidates benchmark acceptance (0/1/0).
Raw report counts remain diagnostic-only in `benchmark_reported`; green reports do
not override the mutation. This is a before/after integrity check, not OS sandboxing
or detection of a transient edit restored before the final snapshot. The historical
v007 reference has not been rerun with this new guard; its earlier integrity claim
covers benchmark/jobs/etalon and HEAD only, not a retroactive checker snapshot.
`PROJECT_STATE.md`: **post-merge regeneration per AGENTS.md:66-67**; this branch
changes the generator and supplies only an expected scratch diff in the PR.
