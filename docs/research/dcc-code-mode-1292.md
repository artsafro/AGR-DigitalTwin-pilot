# DCC Code Mode measurement and Max prototype (#1292)

Status: **offline research prototype; not a production MCP route**. No live Max,
Blender or Revit session was opened. No Revit-Bridge code was downloaded or copied;
its search + bounded-program idea is the issue's input, not a dependency.

## Sources and reproduction

- Frozen task inventory: [#1273 sessions.csv](agent-step-waste-1273/data/sessions.csv),
  28 sessions. [Original report](agent-step-waste-1273.md), especially W2, is the baseline.
- [measurements.json](dcc-code-mode-1292-data/measurements.json): each original transcript's
  relative path, title, SHA-256, per-DCC counters and explicitly loaded tool references.
  Paths resolve below `~/.claude/projects/`. Raw user transcripts are not republished.
- Read-only installed-source census: Max `~/tools/3dsmax-mcp/maxmcp/tools/*.py`,
  Blender `~/AppData/Local/CodexMCP/BlenderLab103/venv/Lib/site-packages/blmcp/tools/*.py`,
  Revit `~/INTERACTIVE_TOUR/RevitMCPServer/dist/index.js`. File hashes are in the JSON.
  AST decorators / literal `server.tool` registrations are counted without importing servers.
- Route provenance: [CAPABILITIES](../agents/CAPABILITIES.md), Max/AGR/Blender/Revit entries;
  [configured routes](../../.agents/mcp_config.json).

```bash
uv run python -m tools.research.dcc_code_mode_measure --out tmp/1292-census-new
uv run pytest -q tests/agr_mcp/test_code_mode.py tests/research/test_dcc_code_mode_measure.py
```

The output directory must not already exist. No source is modified/deleted. The
snapshot was taken on 2026-11-13; some source sessions grew after #1273's 2026-11-12
snapshot. Do not expect byte-for-byte equality with that older report's totals.

## Counting rules and limitations

A task proxy is one session from the original inventory, **not** a GitHub issue:
a job can span several sessions, and one session can contain several user requests.
Calls = deduplicated Claude `tool_use.id` events with an exact DCC route prefix.
Shell commands/headless `blender_runner` executions are not mislabeled as MCP calls.
Exact repeat = same tool + canonical arguments seen earlier in that session,
including failed responses; it is an upper bound on redundant work, NOT proof that
re-execution was unnecessary. User edits between calls can make a repeated read necessary.

Status/inventory polls: Max `list_max_instances`, `max_list_instances`,
`get_selected_max_instance`, `max_dialogs` with omitted/`inspect` action only;
Blender `get_blendfile_summary_path_info`; Revit ping/version/document-info.
Dialog responses, instance selection/rebinding, hold/save are NOT read-only polls.
Blender path-info is an inventory probe, not a busy/idle heartbeat.

Tool-list-in-context measurement is the **union of explicit `tool_reference`s** in
ToolSearch results per active session. It is not the maximum simultaneously resident
schema count: compaction, provider injection and tokenization are not observable here.
Static full catalog counts are a separate potential surface, not token savings.

## Per-DCC measurement table

| DCC | Active sessions / 28 | MCP calls | Calls per active session, median | Status/inventory polls | Exact repeated calls | Repeated polls | Loaded references per active session min / median / max | Full installed static catalog |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 3ds Max (both Max routes) | 23 | 1,024 | 33 | 103 | 163 | 70 | 1 / 7 / 11 | 179 native; 86 AGR tools |
| Blender | 9 | 259 | 9 | 27 | 40 | 20 | 1 / 3 / 4 | 26 |
| Revit HTTP | 0 | 0 observed | not measured | 0 observed | 0 observed | 0 observed | not measured | 94 |

All individual session rows, including zero-call sessions, are in the JSON.
Sessions using both DCCs count in both rows. The Revit zero is a **sample gap**,
not evidence of zero Revit workload/overhead. A separate historical fixture smoke
in CAPABILITIES records 20 Revit calls across 19 tools (2026-10-06); it has no
per-task poll/repeat telemetry and is not combined with this corpus.

#1273 W2's **94 repeated instance-management calls** includes selection/hold/dialog
management and excludes some failure repeats by its tagging precedence. Our 70
repeated **read-only polls** deliberately measure a narrower/different predicate;
94 is not an independently measured number of removable polls.

## Max design and executable fixture

[Prototype](../../src/agr_mcp/code_mode.py), [tests](../../tests/agr_mcp/test_code_mode.py):

```text
frontend: agr_code_search(query) -> exact schemas for an explicit 3-operation allowlist
          agr_code_run({request_id, steps[1..32], allow_write=false})
              snapshot + validate ALL steps before dispatch
              sequential existing AGR MCP client.call_tool(...)
              ordered receipt per step, including skipped remainder
backend:  existing AGR server -> schemas -> host lock -> guarded handler -> runtime
```

An operation-list **script**, not arbitrary JS/Python/MAXScript, is the deliberate
sandbox boundary. No eval/exec, loops, imports, arbitrary code tool, or filesystem
operation is exposed. Supported operations are `agr_check_run`, `agr_op_preview`,
`agr_op_apply`; other existing tools are intentionally not forwarded.
`agr_exec_unsafe` remains unavailable even with `AGR_MCP_UNSAFE=1`.

Read-only is the default. Apply requires explicit `allow_write=true` AND still
passes through the existing preview/PID/document/runtime/state/TTL/apply-row guards.
The boolean is not new user authorization and cannot override a panel-only row.
Existing `agr_check_run` already batches check IDs; prefer that before nesting many
identical checks in this facade. Preview/apply dependencies use explicit backend
preview IDs; this first prototype has no dynamic result substitution.

The fixture uses existing fake pymxs, stable node handles 1/2/3 and a synthetic
installed runtime; it executes the **actual AGR server, bridge, envelopes, locks
and selection restoration** over memory MCP sessions, not a live Max. The two-tool
facade runs two checks in one frontend call and preserves two backend calls and
selection. Another integration probe sends an unknown preview through the actual
server and receives its `stale_preview` refusal. A separate synthetic scene client
commits a rename before raising a transport timeout: the facade records `unknown`,
skips remaining steps, denies subsequent writes, and permits readback of the renamed
stable handle. These are protocol fixtures, not native geometry QA or native latency.

Receipts bind request ID, step ID, tool, argument SHA-256 and program SHA-256 to the
returned backend envelope. Repeated request IDs (even changed payloads) are refused
before a second dispatch. Unknown/cancelled writes latch the session against further
writes. Write admission is checked again immediately before dispatch under a
per-facade async write lock, held through response validation and latch resolution.
Reads may overlap; an already-admitted program whose pending write encounters a
latched uncertainty returns `failed` with that write explicitly `skipped` and a
reconciliation reason. It cannot dispatch or clear another program's latch.
Cancellation during dispatch retains the latch while releasing the write lock;
readback does not automatically reset it. This is single-event-loop facade safety,
not cross-thread/process or DCC session ownership. A backend error is conservatively
unknown for writes: error can occur after commit. Successful writes are
**committed_unverified**, never delivery-pass.

### Explicit prototype limits

- No production registration/config changes and no live-session permission implied.
- Request consumption and uncertainty latch are process-local. No crash-safe journal,
  cross-process exactly-once guarantee or durable receipt recovery is claimed.
  After restart, reconcile before enabling writes; a new session is not a recovery strategy.
- No whole-batch transaction/rollback, no batch-level Max lock, no reduction in backend
  RPCs. Existing guards/locks run for every operation. Another actor can change the
  model between operations; backend preview/state checks remain mandatory.
- No independent verifier is synthesized. Commit receipts require a separate readback
  before production acceptance. The rule draft below describes that boundary.
- A new request ID is not proof that rerunning a write is safe. Reconciliation is the
  operator's policy gate, not a heuristic deduplication of arbitrary write arguments.

## Estimated savings on three real past Max tasks

These are **policy ceilings**, not replayed native execution and not measured elapsed
or token savings. Formula: retain all nonpoll calls and at least the first occurrence
of each identical poll; at most `repeated_polls` can be removed if the pinned process,
document and relevant state remain unchanged. If any uncertainty/user edit occurs,
retain the poll; the safe lower bound is **zero**. Request/receipt batching alone
removes no backend polls. Historical arbitrary MAXScript is NOT supported by the
safe allowlist, so direct unchanged replay through this prototype saves **0 calls**.

| Original task / transcript prefix (full source+hash in JSON) | Actual Max calls | Actual polls | Removable repeated-poll ceiling | Estimated total after policy, best case | Saved calls/polls range | Best-case share |
|---|---:|---:|---:|---:|---|---:|
| Gates Object001 resize / `b8d40379` | 124 | 5 | 4 | 120 | 0..4 / 0..4 | 3.2% |
| MaxScript material cleanup / `f9c15b42` | 149 | 26 | 21 | 128 | 0..21 / 0..21 | 14.1% |
| KG-Grupp bench / `f305f3dd` | 33 | 7 | 5 | 28 | 0..5 / 0..5 | 15.2% |

The original Garibaldi session is mostly **Blender**, despite its NPM/VPM title:
137 DCC calls there must not be counted as Max. The per-route split avoids that error.
For the fixture, 2 independent reads cost 2 direct frontend calls versus 1 code-run
(+1 catalog search on a cold start), and still 2 backend calls. At 32 reads the warm
frontend count is 32 -> 1; cold 32 -> 2. Polls remain 0 -> 0. These are fixture call
counts, not an assertion that 32 historical operations can safely be packed together.

The AGR surface is 86 -> 2 advertised tools (97.7% fewer **names**, not tokens), with
only three operations supported. Compare the native installed Max route fairly:
its `server.py` already offers full/core/progressive profiles (179 / 118 static
registered definitions; progressive uses routing plus lazy discovery/dispatch).
Thus don't deploy another raw-script escape hatch to solve catalog size. The new
value to evaluate is guarded composition + receipts, not discovery alone.

## Blender: do not build another Code Mode

220 / 259 calls already use `execute_blender_code`; 27 are path-info probes and 12
object summaries. Of those 27 probes, 20 repeat identical arguments. The original
#1273 error analysis found 21 path-info failures; failed probes aren't fixed by
wrapping them in more code. Current catalog: 26 static tools; observed loaded refs
are only 1..4 per active session. Headless jobs already use
`src/dt_ai/core/blender_runner.py` (outside the MCP census).

Decision: **no new code execution/batch layer**. Use the existing code/headless
route under its ownership/authorization rules; retain independent post-write readback.
The potential repeated-inventory ceiling is 20 calls, not a measured speedup. No
follow-up issue draft: marginal composition gain over the existing 220 code calls
has not been demonstrated. Do not blindly repeat `execute_blender_code` after a timeout.

## Revit: do not prototype a new wrapper on this evidence

94 static tools match the documented HTTP route; installed source identifies itself
as 0.8.40, newer than the 0.8.31 historical smoke. It already has `REVIT_MCP_PROFILE`
(core always included, 8 names) and `revit_batch` with stop-on-error/dry-run support.
Core-only would reduce 94 -> 8 names (91.5%); actual session token savings and native
batch safety/performance are **not measured**. The 28-session corpus has no Revit calls.

Decision: **no new execution layer**, no installation of Revit-Bridge, no write tests
on Artem's model. Prefer evaluating the existing profile/batch route when a real Revit
task is authorized. No follow-up issue draft: catalog-size arithmetic alone is not a
measured workload gain. Revit-Bridge's advertised 28 -> 2 / up to 32 ops is source
context from #1292, not our 94-tool route's measured behavior.

## Rule draft and verification

[DCC reconcile-not-retry draft](dcc-reconcile-not-retry-1292.md) covers all three DCCs.
It is intentionally not promoted to shared skills, domain law or a numbered decision.
Tests cover empty/partial/unsupported/nonfinite input, 32/33-step boundary, repeated
IDs, status failures, unknown writes, cancellation, caller mutation, concurrent
request reuse, unsafe-name generation, existing guard delegation and fresh imports.
No native exported artifact or native performance improvement is claimed by pytest.
