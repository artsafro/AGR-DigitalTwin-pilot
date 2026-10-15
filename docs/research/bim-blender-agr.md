# Blender for AGR: headless, live session and offline library

Research snapshot: repository `8f48c44452e67eccd25b5901833de7e36aeb50d1`.
Continuation started with this report already present as an untracked partial draft; no tracked diff existed.
Scope: research card, no GitHub issue; one new report extending
[Blender automation research](blender-bpy-automation.md) and
[session-bridge measurements](../experiments/blender-exec-session.md), not replacing them.

## Summary

- Prefer **offline geometry/rules → headless Blender I/O → independent readback → human acceptance**, not a live-session-only twin builder.
- Live Blender earns its shared-session cost for unsaved-source snapshots and interactive review; bulk generation and repeatable QA belong outside that session.
- The current repository already has a shared isolated Blender runner and offline orientation checks; older reports proposing these are historical, not the current implementation status.
- Existing experiments establish small synthetic geometry parity, not full NPM/VPM, texture, render or Max interoperability coverage.
- KPP1/PSU275 need delivery gates closed, Ground needs review/Max verification, and OBJ03/GLB modelling remains stopped; automation does not authorize restarting them.
- Blender can prepare editable masters, derived exports, evidence renders and scene facts; it cannot establish source truth, survey coordinates or signed visual acceptance.
- Prioritize three bounded experiments: cross-route readback parity, reproducible render evidence, and material/UV-preserving Max hand-off on benchmark copies.
- No DCC was launched, installed or queried; measurements below are attributed historical results or proposed acceptance targets, not new native measurements.

## Findings (with sources)

### Evidence vocabulary and what changed since the earlier reports

- **CODE**: directly read in this worktree; establishes implementation, not execution.
- **HISTORICAL**: a tracked report describes a past experiment/job. Its local binary assets, installed applications and external wrappers were not reverified here.
- **SOURCE**: upstream documentation/source assertion, with URL; not a local runtime guarantee.
- **PROPOSAL**: a future experiment or routing recommendation, not an implemented capability.

**CODE:** `src/dt_ai/core/blender_runner.py::run_blender` now supplies background/factory/disable-autoexec/exception-exit flags, per-process configuration directories, captured logs, finite timeout validation, and fresh nonempty output/JSON checks. `src/twinqa/scene.py`, `src/dt_ai/core/build.py` and `tools/qa/run_benchmark.py` use this boundary. It checks freshness, not an artifact's domain validity or a general JSON schema. Its `subprocess.run` timeout is not evidence of descendant-tree termination through arbitrary executable shims. Thus the launch-policy work proposed in the earlier research is partly implemented; do not commission it again unchanged.

**CODE:** `src/twinqa/geometry/checks.py::run` now includes `check_orientation`; its result carries per-mesh judged faces and `unjudged_meshes`. A fully hidden mesh can remain unjudged without failing, and rays from below are excluded. `technical_library/mesh_audit/core.py` also has winding/near-duplicate/bowtie counters but retains `intersection_test_performed=False`. This supersedes older statements that these counters or the orientation gate are wholly absent. General transverse intersection and UCX containment certification are still not established by these functions.

**HISTORICAL:** [BMesh/BVH experiment](../experiments/blender-bpy-automation.md) detected 12/12 injected defects on B01/B02/B02t versus 0/12 in its then-baseline checker. It is not the baseline for today's orientation code. Its depth-only embed allowance could hide a shallow defect; bind allowed crossings to actual inset-slab provenance before using them as a gate. [Mesh-audit experiment](../experiments/blender-mesh-audit-live.md) found integer-counter parity on 15/15 variants; separate live auditing added session latency without additional geometry information. Reuse these results rather than repeat their cube/topology-only benchmarks.

### Headless versus live is an execution boundary, not two modelling algorithms

**SOURCE:** Blender's CLI supports background execution and processes arguments in order [S1]. Operators depend on context and can fail `poll()` [S2]. **Inference:** a common `bpy.data`/BMesh payload can serve a background process and a controlled live fixture; UI operators require separate context qualification. Loading a file after creating geometry can replace that geometry. Factory startup/configuration isolation is not an OS security sandbox.

**HISTORICAL:** [Session report](../experiments/blender-exec-session.md) measured about 124 ms per CLI call, 0.41 s for 1,000 data-API cubes versus 34.5 s using operators, a 20 KB stdout truncation problem, lock bypass with different temp directories, and continued execution after client timeout. These are observations on Blender 4.4/ahujasid at port 9876, not universal Blender performance or current wrapper behavior. [Bridge experiment](../experiments/mcp-dcc-bridges.md) later measured 13/36 torn workflow reads with per-call locks versus 0/36 with its cooperative workflow lease. That prototype does not fence direct clients.

**HISTORICAL:** [Bridge research](mcp-dcc-bridges.md) distinguishes Blender Lab/9877 from the ahujasid/9876 route used by `blender_exec.py`. Do not switch ports/protocols on the strength of a shared product name. A client timeout means outcome unknown, not rollback. For production reviews, exclusive ownership spans snapshot, mutation, verification and cleanup; a per-call lock alone does not supply that ownership.

### Offline library does not mean an in-process bpy dependency

**CODE:** `src/dt_ai/geometry/from_spec.py` builds geometry arrays outside Blender; source extraction and pattern-aware checks are separate. `tools/source/measure_spec_blender.py` reads evaluated mesh data/world coordinates and LEVEL helpers, then releases temporary meshes. It labels units as metres; that string is not a measurement of the original author's units. `tools/blender/fbx_readback.py` reports structural counts/transforms/UV/packed-image facts, not all face data, shader fidelity, normals or a delivery verdict.

**HISTORICAL:** [Wheel viability report](bpy-wheel-viability.md) already tested a separate Python-3.13 `bpy==5.1.2` lane, matching a small FBX fixture and two existing scripts against the executable. The earlier research's wheel experiment is therefore partly answered. This does not establish benchmark-scale materials/multiple-UV/custom-normal/render parity. **SOURCE:** module use has a different executable/signal-handler boundary [S3]. Retain the executable route as the repository default; a separate wheel environment is optional, not the meaning of “offline library” in the matrix.

### Render evidence, editable Max hand-off and regulatory exports are different artifacts

**CODE:** `tools/render_profile_comparison.py` is background-only; it opens the saved master and separately imports its actual FBX, retains common front/oblique cameras, emits four PNGs and `render-evidence.json`, and uses `BLENDER_EEVEE_NEXT`. This proves an evidence-generation path exists, not that rendering works on this host/version. It compares master to transport; architectural correctness also needs approved-source comparison. Preview cameras/lights are not main-delivery contents.

**CODE:** `tools/export/export_mesh_blender.py` preserves input polygons where reconstructible, creates material slots and LEVEL empties, and refuses existing output files. It does not construct production UV/texture sets. It is benchmark exchange, not a final triangulated mesh-only delivery exporter. `jobs/UV-CONTINUOUS/scripts/export_max_v006.py` demonstrates selection-only quad hand-off, embedded/external diffuse, exact topology/UV comparisons and embedded-byte hashing. Its hard-coded historical output root and overwrite behavior mean it should be studied, not executed unchanged on new fixtures.

**HISTORICAL:** `jobs/FACADES-ATLAS/STATE.md` records a native Max reverse-FBX comparison with UV max error 0, IDs 101–105 retained, mapChannel 1, but up to 0.489 mm world-coordinate error at large offsets. `jobs/UV-CONTINUOUS/STATE.md` records Blender roundtrip success but native Max import unconfirmed. These are different evidence scopes. [Max headless experiment](../experiments/max-headless-agr-roundtrip.md) achieved geometry transport but only 7/9 FBX benchmark checks when its prototype omitted material objects; OBJ also lost LEVEL semantics. Small geometric deviation did not preserve the semantic contract.

**Repository policy:** `docs/domain/{export-import,geometry,materials,uv-textures,npm-vpm,validation}.md` require profile-specific output: editable quad master versus triangulated delivery copy; NPM embedded atlases/separate opacity versus VPM external Diffuse/ERM/DirectX Normal; explicit material/slot/UDIM mapping; local work frame versus profile placement. Do not promote the SOSH embedded-diffuse hand-off preset into a VPM delivery preset. C23 Shell and C25 detailed infill recess remain unresolved globally in `docs/domain/conflicts.md`; PSU275's recorded job-specific Shell choice does not settle them for other jobs. Ground density's unit conflict also remains open; this report selects no interpretation.

## How it applies to this repository

### AGR task → automation route → evidence → open risks

Routes are recommendations for this program; CODE/HISTORICAL indicate the strength of the capability evidence, not readiness of a complete delivery.

| AGR task | Automation route in this program | Evidence | Open risks / boundary |
|---|---|---|---|
| Capture an unsaved architectural source, confirm units/document/version | **Live** read-only inventory and authorized versioned snapshot; continue on a copy headlessly | HISTORICAL `jobs/WINDOW-FRAMES/STATE.md`, `jobs/REVIT-OPENINGS/STATE.md`; CODE `tools/source/measure_spec_blender.py` consumes saved files | Disk may differ from live state; snapshot needs user scene ownership. Blender mesh import cannot recover missing native BIM parameters. |
| Extract contours, openings, levels and material provenance | **Headless** Blender mesh dump → **Offline library** `dt_ai.spec` | CODE `tools/source/measure_spec_blender.py`; `jobs/KPP1/STATE.md` mesh/Revit comparison | Revit feet matrices, truncated names, ambiguous finishes, source omissions; unknowns stay questions, not defaults invented by a generator. |
| Build OKS exterior/body, openings, roofs, terraces/decor | **Offline library** `from_spec`, exterior/shell/connect → **Headless** scene realization | CODE `src/dt_ai/geometry/from_spec.py`, `tools/export/export_mesh_blender.py`; HISTORICAL B01/B02/B02t green in `docs/PROJECT_STATE.md` | Unsupported cases stop; K01 has known stops, K02 assets await the user. C23/C25 remain scoped decisions. OBJ03 `from_source` is unsuccessful and not authorized to resume. |
| Repeated window/frame library and instanced placement | **Offline library** type/placement calculations → **Headless** assembly; **Live** selective review | HISTORICAL `jobs/REVIT-OPENINGS/STATE.md`: 285 assignments, including 89 approximate; `jobs/WINDOW-FRAMES/STATE.md`: 654 simplified bars | Instance matrices/facing/seat depth must match each source opening; 285 is not a unique-type count. Approximate placement is not accepted geometry. |
| Ground terrain and finish contours | **Offline library** partition/heightfield/UV → **Headless** saved mesh/readback/render | HISTORICAL `jobs/GROUND-PROJECTION/STATE.md`; scripts `npm_mesh.py`, `npm_readback.py`, `npm_render.py` | v008 visual/Max acceptance open; authorized intermaterial boundaries are not generic manifold failures. Synthetic buildings do not validate terrain slope preservation. |
| GroundEl/MAF, Flora and architectural lights | **Offline library** approved asset selection/transforms → **Headless** placement/export; **Live** review as needed | POLICY `docs/domain/{npm-vpm,geometry,uv-textures}.md`; HISTORICAL `jobs/FACADE-SIGNS/STATE.md`, `jobs/WINDOW-FRAMES/BOX_LIGHTS_STATE.md` are partial attachment precedents | No general terrain/vegetation/MAF pipeline is established here. Alpha differs by profile; physical luminaires and separate Light FBX are different products. |
| Finish mapping, procedural texture tiles, atlas/UDIM UV | **Offline library** raster/phase/scale checks → **Headless** assignment/readback | CODE `technical_library/`; HISTORICAL `jobs/{OBR22-K02,UV-CONTINUOUS,FACADES-ATLAS,A-MAIN-ATLAS,WINDOW-ATLAS}/STATE.md` | ID ≠ slot ≠ UDIM; unknown finishes remain unresolved. Approved RGBA or 1254² study images are not compliant NPM atlases. Pixel readability still needs review. |
| Saved/reopened all-mesh topology and orientation | **Headless** extraction → **Offline library** `twinqa.geometry`, `mesh_audit`; native BMesh cross-check | CODE `src/twinqa/geometry/checks.py::check_orientation`, `technical_library/mesh_audit/{blender,core}.py`; HISTORICAL experiment reports above | Raw/evaluated/welded representations differ. Allowed boundaries and unjudged faces need explicit coverage reporting; zero boundary count is not the universal target. |
| UCX creation and independent collision QA | **Offline library** profile-aware hull/void planning → **Headless** realization/readback → manual passage review | HISTORICAL `jobs/{KPP1,PSU275}/STATE.md`; POLICY `docs/domain/{geometry,validation}.md` | Structural V010 budget checks do not prove convexity, closure, nesting, facade coverage or accessible passage widths. BVH surface crossings miss fully nested volumes. |
| Render/QA: source, master, final reimport, facade close-ups | **Headless** deterministic file render; **Live** user inspection, not scene-wide automated repair | CODE `tools/render_profile_comparison.py`; HISTORICAL `jobs/KPP1/STATE.md`, `jobs/MASHI-LP/STATE.md` | Fixed camera/engine/color management needed; GPU/version differences; front/oblique renders omit some surfaces. Images do not replace topology or V015–V017 signatures. |
| Editable Blender → Max working hand-off | **Headless** selection-only quad FBX + external images → `dcc_batch.py max` native import/save/re-export → independent Blender readback | CODE `tools/max_profile_roundtrip.py`; HISTORICAL `jobs/FACADES-ATLAS/STATE.md`, Max experiment | Map channel 1, per-face IDs, slot order, UV loops, normals, image bindings and local-origin precision need validation. Existing Max helper reports counts/material names, not this entire contract. |
| Final NPM/VPM exports and package checks | **Headless** derived profile export → **Offline library** ZIP/PNG/GeoJSON checks + fresh-process FBX readback | CODE `tools/blender/fbx_readback.py`, `src/twinqa/scene.py`, `tools/qa/validate_package.py`; HISTORICAL `jobs/ORCH-OBR22-NPM/STATE.md` | Package readback must use actual ZIP bytes. KPP1/PSU275 still need real delivery gates; diagnostic helpers/quad hand-off cannot leak into main delivery. |
| MSK placement, architectural acceptance, publication/Unreal/IFC | **Offline library** supplied metadata consistency; **Live** approved review only; no replacement for survey/user authority | POLICY `docs/domain/validation.md`; `docs/PROJECT_STATE.md`; `AGENTS.md` | No source evidence for an automatic CRS truth check, complete IFC production or Unreal acceptance in these Blender routes. Keep `not_run`/review and `delivery_passed=false`; publication is separate. |

### Production priority, not permission to remodel

`docs/PROJECT_STATE.md` places KPP1/PSU275 gate closure first. Their STATE files show export/readback/QA precedents, but incomplete GeoJSON, placement and manual acceptance. The K01 README records 6/9 historical checks and an engine parapet stop; the K02 README requests user-made source/etalon Max fragments. Do not synthesize these missing references. B03/B04 are planned regressions, not ready native fixtures. `jobs/OBJ03/STATE.md` explains the false confidence of 11/11 own checks; `jobs/GLB-NPM/STATE.md` explicitly stops tower modelling. `jobs/MASHI-LP/STATE.md` remains TRIAL with unresolved finishes and intersections. Use their failure modes to design synthetic controls, not their production assets as an implicit execution authorization.

## Proposed next tasks

Exactly three proposals below; no issues created. Each is a future experimenter's task, not executed here. Value/effort are relative S/M/L.

### Shared execution contract for E1–E3

1. Stage a new worktree-local `tmp/agr-blender-<card>/v001/` directory (`S`), copying B01/B02/B02t `spec.json`, `object.json`, `tolerances.json` and manifests first. Hash originals before/after; run builders against the copies. Copy any approved native etalon into `S` and validate its manifest hash; if absent, label engine-generated assets synthetic and do not claim native-etalon extraction coverage. `etalon.json` is a manifest, not mesh coordinates. Thresholds for geometry remain in copied `tolerances.json`; experiment-only targets below do not change standards.
2. Record executable/build/Python version, units, source hash, representation, camera/export settings, wall time versus in-DCC time, return code, full logs and artifact hashes. Use **3 repetitions**, distinct output paths, medians and ranges; separate startup/IPC from work. Preserve failed outputs. Print only a small result index over the live bridge; write full JSON to `S` to avoid the reported stdout cap.
3. The experimenter must inspect the current external wrappers before running: their files are outside this worktree and were not read here. Historical evidence supports `dcc_batch.py max --file ... --card ... --out ...` and `blender_exec.py --code ...`, not a verified `dcc_batch.py blender` subcommand. Preflight `dcc_batch.py --help` and the relevant subcommand help; qualify a Blender batch route before E1/E2 headless arms. If unavailable, report blocked and obtain a program-approved wrapper route; do not silently substitute a raw DCC launch. Do not claim the recipes below are already working commands.
4. For live work, acquire exclusive workflow ownership and confirm the intended ahujasid bridge/application/document/units. Use a disposable session or an explicitly authorized snapshot; opening/resetting a file in the artist's scene is not authorized by this proposal. Inventory objects, meshes, materials, images and collections before/after; clean only owned additions under the same ownership. On timeout/disconnect, preserve evidence and reconcile the in-flight operation before a retry.
5. Future payloads live under `experiments/bim-blender-agr/` in the experimenter's branch. They take configuration from `S/<arm>.json`, forward existing scripts' `sys.argv` explicitly (wrappers need not support argument passthrough), and return a compact manifest. These payloads/configs are to be implemented by that task; this research supplies protocols, not nonexistent tools described as installed.

Wrapper recipes (future execution only; `$BATCH`/`$LIVE` denote the program-provided `dcc_batch.py`/`blender_exec.py` paths):

```bash
# Preflight first; no wrapper was called by this research.
python "$BATCH" --help
# If help confirms Blender batch support, discover its exact --file/--out syntax.
# Each headless entry dispatches an existing repository script with explicit argv.
# Candidate shape ONLY, conditional on that discovered interface:
python "$BATCH" blender --card "$CARD" --file "$PAYLOAD" --out "$S/wrapper-r1.json"
# Live payload uses absolute fixture/result paths from its reviewed config:
python "$LIVE" --code "exec(compile(open(r'$PAYLOAD', encoding='utf-8').read(), r'$PAYLOAD', 'exec'), globals())"
# This Max form is recorded by the existing Max experiment:
python "$BATCH" max --card "$CARD" --file "$MAX_PAYLOAD" --out "$S/max-wrapper-r1.json"
```

### E1 — Twin build and saved/exported readback parity — value L / effort M

**Scope and value:** compare the same offline-generated B01/B02/B02t geometry through headless realization and a live data-API realization, then audit their saved `.blend` and FBX independently in fresh headless processes. This extends the earlier array/BMesh experiment across the persistence/export boundary and checks today's orientation implementation instead of reproducing its obsolete baseline. Future `prepare.py` consumes copied specs via `BuildInputs`/`build`; `batch_entry.py` dispatches `tools/export/export_mesh_blender.py` and `tools/source/measure_spec_blender.py`; `live_entry.py` builds only owned meshes/helpers without executing the exporter's scene-reset code in the artist session. Use `dcc_batch.py` for qualified headless stages and `blender_exec.py` for live stages. Batch status is a transport result, not the verdict.

**Measurements/decision:** 3 benches × 2 routes × 3 repetitions = 18 clean realizations, with 18 fresh saved-file and 18 FBX readbacks. Require matching face degrees/triangle counts, per-face material semantics and helper locations; geometry and silhouette checks must meet each copied tolerance set. Record raw versus welded counters and per-mesh `unjudged_meshes`; a scope gap remains review even if the numerical orientation result passes. Compare canonicalized invariants, not binary FBX hashes. Live is retained for this task only if it supplies otherwise unavailable unsaved data/review value; report its latency/ownership cost rather than impose a universal speed threshold.

**Negative controls:** generate one reversed facade, one consistently inverted decor component and one removed non-base facade face per benchmark: 9 defective copies × 2 routes × 3 repetitions = 54 defective realizations. Target detection 54/54, clean false positives 0/18. Missing-face detection uses an independent reference/allowed-boundary contract, not orientation alone. Rebuild triangles after changing polygons; the old fixture generator's flip variants change polygons without regenerating its triangle array, so do not blindly reuse it for an offline triangle checker. Include stale JSON, missing FBX and intentional script exception as three wrapper controls; each must remain an operation failure, not usable evidence. Outcomes determine whether a shared payload can serve both routes; they do not certify an AGR delivery.

### E2 — Reproducible render/QA packet, separate from user acceptance — value M / effort M

**Scope and value:** add a synthetic approved checker/brick pattern to derived B01/B02t fixtures (not the benchmark references), then produce master/reimport front and oblique images through `tools/render_profile_comparison.py` in the qualified `dcc_batch.py` Blender arm. Inspect the same saved copies through a short `blender_exec.py` payload in a disposable live scene; use a normal file render, not a viewport screenshot, with identical cameras/engine/settings. Do not execute the background-only script unchanged in live Blender. Future `render_batch_entry.py` forwards its config; `render_live_entry.py` reproduces the explicit render configuration and restores owned preview data. This tests whether saved evidence can replace repeated scene inspection without confusing source comparison with exporter parity.

**Measurements/decision:** 2 benches × 2 routes × 3 repetitions × 4 images = 48 expected PNGs. Verify dimensions, readable pixels, camera matrices, orthographic scale and image-input hashes in all 48 records. Pin engine, resolution, samples/seed where applicable, device, Blender build and color/view settings. Compare repeated images within each route first, then cross-route normalized RGB error and silhouette IoU. Pilot target: repeat/cross-route IoU ≥ 0.995 and mean absolute RGB difference ≤ 2/255 on opaque diagnostic renders on the same build/device; these are experiment thresholds, not facade-compliance rules. If build/device differs, split the version comparison and do not attribute the difference solely to headless/live. Report measured duration and UI occupancy separately. Source-approved facade overlays and user signatures remain a later gate.

**Negative controls:** per bench, generate a missing facade patch and a quarter-period UV shift: 4 defect variants × 2 routes × 3 repetitions = 24 render packets. Require the missing-patch silhouette/coverage probe to flag 12/12 and a direct UV phase/pattern-sampling probe to flag 12/12; an attractive image or aggregate RGB similarity cannot clear either. Check original fixture hashes and live inventory after each repetition. Rendering failure leaves the packet incomplete, not visually approved.

### E3 — Blender → Max → Blender semantic transport — value L / effort M

**Scope and value:** derive textured/material-bearing copies of B01/B02 (the geometry benchmarks themselves stay unchanged). Supply a synthetic finish→slot→UDIM/atlas mapping, explicit material objects, asymmetric UV landmarks, shared instance transforms, and a small external PNG set with hashes. Compare two explicitly distinct products: quad editable hand-off with embedded+external diffuse and map channel 1, and triangulated profile export copies (NPM embedded, VPM external/no texture paths). Future `export_entry.py` parameterizes the historical hand-off pattern instead of running its hard-coded job script; `max_entry.py` injects the absolute config expected by `tools/max_profile_roundtrip.py`, following the existing experiment's `maxOps.mxsCmdLineArgs` pattern, and adds per-face/UV/map-channel evidence. All Max operations use `dcc_batch.py max`; Blender export and fresh reverse-FBX readback use the qualified batch route. Live review through `blender_exec.py` is optional and is not the transport verdict. This addresses the previous Max prototype's lost material semantics, not another geometry-only timing comparison.

**Measurements/decision:** 2 benches × 3 products × 3 repetitions = 18 native Max imports/saves/reverse exports and 18 independent Blender readbacks. Require expected object names/counts, profile helper policy, material names/slot mapping, face-assignment area totals, map channel 1, image bindings/hashes, absence/presence of embedding by product, and geometry against copied tolerances on 18/18. Use stable synthetic face/UV landmarks or surface correspondence, not vertex order after triangulation. Pilot UV tolerance ≤ 1e-6 in normalized coordinates; report world deviation in metres and compare against benchmark tolerances. A source NPM/VPM material's physical pattern scale must agree across products; matching only UV-channel counts is insufficient. Compare smoothing/corner-normal behavior separately from geometric winding. Keep native Max reopening of saved `.max` files as an additional independent stage, not just the still-loaded import scene. The current `tools/max_profile_roundtrip.py` hard-codes `EmbedTextures=True` and exports all objects: E3 must parameterize these in its future experiment payload for VPM and profile helper filtering; invoking that helper unchanged cannot validate all three products.

**Negative controls:** for each bench inject one wrong face material assignment, one UV-channel swap and one missing texture: 6 variants × 3 repetitions = 18 defective imports, target 18/18 detected. Add a translated large-coordinate copy per bench (2 × 3 = 6 probes) to quantify float drift versus the local-frame copy; this is a diagnostic precision study, not permission to discard required NPM georeferencing. If native etalons are unavailable, report transport-only evidence on synthetic engine output. Missing CRS, Ground, GeoJSON, signatures and manual review keep `delivery_passed=false` regardless of semantic transport success.

## Open questions for the user

1. Which Blender build/bridge should the experimenter qualify for cross-route comparisons? Historical live results used 4.4/ahujasid, while the shared headless runner names 5.1.2; mixing them would confound route and version.
2. Does the program's current `dcc_batch.py` expose a Blender batch route, and can the experimenter use a disposable live session under exclusive ownership? Its external implementation is outside this worktree and cannot be certified by this card.
3. After synthetic E1–E3, which explicitly authorized production-copy follow-up has priority: KPP1 export-safety/gate closure, Ground Max import, or the outstanding SOSH editable hand-off verification? No OBJ03/GLB restart is proposed.
4. Are approved native B01/B02/B02t etalons available to stage, or should the first experiment explicitly cover engine-generated synthetic geometry only? K02 still waits for the user-made source/etalon fragment.

## Sources and verification limits

### External primary sources

The inherited draft records **HTTP 403** for the official HTML endpoints below; that HTTP observation was not repeated in this continuation. No claim of reading those HTML pages is made. This continuation retrieved and read relevant first-party raw-source passages for S1–S3 (HTTP 200): CLI argument order/background/exception exit, context-dependent operator polling, and module executable/signal boundaries. Upstream `main` is moving and is not evidence about the installed Blender build.

- **S1 — CLI:** https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html ; retrieved first-party CLI implementation: https://raw.githubusercontent.com/blender/blender/main/source/creator/creator_args.cc (argument-order text, background and Python exit-code handlers).
- **S2 — Operators/context:** https://docs.blender.org/api/current/info_gotchas_operators.html ; retrieved documentation source: https://raw.githubusercontent.com/blender/blender/main/doc/python_api/rst/info_gotchas_operators.rst (context-dependent `poll()` failures).
- **S3 — Module boundary:** https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html ; retrieved documentation source: https://raw.githubusercontent.com/blender/blender/main/doc/python_api/rst/info_advanced_blender_as_bpy.rst (empty `binary_path`, signal-handler differences).
- **S4 — FBX API reference, URL only / not retrieved:** https://docs.blender.org/api/current/bpy.ops.export_scene.html . Actual local export arguments in this report come from CODE reads, not an assertion that every installed build supports the current online API.
- **S5 — Render API reference, URL only / not retrieved:** https://docs.blender.org/api/current/bpy.ops.render.html . Local file-render capability is CODE evidence in `tools/render_profile_comparison.py`; no GPU/render runtime was tested.

Internal evidence is linked at each finding/matrix row. STATE files were surveyed across `jobs/*/STATE.md`; deep reads focused on current production, paused failures, Ground, openings and Max/UV transfer. Neither every historical job script nor untracked binary evidence was audited. No available background-agent tool was provided, so research was performed directly and no delegation is claimed. No files outside this worktree, external wrapper implementations or `docs/agr/` originals were opened. No code or existing reports were changed.

### Verification results for this continuation

- Before edits: evidence-honesty assertion **1 failed** on the inherited absent-report RED claim; runner tests **40 passed, 1 deselected**. No implementation failure was manufactured.
- After edits: embedded documentation suite **9 passed**; runner tests **40 passed, 1 deselected**.
- Full suite, once, with repository default `not blender and not dcc` marker selection (no native DCC):

  ```bash
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_8e4a9bd5
  ```

  Final line: **1 failed, 2013 passed, 9 skipped, 12 deselected, 1 warning in 250.27s (0:04:10)**.
  Failure: `tests/qa/test_from_spec_decor.py::test_a_corner_pilaster_passes_every_check`, with `orientation=1`. This is an unresolved current-suite finding, not evidence that documentation changed geometry; no implementation was edited or native benchmark rerun. Fixing it is outside this research-only card. E1 should retain this corner/decor case as a future diagnostic control rather than assume all current orientation checks are green.
- A first attempt to extract the embedded test block split on its own delimiter string and raised `SyntaxError` before tests ran. Extraction was corrected to split only once; this setup error is not counted as RED.
- Scope: one Markdown output only; no code, original reports, standards or production assets changed. No issues created. Wrapper qualification and all E1–E3 native measurements remain future work.

### Documentation regression probe

This executable documentation test stays inside the one allowed Markdown output (no test module outside `docs/research/`). It checks the research contract, not Blender correctness. Run from repository root; section parsing stops before this code block so the test cannot satisfy its own content checks. The inherited draft incorrectly claimed RED on an absent report although the report already existed. Before edits, the evidence-honesty regression below failed **1/1** on that claim; the existing runner tests returned **40 passed, 1 deselected**. This is a documentation correction, not an implementation regression. No absent-file baseline was simulated.

```bash
uv run python - <<'PY'
from pathlib import Path
import re, unittest
P=Path('docs/research/bim-blender-agr.md')
T=P.read_text(encoding='utf-8').split('### Documentation regression probe')[0] if P.exists() else ''
class ResearchContract(unittest.TestCase):
 def test_no_fabricated_absent_report_red(self):
  claim='On the unchanged repository the six tests fail ' + 'because the report is absent'
  self.assertNotIn(claim,P.read_text(encoding='utf-8'))
 def test_sections(self):
  for h in ('Summary','Findings (with sources)','How it applies to this repository','Proposed next tasks','Open questions for the user'):
   self.assertIn('## '+h,T)
 def test_summary(self):
  s=T.split('## Summary\n')[-1].split('\n## ')[0]
  self.assertTrue(5 <= sum(x.startswith('- ') for x in s.splitlines()) <= 10)
 def test_matrix(self):
  self.assertIn('| AGR task | Automation route',T)
  for route in ('**Headless**','**Live**','**Offline library**'): self.assertIn(route,T)
 def test_experiments(self):
  self.assertEqual(len(re.findall(r'^### E[123] —',T,re.M)),3)
  for key in ('dcc_batch.py','blender_exec.py','tolerances.json','3 repetitions','Negative controls'): self.assertIn(key,T)
 def test_evidence(self):
  for key in ('CODE','HISTORICAL','SOURCE','PROPOSAL','https://docs.blender.org/','HTTP 403','unjudged_meshes'): self.assertIn(key,T)
 def test_limits(self):
  for key in ('delivery_passed=false','C23','C25','not_run','No DCC was launched'): self.assertIn(key,T)
 def test_generated_bounds(self):
  for n in range(13): self.assertEqual(5 <= n <= 10,n in {5,6,7,8,9,10})
  for n in range(6): self.assertEqual(2 <= n <= 3,n in {2,3})
 def test_scope(self):
  import subprocess
  tracked=subprocess.check_output(['git','diff','--name-only','HEAD','-z']).decode().split('\0')
  untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z']).decode().split('\0')
  self.assertEqual(set(filter(None,tracked+untracked)),{P.as_posix()})
unittest.main(verbosity=1)
PY
```

Bounded invariant probes: summary length enumerates its bullet lines (8 within 5–10); experiment count enumerates E1–E3 (3 within 2–3); diff scope enumerates every changed/untracked nonignored file (target: this single report). Exhaustive finite probes: enumerate summary sizes 0–12 and proposal counts 0–5 against their inclusive bounds (13/13 and 6/6); enumerate all changed/untracked paths for the one-output/no-code-change constraint (1/1). External links/evidence labels are documentation checks, not universal truth proofs. E1–E3 numeric inequalities and failure targets are future probes with explicit denominators above; no native N/N result is claimed for them. Original-input immutability, live ownership and delivery nonacceptance remain execution policies to verify in those experiments, not guarantees proven by a green documentation test.
