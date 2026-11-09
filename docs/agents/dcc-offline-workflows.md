# Offline DCC preparation and native-run handoff

Status: offline helper + operator runbook, **not a verified native adapter**. This card did not
install, launch or connect to Blender, 3ds Max or Revit. Follow the permission matrix in
[WORKFLOW.md](WORKFLOW.md#permission-matrix); this document grants no new permissions.

## Selected research proposals

1. File-only subset of [MCP bridges, Task 2](../research/mcp-dcc-bridges.md): stage a disposable
   copy, record source SHA-256, verify the immutable original after a workflow, retain failed runs.
   `tools/mcp/fixture_manager.py` implements this subset, not units/dirty-state inspection or reset.
2. Runbook subset of [MCP §2.3](../research/mcp-dcc-bridges.md),
   [Blender A](../research/blender-bpy-automation.md#proposed-next-tasks), and
   [Max 2](../research/3dsmax-scripting.md#proposed-next-tasks-recommendations): separate offline
   tests, future headless runs and cooperative multi-agent ownership. Revit limits follow
   [the Revit report](../research/revit-api-automation.md).

The MCP experiment on `experiment/mcp-dcc-bridges` reports fewer torn reads under a workflow lease
and residual datablocks under object-only cleanup. It used Blender 4.4 / port 9876, **not** the
approved Blender 5.1.2 baseline. Its measurements are motivation, not certification of 5.1.2,
Blender Lab or the Max/Revit routes. No prototype lease or reset code is promoted here.

## File staging (no DCC required)

From the repository root, with an approved source and a **new**, card-owned output directory:

```bash
uv run python tools/mcp/fixture_manager.py stage \
  "C:/approved/fixture.blend" "tmp/t_25370275/blender-v001"
uv run python tools/mcp/fixture_manager.py verify "tmp/t_25370275/blender-v001"
```

Paths are placeholders; use `.blend`, `.max` or `.rvt`. The CLI creates `working.<suffix>` and
`fixture.json`, refusing any existing run directory (even an empty one). Hashes are streamed;
the original and copy must match the initial source hash at staging completion. A concurrent
change or I/O failure may leave a partial directory: preserve it for diagnosis, use v002 next.

Verification is read-only: source path/hash before/after, working-copy existence/hash/change,
`delivery_passed=false`. Working-copy edits are allowed and reported separately from etalon damage.
Exit 0 means file checks succeeded, 1 means changed/missing source or missing copy (or a staging
integrity mismatch), 2 means invalid arguments/manifest or I/O failure. Missing source is not a pass.
Do not replace the manifest to conceal a mismatch. Keep the initial manifest with the run evidence.

Limits: this copies **one file**, not linked RVTs, libraries, textures or XRefs; the manifest is not
signed, portable after moving the source, or an atomic snapshot of an externally edited file.
It is not a sandbox and does not enforce read-only permissions on originals. Only use trusted,
quiescent inputs/manifests and card-owned directories; do not edit the manifest or swap symlinks.
The helper does not inspect model validity, units, active documents or queued requests, acquire a
lease, start DCCs, save/reset scenes, delete/quarantine directories, or certify delivery.

## Offline tests and evidence

```bash
uv run pytest -q tests/test_dcc_fixture_manager.py
uv run pytest -q  # default lane from pyproject addopts: excludes blender, dcc, acad, perf, max
uv run dt profiles check
uv run dt schemas --check
```

The tests use explicitly synthetic opaque bytes, not real model files. They exercise actual
filesystem copies, mutation detection and the CLI; a passing test does not imply `.rvt` parsing.
Existing native tests use `blender`/`dcc` markers and skip when their executable prerequisite is
absent. Some automatically discover Blender: **unsetting DT_BLENDER alone is not an offline gate**.
On a no-DCC card, exclude both native markers, including when a program is installed. Report the
selected/deselected totals separately; never describe that run as unrestricted native verification.

On this Windows/Git Bash host, use native `C:/...` subprocess paths and quote spaces. For shell
fixture tests that depend on MSYS conversion, remove `MSYS_NO_PATHCONV` and `MSYS2_ARG_CONV_EXCL`
only for the test command. Use a card-private `TMPDIR`/`TEMP`/`TMP` and pytest `--basetemp` to avoid
cross-worktree collisions. Do not alter global environment settings to make a test pass.

## Future headless runs (examples only; not executed here)

Only after the task authorizes native execution, confirm the executable/version, script, source,
new output directory and process ownership. Retain exact argv, version/build/Python identity,
start/end times, timeout, stdout/stderr, exit code, input/output hashes and explicit unrun checks.
Reject stale evidence; reopen/export-readback independently. Exit 0 alone is not a QA verdict.

### Blender

The approved baseline is 5.1.2, not the older version mentioned in some domain/history files.
`--python-exit-code 1` is mandatory on every headless Blender call: without it a Python exception inside Blender exits 0 and a checker reads success.
An isolated FBX readback candidate (input is an already exported FBX, not `working.blend`):

```bash
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" \
  --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python tools/blender/fbx_readback.py -- \
  "C:/approved-export/model.fbx" "C:/new-run/readback.json"
```

This existing script supplies structural facts, not a general intersection/outwardness certificate.
The output path must be new even where an existing script does not enforce that itself.
Factory startup is not an OS sandbox. Do not add pip `bpy` to core dependencies or substitute a
wheel test for executable/FBX evidence. Never use headless examples against the user's live scene;
live calls follow the session-lock wrapper required by workstation coordination rules.

### 3ds Max

Use one authorized Max process at a time, only on copies. `tools/max_profile_roundtrip.py` is an
existing native candidate, **not** an offline Python entry point (`pymxs` belongs inside Max).
A future batch invocation skeleton, adapted from the research and requiring native quoting checks:

```bash
"C:/Program Files/Autodesk/3ds Max 2026/3dsmaxbatch.exe" \
  "C:/repo/tools/max_profile_roundtrip.py" -safescene ON \
  -mxsString 'config:C:/new-run/config.json' \
  -log "C:/new-run/batch.log" -listenerlog "C:/new-run/listener.log"
```

The configuration is JSON with `fbx` (absolute FBX input) and `output_dir` (fresh output directory).
The fixture helper's `.max` copy is **not** that script's FBX input. Do not pass it as one.
The candidate hardcodes embedded textures and lacks independent reimport; it is not a VPM preset.
Plugin availability, exporter parameter readback, FBX binary version and independent geometry/UV
readback need native evidence. `-i`/`-p` are INI paths, not scripts; `-dm` is not a general sandbox.
A batch timeout may leave a child process alive: stop dispatch, preserve logs and reconcile before
starting another Max. Do not assume a killed parent means the DCC is idle.

### Revit

There is no supported standalone host-Python `import RevitAPI` route for native `.rvt` processing.
Use an authorized in-process add-in/bridge on the Revit main thread; mutations need transactions.
The current extraction path is `tools/source/measure_spec_revit_twin.mjs` → HTTP TwinPack →
`src/dt_ai/spec/revit_twin.py`; offline TwinPack tests are not a live Revit check. Do not invoke the
broken `revit-twin` registration. IfcOpenShell is an IFC-only alternative, not a `.rvt` engine.
No IFC parser/dependency or cloud APS WorkItem is added here; approved fixtures/schema/export settings,
cloud security/budget and target versions remain separate tasks/user decisions.

## MCP workflow ownership protocol (cooperative, not enforced by this helper)

1. Reserve **one owner per program for the entire workflow**, not one lock per call. Record card,
   agent, client PID/start time, application PID/start time, route, document path, version, units,
   source hash and output directory. Worktrees and serial UI-thread calls do not isolate scenes.
   Revit HTTP and pipe aliases share the same program reservation. Do not claim true fencing:
   raw socket/HTTP clients bypass advisory leases; an enforcing broker is future work.
2. Before mutation, use the matching DCC skill, current wrapper and read-only smoke. Max: explicit
   verified instance → bridge status → on-demand session/units context → scene info. Blender:
   path/datablock summary → reviewed `import bpy` version/unit query. Revit HTTP: ping → version →
   document info; pipe: status → version → active-document info (status alone is not UI-thread proof).
   Read real returned fields; absent units are unknown, not inferred. Ports in reports are historical,
   not a discovery mechanism. Do not bypass the workstation's approved wrapper/lock route.
3. Keep the reservation through copying, inspection, mutation, export, readback and teardown.
   Never open originals directly for processing. Preserve dirty user documents. No automatic global
   reset, close-without-save, `hold/fetch`, or inventory-diff deletion in a shared live scene.
4. On timeout, disconnect, `RequestOutcomeUnknown` or `DialogBlocked`, record **outcome unknown**,
   cease mutation/retry and retain logs/artifacts. Transport abort is not host rollback/cancellation.
   Dead client or expired heartbeat does not prove the DCC is idle: quarantine operationally, do not
   steal the reservation or delete evidence. Reconcile state read-only under the current owner or
   escalate to the operator; replay only after known pre-dispatch failure or established idempotence.
5. Under held ownership, verify the immutable source hash, working-copy path, units, expected scene
   inventory, and no unknown in-flight work. Dispose/reset only authorized disposable state; Blender
   object deletion alone can leave meshes/materials. Inventory-diff cleanup is unsafe without exclusive
   ownership. Release only after reconciliation; record unresolved recovery work explicitly.
6. Separate file integrity, operation completion, technical QA, visual/user acceptance and publication.
   Native export readback, topology, normals, UV, materials and transforms remain mandatory for delivery;
   V015–V017/manual gates stay `review`/`not_run` while open. Never promote this helper's exit 0 into
   `passed=true`. No production-model gates change as a result of this document.
