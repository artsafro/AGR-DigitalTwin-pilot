# Experiment: MCP bridges to Blender / 3ds Max / Revit — multi-agent sharing

Card `t_d6c8f213` (experiment, [blender]). Report under test: `docs/research/mcp-dcc-bridges.md` (on `main`, PR #36).

## Question

The report says every DCC bridge serializes single calls on the main thread, but none isolates a
**multi-step** workflow, so two agents interleave (torn reads, overwritten edits), and proposes (2.3) a
host-global lease per program with PID + start-time identity, fencing tokens and quarantine, plus a
disposable fixture lifecycle (copy, hash before/after, reset). Do these hold on the live Blender the
workers use today, and are they worth adopting?

## Methods tested (2 of the report's proposals)

- **M1 — program lease over a whole workflow** (report 2.3.1–2.3.4, Task 1). Prototype
  `experiments/mcp-dcc-bridges/dcc_lease.py` (142 lines, stdlib + ctypes): `O_EXCL` lease file
  `%LOCALAPPDATA%\Temp\agr-dcc-leases\blender.lease`, owner = PID + process creation time (`GetProcessTimes`),
  monotonically increasing fencing token checked before every step, dead owner → reclaim only after the
  DCC answers a ping, otherwise `Quarantined`. Baseline: today's per-call lock in `blender_exec.py`.
- **M2 — fixture lifecycle: inventory-diff reset + etalon hash** (report 2.3.3, Task 2). Before a workflow,
  snapshot the names of every ID in `objects/meshes/materials/images/collections`; at the end remove every ID
  not in the snapshot. Baseline: the current card rule "remove the objects you created"
  (`bpy.data.objects.remove(obj)`). Etalon files (`benchmark/bench-b0{1,2,2t}/*`) SHA-256 before/after.

Not tested: 3ds Max / Revit routes (programs not available to this card; the report's claims about them stay
code-reading only), enforcing broker (report itself says it does not exist yet).

## Setup

- Blender 4.4.0, ahujasid blender-mcp add-on on 127.0.0.1:9876, driven only through
  `hermes_kanban/scripts/blender_exec.py` (not edited). User scene before/after: 0 objects, 1 mesh, 2 materials.
- Fixtures: engine `from_spec` body meshes of B01 (156 v / 141 f), B02 (263 / 236), B02t (370 / 324), written
  to `%TEMP%\agr-exp-t_d6c8f213\fixtures\` (no file in `data/` or `benchmark/` written).
- Workflow (`agent.py`) = 5 `blender_exec` calls per mesh: snapshot → create (bpy.data mesh + material +
  object) → move x+10 → **scene-wide readback** (mesh-object count, vertex sum, world min-x; any mismatch
  with the agent's own expectation = torn read) → cleanup.
- Concurrency: 2 agent processes in parallel, 3 meshes × 2 rounds each = 12 workflows / 60 calls per run;
  4 configs × 3 reps. `uv run python experiments/mcp-dcc-bridges/harness.py fixtures|concurrency 3|recovery`
  (≈ 2 min total). Raw: `experiments/mcp-dcc-bridges/results_{concurrency,recovery}.json`.

## Results

### Two agents in parallel (36 workflows per config)

| Lock | Cleanup | Torn readbacks | Failed workflows | Residual datablocks after 12 workflows | Wall, median of 3 |
|---|---|---|---|---|---|
| per-call (current) | remove object (current) | **13 / 36** (6, 2, 5) | 0 | **+12 meshes, +12 materials** every run | 8.48 s |
| per-call (current) | inventory diff | 7 / 36 (1, 2, 4) | **1** (deleted the other agent's object → `KeyError` in its next step) | 0 | 8.68 s |
| **lease** | remove object | 0 / 36 | 0 | +12 meshes, +12 materials | 8.92 s |
| **lease** | **inventory diff** | **0 / 36** | **0** | **0** | 8.67 s |

- Lease overhead: 1.2 ms per uncontended acquire+release (median of 50); wall time within run-to-run noise
  (8.43–9.18 s across lease runs vs 8.36–8.74 s per-call). Two agents sharing one Blender serialize anyway, so
  holding the session for a whole 5-call workflow costs no throughput here.
- Residual check: the "remove the object" rule leaves 1 orphan mesh + 1 material per workflow (72 + 72 over
  the 6 runs; removed by hand after the run). Orphans are not saved into a .blend, but they accumulate in the
  live session and are visible to every later scene-wide check (`bpy.data.meshes` counts).
- Etalon SHA-256 of all 15 `benchmark/` files: unchanged before/after.

### Crashed holder and identity

| Case | Current per-call lock | Lease prototype |
|---|---|---|
| Holder killed mid-call, Blender idle afterwards | lock file left; next caller `busy` (exit 3) after `--wait 10`; stale only after **1800 s** (`max(1800, timeout+120)`) | reclaimed in **0.15 s** (`owner_dead`, ping OK) |
| Lease names a live but different process (PID reuse, start time differs) | n/a (no PID check; treated as held until stale) | reclaimed in 0.12 s (`pid_reused`) |
| Owner alive | waits | `Busy` after `--wait` (2.0 s), not taken over |
| Owner dead, DCC does not answer ping | — | `Quarantined`, lease file kept (no takeover) |

## Verdicts

| Method | Verdict | Reason |
|---|---|---|
| M1 program lease over a workflow (PID + start time, fencing token, ping-gated reclaim) | **adopt** | Torn scene-wide readbacks 13/36 → 0/36 with two agents; recovery after a crashed holder 1800 s → 0.15 s; 1.2 ms overhead; no throughput loss. Cooperative only — a client that opens 9876 directly bypasses it (as the report says). |
| M2 inventory-diff reset + etalon hash | **adopt, only together with M1** | Residual datablocks 24 per 12 workflows → 0, etalons unchanged. Without a lease it is unsafe: it deleted another agent's object once in 36 workflows. |

The report's core claim (single calls serialized, multi-step workflows interleave) is confirmed on Blender:
no crash or socket desync in 359 interleaved per-call-locked calls, but up to 6 of 12 workflows per run read another
agent's object.

## Proposed follow-ups (not created as issues)

1. **`tools/mcp/dcc_lease.py` + `blender_exec.py --lease`** — move the prototype into the shared tool; add
   `--lease-token`/`--card` to `blender_exec.py` so every call of a held workflow passes the fencing check; a
   `dcc-lease acquire|status|release` CLI for workers that run several `blender_exec` calls; one lease file per
   program (`blender`, `3dsmax`, `revit` — `revit-http-2025` and `revit-bridge` share `revit`). Acceptance:
   `harness.py concurrency` gives 0 torn with lease; `harness.py recovery` table as above.
2. **Blender session reset by inventory diff** — a `snapshot`/`restore` pair (in `blender_exec.py` or the
   Blender skill) used at the start/end of every [blender] card under the lease; replace the card rule
   "remove the objects you created" with it. Acceptance: residual datablocks 0 after the concurrency
   harness; benchmark etalon hashes unchanged.
