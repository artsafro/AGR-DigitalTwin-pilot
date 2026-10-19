# 3ds Max for AGR: route selection and remaining delivery evidence

Card: `t_4493dee7`; repository snapshot: `3cfea95`; branch: `docs/research-bim-3dsmax-agr`.
Scope: research only, approximately 60-minute planning timebox, not a measured duration.
This extends [3ds Max scripting research](3dsmax-scripting.md): it does not repeat its CLI/API catalogue, licensing survey or secondary-format comparison.

## Summary

- Prefer bounded headless Max jobs for repeatable intake/export, live MCP for targeted inspection, and existing offline libraries for texture generation and array-based QA.
- `pymxs` is the in-Max execution API, not a competing transport; batch and live routes still require separate lifecycle controls.
- A committed Max 2026 experiment already supports geometry-only batch roundtrips; it does not establish textured NPM/VPM readiness.
- The same experiment exposes a critical distinction: imported material-bearing FBX retained IDs, but constructing meshes with face IDs alone lost their semantics on export.
- `FACADES-ATLAS` records a live transfer preserving corner UVs; its quad handoff and diffuse assets are not an AGR delivery profile.
- New upstream inspection found that MCP `scene_qa` explicitly excludes topology, normals and UV, while `inspect_mesh` reads a capped base cage.
- Test profile-aware material/UV survival and failure detection next, rather than repeating startup-speed or unconfigured OBJ experiments.
- No DCC was installed, started or contacted for this research; proposed experiment runtimes and outcomes are **not tested**.

## Evidence and method

Labels used below:

- **LOCAL-CODE**: inspected tracked implementation, not executed here.
- **LOCAL-REPORT**: inspected tracked report/data; historical measurements belong to their original experiment, not this research. Ignored binaries and external workstation installations were not revalidated.
- **SOURCE**: fetched primary documentation or pinned upstream source over HTTPS during this task; a source/API claim, not installed-host verification.
- **PROPOSAL**: engineering recommendation, acceptance target or estimate; not a regulation or measured result.

Relevant reading included `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/agents/WORKFLOW.md`, `docs/agents/CAPABILITIES.md`, `benchmark/README.md`, K02's brief, domain geometry/material/UV/export/validation/conflict documents, `jobs/FACADES-ATLAS/STATE.md`, `jobs/UV-CONTINUOUS/STATE.md`, `jobs/OBR22-K02/STATE.md`, and production context in KPP1/PSU275 states. Existing research and experiments are cited at the findings they inform. Large JSON evidence was inspected by relevant sections and parsed summaries, not treated as independently reproduced native output.

The run policy limits access to this worktree. Consequently the external coordination file, installed MCP checkout and `dcc_batch.py`/`blender_exec.py` implementations were not read. Wrapper invocation shapes below come from committed experiment reports, not a claim about their present installed versions. No background-agent tool was available; research was performed directly. Exactly one tracked document is added. The research-writing run did not publish; publication is performed by the driver after review. No issue or hand-written Agent trace was created. `WORKFLOW.md` requires the publication trace to be generated, not invented.

## Findings with sources

### 1. Intake of a digital twin is a semantic contract, not just import success

**LOCAL-REPORT/CODE.** Here “twin import” means intake of source/engine geometry into Max for measurement, working handoff or delivery preparation. It does not assert a dedicated product named Twin Import or a new IFC/BIM importer. `tools/max_profile_roundtrip.py` imports FBX into an initially empty batch scene, saves a new MAX and exports FBX. It records hashes and shallow counts, but neither verifies its own export nor preserves a complete BIM mapping by contract.

The historical experiment [max-headless-agr-roundtrip](../experiments/max-headless-agr-roundtrip.md), together with `experiments/max-headless-agr-roundtrip/evidence.json`, `native_job.py` and `checker-results.json`, adds evidence missing from the earlier research:

| Historical arm | Observed in committed evidence | What it does not establish |
|---|---|---|
| Existing tool, copied B01 etalon FBX | 12 exports; fresh native readback has IDs `[1,6,11,21]` and 9/9 geometry checks each | UV, PNG embedding, allowed shaders, production acceptance |
| Engine arrays → native mesh → FBX | B01/B02 retain geometric counts, but prototype returns ID `[1]`; 7/9 checks | Semantic equivalence or a working delivery bridge |
| One job/process vs three jobs/process | Recorded medians 41.5 s/job vs 72.7 s/three-job batch; reported 1.713× per-job gain | Current performance, large-scene scaling, live MCP speed |

`native_job.py:create` sets face IDs but creates no material objects or UVs. This explains why a geometry-preserving transport can fail `opening_planes` and `mesh`: roof/opening classification depends on material semantics. Assigning IDs is not equivalent to constructing a valid material graph. Do not generalize that Max always loses IDs; the imported-FBX arm is a counterexample.

**PROPOSAL.** An intake manifest should bind source hash, source object/element identifiers, local/world matrices, expected dimensions, face-finish provenance, material table, helpers and asset dependencies. Preserve semantic IDs in a sidecar and verify their correspondence after import; do not assume FBX carries arbitrary attributes. Benchmark `LEVEL_*` helpers belong to extraction/checking, not final main delivery FBX. `docs/domain/export-import.md` and `materials.md` already separate internal finish IDs, material slots and UDIMs.

**LOCAL-REPORT.** `jobs/OBR22-K02/STATE.md` records Revit FBX without Material nodes and matrices carrying the feet conversion factor; names and source IDs required recovery. Native Max import cannot, by itself, recover missing finish assignments. Current `PROJECT_STATE.md` keeps `from_source` experimental after the unsuccessful OBJ03 result; this report proposes no bypass or resumption.

### 2. Facade/texturing: reuse the math; test the Max boundary

**LOCAL-CODE.** `tools/facades_texture_pattern.py` is NumPy-only. Its historical default panel dimensions differ from v005: pass `(1.2, 0.6)` for ID101 and `(0.6, 1.2)` for IDs102–105 explicitly. `technical_library/texture_tiles` already reuses this raster via `metric_pattern`; a second Max-specific procedural generator would duplicate tested logic.

**LOCAL-REPORT.** The only matching `jobs/FACADES-*` state found is `jobs/FACADES-ATLAS/STATE.md`. It records three transferred meshes, IDs101–105, 15 accessible bitmap references on channel 1, and reverse-FBX checking of 59,912 polygons / 239,948 corners with maximum UV error zero. The reported world-position error reaches 0.489 mm at large coordinates. These are historical job claims: the ignored MAX/FBX and native QA JSON were not available for reinspection. Tracked `v005-package-verification.json` does provide hashes and dimensions for three atlases plus five shared maps, all 2048²; it does not prove current native bindings.

**LOCAL-CODE.** Despite their names, `tools/export_facades_max.py` and `tools/check_facades_max_roundtrip.py` run in Blender. The exporter strips other UV layers in memory, renames the selected meshes and writes a **non-triangulated, non-embedded** FBX plus external PNGs. Never run it in an artist's working session. The comparator checks polygon counts/degrees and finds corner UV matches among positions within 2 mm; it does **not** enforce bijective corner correspondence, compare face IDs, validate normals or inspect embedded bytes. Its UV threshold `<2e-6` and 2 mm search radius are comparator settings, not universal regulatory tolerances.

**PROPOSAL.** Keep metric texture/atlas generation offline; use Max to verify map channel, UV seams, face-to-finish mapping and native appearance. Export a derived triangulated copy only after preserving and checking the editable master. Keep physical repeat/phase comparisons separate from corner-UV roundtrip comparisons: unchanged UV does not prove the intended material size or finish.

`jobs/UV-CONTINUOUS/STATE.md` records a user-accepted UV stage but no confirmed native Max import. Its 20 px padding on 4096 maps remains a delivery concern under `docs/domain/conflicts.md` C29, not a precedent for overriding VPM padding. `jobs/OBR22-K02/STATE.md` likewise retains ID0/PBR/export gaps despite partial visual acceptance. Do not infer blanket compliance from either case.

### 3. FBX profile settings need artifact-level evidence

**SOURCE.** Autodesk documents `EmbedTextures`, `ConvertUnit`, `Triangulate`, `UpAxis`, `PushSettings`/`PopSettings` and `ResetExport`; the latter loads the Autodesk Media & Entertainment preset, not an AGR preset [S3]. Its published `FileVersion` table still ends at `FBX201300` [S3]. **LOCAL-REPORT:** the newer committed experiment reads back `FBX201400` from the Max 2026 exporter and independently reports binary 7400 with metre units. This closes the earlier research's uncertainty for that specific install/run, not every Max/plugin release.

The following requirements are **local domain rules**, sourced from `docs/domain/export-import.md`, `uv-textures.md`, `materials.md`, `geometry.md` and decided items in `conflicts.md`; they are not inferred from Autodesk defaults:

| Requirement | NPM | VPM | Missing evidence at the Max boundary |
|---|---|---|---|
| FBX | Binary 7400; metres; triangulated export copy | Same | Header alone cannot prove dimensions or transform correctness |
| Texture transport | Embedded PNG; texture names agree | External PNG; texture paths removed from FBX materials | `EmbedTextures=False` alone does not remove saved paths |
| Maps | RGB/no alpha; separate opacity when needed; no normal per D014 | Diffuse + ERM + DirectX Normal; profile alpha rules | Correct channel wiring/byte payloads not established by geometry experiment |
| Layout | Atlas, physical finish scale preserved; no NPM-OKS Ground-density gate | One UV channel; sequential 1001–1100; profile density/padding | UV retention is not a density, phase or padding check |
| Placement | Moscow project coordinates/heights | Local origin/shared pivot; MSK-77 placement in GeoJSON | Large-coordinate precision, pivot and georeference still need independent controls |
| Scene | Allowed meshes/materials; no working helpers/modifiers | Single default layer; separate Light FBX | Benchmark helpers must not leak into delivery |

**LOCAL-CODE.** `tools/max_profile_roundtrip.py` hardcodes `EmbedTextures=True`, does not set `ConvertUnit`/`Triangulate`, does not load/check the plugin explicitly and does not read parameter getters. Thus its successful use is not evidence of a profile-aware exporter. `adapters/max/README.md` still calls the adapter unimplemented; reconcile its historical “no export/import” wording with the later experiment rather than equating an experimental tool with a shared adapter.

**PROPOSAL.** Explicitly load the plugin, apply an allowlisted profile, record setter results plus getters, and read the resulting FBX/PNG package independently. Use fresh processes to isolate settings; if live export is later authorized, preserve/restore exporter settings in `finally` using documented controls [S3], while separately restoring scene state. Neither `PopSettings` nor Undo substitutes for asset preservation.

### 4. Which checks belong in batch, live MCP and offline code?

**SOURCE.** Batch executes a supplied Python/MAXScript script, optionally loads a scene and exits [S1]. `pymxs` scene access cannot run in Python worker threads; `mxstoken` is deprecated/nonfunctional [S2]. Therefore thread pools are not a route to concurrent native QA; prefer external orchestration and serialized scene access (**PROPOSAL**).

**SOURCE.** At pinned upstream commit `bcd4e4c6e8e674b48bf9904f58aef708a93a9dca`, `scene_qa` explicitly excludes mesh, topology, normals and UV. It scans names/transforms/hierarchy/frame metadata; deterministic fixes currently cover name collisions/empty names, with an optional expected scene sequence [S4]. `inspect_mesh` inspects the Editable Poly **base cage**, rejects other base types, caps a request at 1–1000 components and reports truncation [S5]. Do not call either a full AGR checker, or silently convert a master to accommodate inspection.

**SOURCE.** The pinned MCP client defines `RequestOutcomeUnknown` for lost responses after dispatch and `DialogBlocked` for still-running calls held by a modal dialog [S6]. A client timeout is not evidence of rollback. Inspect outcome before retrying a mutation (**PROPOSAL**). This research fetched upstream code, not the installed binary: host correspondence remains unverified.

**LOCAL-REPORT.** `CAPABILITIES.md` lists Max MCP as CONFIGURED, not live-scene validated, despite the earlier facade state reporting a successful live transfer. Preserve both evidence scopes; one case is not current general capability certification. [MCP bridge research](mcp-dcc-bridges.md) documents the transport/lifecycle design. The [multi-agent experiment](../experiments/mcp-dcc-bridges.md) measured lease benefits on **Blender**, not Max; a Max workflow lease remains a proposal, not a verified feature.

**LOCAL-CODE.** `technical_library/mesh_audit/core.py` supplies offline topology diagnostics; its README excludes inter-object overlap, full contour preservation, shader and density checks. [Blender mesh-audit experiment](../experiments/blender-mesh-audit-live.md) reports counter parity on synthetic fixtures, not arbitrary Max scenes. `src/twinqa/scene.py` implements selected scene gates, not V001–V017 in full: transforms, triangulation/counts, embedding indication, UV/mirroring, pivot and UCX budget. UCX shape/coverage and georeference remain explicitly unrun there. `src/twinqa/fbx_header.py` only checks header/version. Full package validation still needs `tools/qa/validate_package.py`, actual exported-file readback and signed manual gates under `docs/domain/validation.md`.

**LOCAL-REPORT.** Historical batch results also include native exit `-130` on successful jobs due to an installed startup plugin exception; the wrapper classified this as a warning. This is not a reason to accept all `-130` failures: require fresh logs, job-specific completion evidence, output hashes and readback. Reused listener-log filenames can retain stale text. Do not disable security or plugins to improve a reported success rate.

## AGR task → route → evidence → open risks

Routes are recommendations, not claims of production readiness.

| AGR task | Preferred route | Evidence | Open risks / stop conditions |
|---|---|---|---|
| Measure source MAX/FBX and extract twin geometry | Headless `pymxs`; live only for ambiguous visual/source context | Existing batch tool + B01/B02 experiment; S1/S2 | Missing XRefs/maps/plugins, units, incomplete BIM provenance; stop on missing dependencies |
| Build engine-array mesh in Max | Headless, experimental | `native_job.py`; FBX prototype 7/9 | Material graph absent, ID loss; must restore semantic parity before adoption |
| Metric facade raster/atlas | Offline library | `facades_texture_pattern.py`, `technical_library/texture_tiles` | Defaults are historical; ID0, module sizes, seam phase and readable joints need explicit configuration |
| Inspect facade UV/materials in native Max | Live MCP targeted read-only; batch full extraction | FACADES state; S4/S5 | Base vs evaluated geometry, truncation, missing bitmap/channel data, current capability unverified |
| Prepare NPM/VPM delivery copies | Headless profile job, then independent readback | Domain export rules; historical FBX201400 getter | Current tool is embedding-only; VPM path stripping/ERM/Normal unproved |
| Diagnose scene naming/transforms | Live `scene_qa(scan)` on owned copy, or batch inventory | S4 | Metadata scan is not topology/UV QA; no automatic fixes in research scope |
| Topology/UV numeric regression | Offline library on complete dumps; batch extraction | Mesh-audit code and Blender parity report | Intentional boundaries; no universal overlap/normal-quality proof |
| Check packed FBX + PNG + GeoJSON | Offline validator + clean DCC readback | `twinqa`, `validate_package.py` | Unimplemented gates, cross-DCC normal/material conversions, manual reviews |
| Compare architectural appearance | Human review of fixed-camera native views on copies | Validation domain and facade job limits | Numeric pass cannot sign V015–V017 or infer source/material approval |

## How it applies: concrete repository boundaries

1. **Intake/extraction:** keep `src/dt_ai/spec/` and `src/dt_ai/geometry/from_spec.py` as the spec/build chain; add Max extraction only behind an adapter contract. Preserve `benchmark/*/tolerances.json` as geometry thresholds. K02 awaits user-provided `source.max`/`etalon.max`; do not manufacture replacement “etalons” from the engine.
2. **Facade work:** reuse `tools/facades_texture_pattern.py`, `tools/update_facades_600x1200.py` and `technical_library/texture_tiles/`; retain `jobs/FACADES-ATLAS/` manifests and correspondence. Generalize the existing Blender handoff/comparator only after a second-fixture test, not by assuming their names imply native Max code.
3. **QA:** share array diagnostics in `technical_library/mesh_audit/`; put Max-specific scene extraction in a future `adapters/max/` implementation. Keep package checks in `src/twinqa/` and `tools/qa/`, not embedded in a live MCP tool list.
4. **Evidence:** reuse the schema ideas, not pinned scratch constants, from `experiments/max-headless-agr-roundtrip/`. Its `prepare.py` reads an external fixture location and overwrites a tracked evidence file; **do not run it unchanged for a new experiment**. Copy/reparameterize the harness in the experimenter's own task first.
5. **State:** no changes to `docs/PROJECT_STATE.md`, capabilities, locked standards or production jobs in this research. A shared Max adapter needs its own implementation/evidence task and capability registration on main.

## Measurable experiments for the experimenter

All three are **PROPOSALS; native runtime not tested here**. Effort/runtime budgets below are estimates, not measurements. Existing wrapper call forms are documented in [Max experiment](../experiments/max-headless-agr-roundtrip.md) and [Blender session experiment](../experiments/blender-exec-session.md); the wrappers are external prerequisites, not repository files.

### Common protection and execution contract

- Separate experiment card/worktree; authorized, licensed DCC and one owner per host/session/export root. Read the applicable DCC skill and external coordination rules before any execution. Confirm wrapper CLI with its current help; do not bypass its lock or call native executables directly.
- Create a fresh run root **inside that worktree**, e.g. `experiments/bim-max-agr/local/<unique-run>/`; reject existing destinations. Copy benchmark JSON, tolerances and available hash-matching FBX from the approved fixture location. All subsequent reads use copies; never write into `data/` or `benchmark/`.
- Verify original/copy SHA256 before running and original SHA256 afterwards. Create scripts/configs/exports/logs only under the new root. Preserve a readonly reference copy and a separate mutation copy. User/approved scenes are never opened on write or reset.
- Batch starts with zero objects and empty document name; only private-session cleanup is allowed. Live Blender requires an explicitly reserved disposable scene; if an artist scene is open, stop. Snapshot datablocks and clean only owned additions under a whole-workflow lease; never perform scene-wide diff cleanup without exclusive ownership.
- Record DCC/plugin/Python versions, units, per-job completion markers, fresh log paths, raw times, hashes and mandatory/not-run checks. Large arrays go to files with hashes, not bridge stdout: the historical `blender_exec` experiment found a 20 KB output truncation hazard.

**Execution templates, not commands executed here:** PowerShell variables `$WT`, `$RUN` and `$WRAPPERS` are absolute authorized paths; `$WRAPPERS` is the operator's coordination-approved wrapper directory. Files named below are **small harness scripts to implement on the experiment card**, not scripts supplied by this research. Each reads a `config.json` beside itself (using `__file__` in batch); configuration contains only absolute copied-fixture/output paths. Scripts must refuse overwrites. The wrapper need not support extra script arguments.

```powershell
# E1/E2 native stages; separate calls and new evidence files per repetition.
python "$WRAPPERS/dcc_batch.py" max --card <experiment-card> --file "$RUN/e1_native.py" --out "$RUN/e1-wrapper.json"
python "$WRAPPERS/dcc_batch.py" max --card <experiment-card> --file "$RUN/e2_export.py" --out "$RUN/e2-wrapper.json"
python "$WRAPPERS/dcc_batch.py" max --card <experiment-card> --file "$RUN/e2_readback.py" --out "$RUN/e2-readback-wrapper.json"
# Independent Blender stages, in a reserved disposable session only.
# exec uses an explicit globals dict because bridge execution need not define __file__.
python "$WRAPPERS/blender_exec.py" --code "p=r'$RUN/e2_blender.py';exec(compile(open(p,encoding='utf-8').read(),p,'exec'),{'__file__':p})"
python "$WRAPPERS/blender_exec.py" --code "p=r'$RUN/e3_blender.py';exec(compile(open(p,encoding='utf-8').read(),p,'exec'),{'__file__':p})"
```

`blender_exec.py` is a Blender route, **not** a Max MCP client. None of these commands verifies live `3dsmax-mcp`; the optional read-only Max arm below requires a separately authorized MCP session. If unavailable, report it `not_run`, without substituting raw sockets or UI automation.

### E1 — Restore material semantics, not just mesh positions

**Question:** does an explicit Standard/Multi-Sub material table prevent the semantic loss observed in the geometry-only prototype?

- Inputs: copied B01 and B02 `object/spec/etalon/tolerances` and etalon FBX. Build baseline engine arrays through the existing `from_spec` API, not handwritten specs.
- Implement `e1_native.py` from the logic of `native_job.py`, with no inherited scratch constants. Arm A reproduces face-ID-only mesh creation. Arm B adds named material objects and explicit face-ID-to-submaterial mapping. Export FBX with getter-confirmed settings; read each output in a separate clean batch call before comparing offline.
- Three repetitions per fixture/arm: **12 output FBXs**. Record geometry-check statuses, face-ID histograms and area-weighted finish correspondence, helper preservation, bounds and sampled surface deviation. Report sample count/definition; do not describe sampled distances as certified Hausdorff bounds.
- **Proposed acceptance:** Arm B restores all 9 benchmark checks on both fixtures, exact intended ID/face correspondence for unchanged tessellation, and no regression versus the baseline under copied tolerances. Arm A's failures remain visible. Source hashes unchanged, no output reused. Missing fixture or material API incompatibility blocks that arm, not a fabricated pass.
- Effort estimate **M**; execution allowance **20 minutes after harness preparation**, not measured. No UV/delivery claim from E1 alone.

### E2 — NPM/VPM texture contract across Max and Blender

**Question:** do profile differences survive actual FBX bytes and clean reimport?

- On copies of B01/B02 engine geometry, add **synthetic** metric facade textures using the existing raster, explicit finish mapping, one UV channel and seam probes. Keep a quad master; export triangulated derivatives. NPM uses an RGB atlas with embedding; VPM uses sequential external Diffuse/ERM/DirectX-Normal tiles and stripped material paths. Synthetic ERM/Normal are diagnostic maps, not invented production finishes.
- `e2_export.py`: load plugin, set/get explicit profile values, export both profiles. `e2_readback.py`: fresh native reimport, dump corner XYZ/UV/IDs, texture nodes/channel references and embedded/external status. `e2_blender.py`: independent import of the same files, plus inspection of binary texture payload/references; never “prove” embedding by a successful import that can resolve an external file.
- Three repetitions × two fixtures × two profiles = **12 outputs**. Pair triangle corners bijectively by geometry and finish, not the legacy comparator's unrestricted nearest-neighbour reuse. Compare IDs/areas, UV error, physical repeat/phase at named seam points, PNG SHA/mode/size, missing maps, absolute path leakage and 7400 header.
- **Proposed acceptance:** zero wrong finish assignments, zero missing maps/path-policy violations, header 7400 for every output, UV maximum error `<2e-6` as a trial engineering target (not a regulation), no new winding defects; repeat/phase and XYZ budgets declared before running. Tamper controls: wrong bitmap channel, disabled embedding and one leaked absolute VPM path must each be detected. Record NPM world-placement/georeference and whole-package/manual checks as unrun unless explicitly exercised.
- Effort estimate **M**; execution allowance **30 minutes after harness preparation**, not measured. A synthetic profile-component pass is not acceptance of an OKS delivery.

### E3 — Determine checker coverage without mistaking metadata QA for topology QA

**Question:** do complete native dumps and offline diagnostics detect the same deliberately introduced defects?

- Copy B01/B02/B02t JSON inputs; generate baseline engine meshes and four mutation copies each: one reversed quad, one deleted quad, one corner duplicated 0.5 mm away, one bowtie quad. Reuse the fixture logic from `experiments/blender-mesh-audit-live/`, reparameterized to read copied inputs; never edit etalons/specs.
- Run the same `technical_library/mesh_audit/core.inspect_mesh` offline and on arrays extracted by `e3_blender.py`. Add an `e3_native.py` batch extraction through the E1 wrapper form to determine whether Max conversion changes topology/IDs. Preserve base polygons for this comparison; do not compare triangulated and quad counters as though identical.
- **15 cases**, three repeats/path. Record detection matrix, clean false positives, counter differences, boundary deltas, extraction/compute/whole-call times separately. **Proposed acceptance:** zero unexplained parity mismatches, zero newly introduced winding/near-duplicate/bowtie findings on clean fixtures, expected detection of those three mutations; deletion must be recognized against reference boundaries, not an absolute zero-boundary rule.
- Optional authorized **live Max MCP** arm: reserve a copied scene, select/confirm target PID/document/units/version, run `scene_qa(action='scan')`, then targeted `inspect_mesh(capture=False)` over explicit base Editable Poly nodes with complete pagination/filter accounting. No fixes, resets, conversion or security changes. Compare reported fields with batch extraction; mark unsupported UV/topology checks **not covered**, not pass. Record if a capped response is incomplete. This arm tests coverage, not claims of equivalence for fields the tool never returns [S4–S5].
- Effort estimate **M**; execution allowance **20 minutes after harness preparation**, not measured. Stop if live ownership cannot be secured; retain valid offline/batch results with live `not_run`.

## Proposed next tasks

All value/effort ratings are **estimates**; these are proposals, not newly created issues.

1. **Max: pin an authorized execution/evidence contract** — Value **L**, effort **S**. Confirm supported Max/plugin version, entitlement, fixture availability and output ownership; reconcile adapter/capability documentation with historical experiment evidence. Require wrapper version/help, fresh logs, unknown-outcome stop handling and no artist-scene access. This removes execution ambiguity before any native follow-up.
2. **Max intake: preserve material semantics through engine-array FBX** — Value **L**, effort **M**. Execute E1, then implement only the verified material/provenance mapping behind the adapter boundary with negative tests and independent readback. Preserve the current engine and offline diagnostic library; do not build a daemon or reimplement geometry generation.
3. **AGR export: prove NPM/VPM texture and placement separation** — Value **L**, effort **M**. Execute E2 and package its artifact-level checks as profile-aware export/readback evidence, including bitmap channels, embedding vs path stripping, finish correspondence and source-preserving triangulation. Keep unresolved georeference and manual gates explicit.
4. **QA: compare complete dumps before expanding live MCP use** — Value **M**, effort **M**. Execute E3, establish a common array contract and defect coverage table, then add only missing extraction glue. Reserve live Max for source/visual ambiguity and targeted debugging; do not port already equivalent pure-Python checks into many small MCP calls.

## Open questions

- Is “twin import” intended to include a particular third-party importer? No such product is assumed here; the scoped route is FBX/MAX/engine-array intake.
- Which Max and FBX plugin build is the supported target? Historical evidence is Max 2026.3; K02 requests Max 2024 assets, which are still blocked in project state.
- Are hash-matching B01/B02 FBXs and the approved facade source available to the experimenter? Tracked metadata is not a binary backup; the facade job cannot be reproduced from a clone alone.
- What approved control points and error budget should govern NPM world-coordinate publishing versus local-frame VPM? Do not silently choose unresolved CRS/pivot behavior from tool defaults.
- Who owns the live Max/Blender sessions for follow-up, and is a workflow-wide lease actually available? Blender-only lease results do not establish Max isolation.
- Who signs finish mapping, ID0 resolution, PBR sources and visual acceptance? Neither synthetic maps nor successful Max import supplies those decisions.

## Validation performed in this research

No native runtime tests or performance measurements were made. The required ordinary project test command was run; `pyproject.toml` excludes `blender` and `dcc` markers by default:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_4493dee7
```

Final line: **`1 failed, 1910 passed, 2 skipped, 12 deselected, 1 warning in 190.07s (0:03:10)`**.
Failure: `tests/qa/test_from_spec_decor.py::test_a_corner_pilaster_passes_every_check`, assertion finding `('orientation', 1)`. This was run before adding the report; no production code was changed or repaired in this research. It is not a Max experiment result.

## External source ledger

All seven requests returned HTTP 200. Documentation was converted to text and inspected for the cited parameters/behavior. Pinned upstream `scene_qa.py` was read in full; `mesh_ops.py` inspection covered `inspect_mesh`, not the whole modeling module; client inspection targeted selection, transport and failure paths. None was executed.

- **[S1] Autodesk, 3ds Max Batch command line:** https://help.autodesk.com/cloudhelp/2023/ENU/3DSMax-Batch/files/GUID-48A78515-C24B-4E46-AC5F-884FBCF40D59.htm
- **[S2] Autodesk, Python threading:** https://help.autodesk.com/cloudhelp/2026/ENU/MAXDEV-Python/files/MAXDEV_Python_threading_html.html
- **[S3] Autodesk, FBX exporter parameters:** https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/FBX-Import-and-Export-Dialog/GUID-54B1F140-B304-48A2-9829-C68B345E2044.html
- **[S4] Pinned MCP scene QA implementation:** https://github.com/cl0nazepamm/3dsmax-mcp/blob/bcd4e4c6e8e674b48bf9904f58aef708a93a9dca/maxmcp/tools/scene_qa.py
- **[S5] Pinned MCP mesh inspection implementation:** https://github.com/cl0nazepamm/3dsmax-mcp/blob/bcd4e4c6e8e674b48bf9904f58aef708a93a9dca/maxmcp/tools/mesh_ops.py
- **[S6] Pinned MCP client failure/target handling:** https://github.com/cl0nazepamm/3dsmax-mcp/blob/bcd4e4c6e8e674b48bf9904f58aef708a93a9dca/maxmcp/max_client.py

Six distinct source URLs; `scene_qa.py` was fetched twice (targeted discovery, then full inspection). No claim about current licensing rights, installed runtime health or unsupported import formats is inferred from these sources.
