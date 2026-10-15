# Revit for AGR: live evidence capture, offline IFC and delivery synthesis

Research card `t_d7aac992`; no GitHub issue. Repository baseline: `3cfea95b5af7f65aec3b9c1e339f4fb07e37f491`.
Estimate before discovery: medium, 45–60 minutes. This is an extension of [revit-api-automation.md](revit-api-automation.md), not a replacement API survey.

## Summary

- Keep live Revit for authoritative RVT inspection, missing semantics, linked-model diagnostics and controlled source exports; do not keep it occupied for mesh QA.
- KPP1 already separates live capture from offline TwinPack parsing and delivery construction; prioritize making that boundary reproducible.
- IFC is a candidate **offline intake snapshot**, not an implemented replacement for our Revit extractor or an editable-RVT round trip.
- Distinguish storeys/levels, structural floor slabs and AGR inset plates: they are three different contracts.
- KPP1 “groups” are export selections of element IDs, not evidence of native Revit Model Groups; preserve selection provenance outside delivery hierarchies.
- Public `revit-mcp`, local `revit-bridge`, `revit-http-2025` and broken `revit-twin` are not interchangeable connectors.
- Share a Revit session by exclusive workflow ownership across both HTTP and pipe aliases, then fan out immutable snapshots to offline workers.
- Run two proposed experiments: IFC semantic/geometry loss accounting, and group/provenance preservation through saved-file transport; neither requires Revit.
- No model acceptance, capability-registry update or issue creation is implied; K01 and the existing delivery/manual gates remain open.

## Findings with sources

### Evidence classes and scope

**READ-LOCAL** means files/code inspected in this worktree. **HISTORICAL-RUN** means a previous report records execution; it was not repeated here. **READ-WEB** means public text/code fetched successfully over HTTPS in this card, not runtime verification. **SOURCE-CLAIM** means the author/vendor advertises behavior, even when its documentation was read. **PROPOSED** denotes recommendations and experiment thresholds, not established capabilities.

Read first: `AGENTS.md`, `docs/PROJECT_STATE.md`; then `docs/domain/{geometry,npm-vpm,export-import,validation,conflicts,sources}.md`, the relevant patterns, every `jobs/*/STATE.md`, and `benchmark/README.md`. Coordination basis: `docs/agents/WORKFLOW.md` (Permission matrix, asset preservation, DCC authorization), `docs/agents/CAPABILITIES.md`, and the sharing report/experiment below. No separate coordination file was found by the filename scan. External workstation scripts/configuration were **not** opened: the worktree-only boundary applies to this research too.

No Revit/Blender/Max/AutoCAD application was explicitly launched or installed for the research, and no cloud WorkItem or IFC execution was performed. Public sources were retrieved with Python's standard-library HTTP client. The mandatory harness test run is recorded at the end; it is not bridge evidence.

Existing reports retained as dependencies rather than repeated:

| Existing evidence | What this card adds |
|---|---|
| `docs/research/revit-api-automation.md` | Task-level route choices, slab/storey distinction, actual KPP1 group semantics, executable experiment contracts. No repeat of the pyRevit/Dynamo/APS introduction. |
| `docs/research/mcp-dcc-bridges.md`, `docs/experiments/mcp-dcc-bridges.md` | Revit-specific handoff boundary, both aliases plus direct TwinPack client under one owner. Previous Blender lease result (13/36 torn readbacks → 0/36) is **HISTORICAL-RUN**, not a Revit result. |
| `docs/experiments/blender-exec-session.md` | Require compact stdout, file artifacts and quarantine after unknown outcomes; do not repeat latency/lock experiments. |
| `docs/experiments/{blender-bpy-automation,blender-mesh-audit-live,scripts-logic}.md` | Reuse independent readback/orientation checks; no new generic mesh-audit comparison. Their results describe earlier revisions, not necessarily current checker behavior. |
| `docs/experiments/max-headless-agr-roundtrip.md` | Test source-group semantics, not another startup/batching benchmark. Prior geometry-only FBX prototype lost material IDs and achieved 7/9, despite small coordinate error. |
| `docs/experiments/acad-coreconsole-agr-plans.md` | Adopt its distinction between committed spec proxies and independent binary etalons; do not equate serialization parity with architectural correctness. |

### 1. Execution routes: do not call every non-interactive request “headless”

- **Live Revit:** Autodesk documents `ExternalEvent.Raise()` followed by execution in an available Idling cycle [W1, READ-WEB]. KenLP documents queued HTTP requests dispatched through that mechanism [W2, SOURCE-CLAIM]. A terminal/MCP caller does not remove the desktop host dependency. A completed transaction is not proof that an RVT was saved/reopened.
- **Headless native Revit:** Autodesk advertises its cloud Automation API as the Revit engine with DB API access, without a desktop installation [W3, SOURCE-CLAIM]. This is a separate cloud deployment, **not** a `dcc_batch.py revit` mode established by our repository. No local Revit headless runner, APS credentials, approved upload policy or cloud execution evidence was found in the inspected project routes. Defer it rather than port TwinPack merely to avoid a session queue.
- **Offline library:** IfcOpenShell documents geometry processing of IFC into vertices/faces, product geometry with openings applied, and a multicore iterator [W4, READ-WEB]. Placement, unit and relationship utilities are documented separately [W5–W7, READ-WEB]. Recommendation: consume a versioned IFC once produced, without a live Revit session. Native RVT manipulation through this route is **not established** by these IFC APIs.
- **Headless downstream DCC:** this project's saved-dump synthesis and background FBX readback are independent of live Revit (`tools/qa/run_benchmark.py`, `tools/source/measure_spec_blender.py`, `tools/blender/fbx_readback.py`). The Max experiment establishes a historical `dcc_batch.py max` lane. This says nothing about native RVT support in that wrapper.

### 2. What the named bridges actually establish

**`revit-http-2025`: local alias for KenLP/RevitMCPServer.** `CAPABILITIES.md` records inspection working on 2026-10-06 with v0.8.31, 20 calls across 19 tools, but no persisted-edit verification. The later bridge research records locally inspected v0.8.40. Those are different evidence dates, not permission to assume the current installation version. Public README/API coverage advertise v0.8.40, 94 MCP tools, typed architecture operations, dry-run and batch support [W2, SOURCE-CLAIM]. The API coverage lists IFC export as future work [W2]; do **not** promise a typed `revit_export_ifc` tool.

Public code at commit `4d273c6053be449e2066d0373d10b47c236de7ad` was read:

- `ListLevelsCommand` collects `Level`, sorts by elevation and returns feet plus metres [W8, READ-WEB/code]; it does not decide which levels count as AGR storeys.
- `CreateFloorCommand` builds **one** closed polygonal CurveLoop, projects all supplied Z values to the resolved level and defaults to the lowest level/first floor type when names are absent [W9, READ-WEB/code]. This is not evidence for holes, sloped floors, measured slab undersides or AGR inset plates. Explicit type/level selection would be mandatory in any future authoring trial.
- `GroupElementsCommand` invokes `doc.Create.NewGroup(ids)` [W10, READ-WEB/code]. That mutates the RVT; our KPP1 export grouping does not require it.

The upstream default Revit 2025 port is documented as 7890 [W2]; **our inspected extractor defaults to 7891**, so identify the host/version/document rather than inferring them from a port. Upstream batch rollback and read-back verification claims [W2] are not a cross-client session lease, nor AGR geometry acceptance. Public command packs being HTTP-only [W2] explains why an absent MCP tool listing alone cannot disprove a custom command, but does **not** establish that our `twin_*` commands ship upstream. Verify their installed command inventory before capture.

**Public `revit-mcp`: a different implementation.** The old server and plugin READMEs explicitly point to the successor monorepo [W11, READ-WEB]. That monorepo describes stdio → WebSocket → in-Revit plugin → command set, advertises Revit 2020–2026, element creation/inspection and `send_code_to_revit` [W12, SOURCE-CLAIM]. Compatibility and AGR extraction parity were not run here. Its arbitrary C# tool is not a safe drop-in for TwinPack, and its tool names are not KenLP names.

**Local `revit-bridge`: another route again.** `CAPABILITIES.md` and `jobs/KPP1/scripts/export_revit_groups.mjs` identify a named-pipe client with `agr_export_fbx`; no public repository identity for that exact local plugin was established. Preserve historical/code-reading attribution instead of borrowing capabilities from public `revit-mcp`. `revit-twin` remains documented **BROKEN**; do not select it because TwinPack files contain the word “twin”.

### 3. Levels, floors, walls/openings and groups: AGR-specific interpretation

**Levels vs slabs.** `markup-helpers` [D045] maps Revit level names through `object.json.revit_levels`, including explicit null/non-storey entries; roof covering is base + offset + volume/area. KPP1's recorded design level +7.700 is not the covering top +7.909, parapet +8.650, or derived inset plate +7.914. Preserve all four meanings. IFC's `get_storey_elevation` returns **project units**, taking placement Z and falling back to `Elevation` [W5]; apply unit conversion once [W6], and explicitly map exported storeys to AGR helpers. A slab top or an `IfcBuildingStorey` is not automatically the missing roof helper.

`tools/source/measure_spec_revit_twin.mjs` filters bands to ones with non-floor exterior elements; it separately reads levels and **roofs**, not a complete native floor/slab inventory. Do not infer slab coverage from “floor” in `twin_export_floor`. KPP1's separate `floors` FBX selection is the existing route for source floor geometry. OBR22's historical cut used the measured slab underside +4.100 and next level minus 1 mm; native slab thickness/geometry matters to that source extraction, not to a new invented AGR storey height.

**Walls/openings.** `src/dt_ai/spec/revit_twin.py` reconstructs uncut wall prisms on location lines and reads opening records separately. For IFC, product geometry normally already has openings subtracted [W4]; flattening that mesh into a TwinPack-shaped record without adapting the contract risks double cutting or interpreting door recesses as contour niches. IFC offers opening/void/fill and containment utilities [W7], but the presence and completeness of those relationships in a particular export must be measured. Keep rough/frame opening size distinct from glass dimensions; KPP1's historical spec-v0.3 comparison resolved precisely this mismatch. Keep OD1 [D048] “depth by default” at 0.4 m when the source lacks depth, and profile seating per [D037]. Do not replace either with IFC wall thickness silently.

**Three different meanings of “group”.**

1. KPP1 `export_revit_groups.mjs` defines eight **selection sets**: `walls_ext`, `walls_int`, `curtain`, `openings`, `floors`, `roofs`, `generic`, `stairs_rails_equip`. It forwards explicit `elementIds` to `agr_export_fbx`, checks `savedDocument === false`, and does not call native `NewGroup`. Its comment warns that unknown category names can export the whole model. Name-based wall predicates (`ADSK_Внутренняя`, `Витраж`, `ADSK_Обрамление`) are local classification heuristics, not general BIM truth. The script currently logs failures rather than throwing for each failed response; the caller must not treat process exit 0 as export acceptance. It also lacks the TwinPack runner's refusal of existing output folders.
2. Native Revit Model Groups are a separate authoring construct [W10]. IFC utilities distinguish group membership, aggregation, spatial containment and nesting [W7]; no 1:1 retention of Revit group/type/member IDs is established by the inspected exporter README [W13]. Missing groups must remain missing, not reconstructed from matching names.
3. AGR working logical groups/instance libraries are useful for editing and provenance, but final geometry hierarchies/groups are forbidden by `docs/domain/geometry.md`. Flatten only the derived delivery copy; retain the source-selection/member mapping externally. Revit material or IFC style is not automatically an approved finish ID, UDIM or window-library type.

### 4. AGR task → automation route → evidence → open risks

Routes below are recommendations unless marked implemented. **H** = headless downstream DCC; **L** = live Revit bridge; **O** = offline library/file processing. A snapshot may require L once and O thereafter.

| AGR task | Automation route in this program | Evidence | Open risks / stop conditions |
|---|---|---|---|
| KPP1 level helpers and roof covering | **L → O, implemented:** HTTP levels/roof parameters → TwinPack → `markup.py`; **O IFC, proposed:** storeys + explicit roof mapping. | READ-LOCAL `measure_spec_revit_twin.mjs`, `markup-helpers`; HISTORICAL-RUN KPP1 v030/v031 match. IFC placements/units [W5–W6]. | Localized roof parameter names; unmapped/non-storey levels; volume/area is project roof convention, not a general maximum elevation. No absolute/geodetic datum inference. |
| OBR22 floor-band extraction; real slab undersides | **L capture** native levels/slab geometry or pipe FBX, **H/O** inspect copied export; **O IFC, proposed** slab geometry + containment. | `jobs/OBR22-K02/STATE.md`: API +4.500/+7.500, underside +4.100, nine unloaded links. KPP1 floor-ID selection. | A level is not a slab; a clipped stair window is not a full opening. Unloaded links contain no captured geometry. TwinPack index is not a floor census. |
| KPP1 exterior contours, hosted doors/windows, grilles | **L → O, implemented:** TwinPack wall lines + openings → spec; **O IFC, proposed:** semantic relation graph + geometry sections. | `revit_twin.py`; KPP1 spec comparisons (historical contour 0.0 mm, opening pairs ≤5 mm); IFC openings behavior [W4, W7]. | Curtain hosts, curved/tilted walls, family bbox vs frame/glass, phases/options, double-applied voids, source IDs scoped to document/link. Grilles reported separately, not silently lost. |
| KPP1 export groups and source-ID/material census | **L → H/O, implemented:** paged HTTP census + pipe `agr_export_fbx(elementIds)` → copied FBX/sidecars → offline match/audit. **O IFC, proposed** groups/aggregate/containment + explicit category map. | `jobs/KPP1/{STATE.md,scripts/export_revit_groups.mjs,scripts/match_ids.py}`; public group utilities [W7]. | Overlapping selection sets; nested components; localized predicates; failed export logged but process may exit 0. IFC `GlobalId` is not a guaranteed Revit `UniqueId` crosswalk. |
| AGR inset roof/terrace plates, quad body and opening seats | **O synthesis + H saved-file readback**, no native RVT floor creation required. | `roof-inset-plane` [D038/D039], `opening-plane` [D037/D048], `from_spec.py`; KPP1 v007. Public floor command's limited contract [W9]. | Never demand a 5 mm gap/20 mm overlap in the architectural RVT/IFC: these are derived model joints. PSU275 predates inset rule and stays untouched. K01 engine parapet stop remains. |
| Window/door simplification and shared meshes | **O library + H** placement/readback; **L only** when exact source family/host/orientation is missing. | `jobs/REVIT-OPENINGS/STATE.md`: 89 approximate placements remain; `library/windows/window_types.json`; OBR22 45 windows/three meshes. | Same bbox ≠ same sash type; orientation/depth and rare curtain assemblies still need review. Neither bridge automatically approves an architectural type. |
| PSU275 whole-building massing, stairs, transformer/racks | **L** inspect source omissions/links; **O/H** massing and parameterized rebuild from approved data. | `jobs/PSU275/STATE.md`: no industrial typical floor, 152 openings; S3 racks absent, transformer voxelized. | IFC cannot recover objects absent from its export. Do not resume per-storey repetition, invent racks, or claim native IDs for S3 measurement IDs. |
| Materials, atlases, UV, NPM/VPM packaging and UCX | **O + H**, not an always-live BIM workflow. **L** only supplements source material/layer evidence. | `jobs/{FACADES-ATLAS,A-MAIN-ATLAS,UV-CONTINUOUS,GROUND-PROJECTION,WINDOW-FRAMES,FACADE-SIGNS,WINDOW-ATLAS}/STATE.md`; `technical_library/`; domain export/validation rules. | IFC geometry has style/material indices [W4], not approved AGR PBR/finish assignments. Quads, normal orientation, collision passages, UV and exported bytes still require independent checks. |
| GeoJSON/MSK-77/absolute marks and official delivery | **O validation + manual/source confirmation**; **L** may expose model coordinates, not establish their correctness. | `PROJECT_STATE.md`, KPP1/PSU275 open gates; `docs/domain/{npm-vpm,validation}.md`. | A zero base point is not a survey; address/district/УКЭП/manual SINTEZ gates remain. No route alone closes V015–V017. |
| Rebuild/repair native RVT levels, floors or groups | **L, only separately authorized copies** via inspected typed tools; **cloud headless, deferred** [W3]; **O IFC** is not this task. | Public creation/group commands [W2, W9–W10], no persisted-edit evidence in our registry. | Not needed to finish current AGR meshes. Never edit source RVT merely to simplify delivery; no Revit authoring experiment authorized by this card. |

OBJ03 remains stopped after the user's unsuccessful review; MASHI remains a trial, and GLB towers must not be resumed (`jobs/{OBJ03,MASHI-LP,GLB-NPM}/STATE.md`). They inform risks, not new production work. SYNTH-001 and ORCH-OBR22 illustrate development/component success without delivery acceptance.

### 5. Sharing a session: one capture owner, many offline consumers

**PROPOSED Revit application of the existing coordination rules**, not an implemented Revit lease:

1. Reserve **one Revit workflow owner** across HTTP, pipe, aliases and direct Node clients. Worktrees isolate files, not Revit. Until an enforcing broker exists, stop other clients/operator document changes by agreement; a cooperative file lease cannot block bypass clients.
2. Under the reservation, read health **and an API-backed document/version query**, confirm PID/start time if available, exact upgraded/detached copy path, units, dirty state, phases/options, link load state and output version. Pipe `revit_status` alone previously bypassed the API queue; pair it with version/document calls (bridge research). Stop on identity mismatch or missing session; never guess response fields.
3. Capture paged census, levels, transform stack and selected outputs in one bounded workflow. Proposed manifest: card/owner, process identity, source/document hash, dirty-before/after, selected element IDs, link transforms/status, bridge/plugin/pack versions, phase/options, commands/request IDs, output hashes and unit/frame contract. Source file hashes cannot describe unsaved live changes; record that limitation or request an approved frozen copy.
4. Release only after document identity and idle state are reconciled, source hashes unchanged, and artifacts complete. Do not close/discard a dirty user document. Timed-out exports are **outcome unknown**: quarantine and inspect, never automatically retry a mutation or let another client switch documents. `isModified=false` and `savedDocument=false` are useful signals, not immutable read-only guarantees.
5. Fan out copies of the manifest/TwinPack/IFC/FBX to offline parser, checker and library workers. Reacquire live ownership only for a concrete missing fact. Do not hold a Revit lease while doing UV, mesh rebuilding or checking ZIPs.

The Blender sharing experiment established its lease result only for Blender. Do not transfer its reset-by-inventory-diff implementation to Revit documents. Also distinguish the registered Blender Lab route (historically 9877) from the experimenter's `blender_exec.py` route (historically ahujasid/9876); confirm the actual runtime before a future experiment.

## How it applies to this repository

- Preserve `tools/source/measure_spec_revit_twin.mjs` as a **live capture boundary** and `src/dt_ai/spec/revit_twin.py` as an **offline consumer**. Add a capture manifest/command inventory in a later implementation, not another opaque bridge.
- Keep mapping policy in `jobs/KPP1/{object.json,materials.json}` and benchmark tolerances in `benchmark/bench-k01-kpp1/tolerances.json`; do not rewrite standards to make an import pass.
- Extend `adapters/revit/README.md` only after an actual IFC intake implementation/experiment: it currently says the generic importer is unimplemented. This research does not change that status.
- Use `src/dt_ai/spec/markup.py`, `Spec.expanded_floors()`, `tools/qa/check_geometry.py`, and `tools/blender/fbx_readback.py` as comparison interfaces. Preserve per-element identity in a sidecar even if the delivery flattens collections and merges glass.
- Correct the older research's stale K01 gap: **current** `benchmark/bench-k01-kpp1/tolerances.json` has a `geometry` block. Its README still records mesh/opening/material failures and a parapet engine stop; do not advertise K01 as green or relax those checks for IFC.
- No scripts, adapter, job, shared capability registry, standards or project-state file are changed by this card.

## Proposed next tasks

These are **two experiment proposals**, not executed results or GitHub issues. Value/effort estimates include writing the small experiment drivers. Driver filenames below are **proposed, not existing commands**; the experimenter implements them in a separately authorized experiment worktree. Wrapper CLI shapes are taken from existing experiment reports, not inspected outside this worktree. Before execution, the experimenter must confirm wrapper help, authorization, active app/version/units, lease ownership and dependency availability. No undocumented `dcc_batch.py revit` or `dcc_batch.py blender` mode is assumed.

Common protocol: copy B01/B02/B02t `spec.json`, `object.json`, `tolerances.json`, `etalon.json` into a fresh task-local scratch root; hash originals before/after. Copy available binary etalons before opening; a manifest is not a mesh. Use three repetitions, separate versioned output directories, bounded calls, compact stdout (<10 KB) and full JSON artifacts on disk. No writes into `data/`, source/approved files or another worktree. No installation is implied; a missing dependency/fixture is `blocked`, not pass. Raw times are informative, not a speedup claim against unequal work. Acceptance below concerns these experiments only; `delivery_passed=false` throughout.

### E1 — IFC intake loss ledger for levels, slabs and hosted openings

**Scope:** implement a report-only IfcOpenShell intake prototype driven from `blender_exec.py`, with no Revit calls. Start on copied B01/B02/B02t specs: generate explicitly **synthetic IFC transport fixtures** containing storeys, slab geometry, wall/void/fill relationships and source keys, then independently read them into a normalized fact ledger and compare with the original copied specs. Exercise metre and millimetre project units, a translated/rotated placement chain, and a missing-storey/opening-relation negative fixture. Do not feed hand-written specs into the production benchmark or claim this generated IFC is an independent architectural etalon. If the user supplies a frozen K01 IFC paired with existing TwinPack/spec evidence from the same model revision, add a separate real-export arm without creating/exporting RVT in this experiment. This adds semantic-loss evidence absent from the previous generic IFC pilot proposal. **Value L / effort M.**

- **Route/invocation:** proposed `experiments/bim-revit-agr/ifc_probe.py`, loaded through the known live-Blender wrapper interface:
  ```bash
  python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py --code \
    "ROOT=r'<experiment-worktree>'; INPUT=r'<copied-fixtures>'; OUT=r'<new-run-dir>'; exec(open(ROOT+'/experiments/bim-revit-agr/ifc_probe.py', encoding='utf-8').read(), globals())"
  ```
  Use IfcOpenShell already available in that runtime, or an explicitly configured existing offline Python interpreter launched by the reviewed driver; record interpreter/library/schema/kernel versions. If neither is available, stop before scene mutation. No large IFC JSON on stdout. Blender can inspect resulting mesh arrays without replacing the user's scene; prefer unlinked datablocks and release only driver-owned data.
- **Baseline:** current copied spec facts (`expanded_floors`, mapped levels, contours and opening spans); existing engine geometry is a second **derived** reference, not an independent etalon. No current IFC adapter exists, so do not invent a legacy IFC timing baseline. Real arm baseline is paired frozen K01 TwinPack extraction, not today's active RVT.
- **Metrics/pass:** synthetic arms: 100% expected storey/host/fill associations and source keys; exact opening counts; max SI coordinate/elevation error ≤1 mm, contour area difference ≤0.1%, opening bbox difference ≤1 mm. Missing relations must produce explicit incomplete/unknown facts in 100% of negative cases, never fabricated associations. For the real K01 arm use its committed `spec_compare` tolerances (levels 0.03 m, contour area 2%, contour Hausdorff 0.05 m, opening bbox 0.05 m; exact counts/kinks; grilles reported separately). Every expected class is accounted as extracted/unsupported/missing; unsupported mandatory facts block adoption, not merely disappear from the denominator.
- **Artifacts:** input/output hashes; schema/export settings when supplied; facts JSON keyed by IFC GlobalId + file hash; placement/unit ledger; slab top/underside vs storey table; opening relation/missing-field ledger; comparison JSON/Markdown; three raw timings per arm and geometry overlays. Explicitly separate synthetic transport verdict from real-export verdict.
- **Constraints/value:** tests snapshot sufficiency, not RVT editability, parametric roundtripping or Revit exporter quality. A passing synthetic arm only licenses further real-IFC intake work. Missing K01 IFC leaves the real arm blocked while the synthetic arm remains runnable; native family/type/phase/georef preservation stays unverified.

### E2 — KPP1-style selection groups and provenance survive the delivery boundary

**Scope:** implement a sidecar-versus-name-only transport experiment on copied B01/B02/B02t meshes using KPP1's selection-set vocabulary, not native Model Groups. Build a source-qualified member/role mapping, preserve it through a saved `.blend` and derived flat FBX, then read both back in a separate invocation. Inject repeated/truncated names, one mesh belonging to two source selections, one unassigned ID, a missing sidecar, a stale sidecar hash and an accidental whole-model export. Compare membership independently of display names. Optionally replay the same verifier on copied KPP1 census/group FBX/sidecars when those local artifacts are provided; never silently substitute B01 success for KPP1 validation. This directly tests the selection-set risks in the current job script rather than repeating mesh-audit or batching experiments. **Value L / effort M.**

- **Route/invocation:** proposed `experiments/bim-revit-agr/group_probe.py`, invoked twice through `blender_exec.py --code` with `MODE='write'` then `MODE='readback'`, `ROOT`, `INPUT`, `OUT` and `exec(open(...).read(), globals())` as in E1. No application reload/open over a user's scene: load copies into driver-owned data, save only owned data to a new library file and remove it after verification. A native Max confirmation is optional via the already documented `dcc_batch.py max --card <experiment-card> --file <reviewed-max-driver.py> --out <new-wrapper-result.json>`; it is not a prerequisite or permission to run another DCC on a Blender-only card.
- **Baseline:** same fixture passed through name-only group matching, reflecting the fallback risk from truncated FBX names; record observed failures rather than assuming a baseline failure count. Candidate: sidecar mapping uses source file hash + source element key + selection-set memberships + exported object/geometry mapping, with an explicit many-to-many relation. Material roles remain a separate map.
- **Metrics/pass:** all clean fixtures, three repetitions: membership precision/recall 1.0, zero falsely unique source matches, zero unexplained missing/extra objects; world-space max coordinate error ≤1 mm; identical level-helper names/elevations and intended role assignments. Original benchmark hashes unchanged. All five injected fault classes (ambiguous names, unassigned identity, missing sidecar, stale hash, whole-model selection leakage) must be rejected or explicitly marked ambiguous/incomplete, never accepted as complete. Name ambiguity with a valid sidecar may be resolved, but must not be “resolved” by guessing a source ID. Final FBX contains no group-parent hierarchy; development helpers must be excluded from a delivery-profile copy.
- **Artifacts:** original/copy/export hash ledger, selection sets and expected object/member table, name-only vs sidecar confusion tables, export/reimport map, orphan/duplicate/unknown lists, saved-file geometry/role comparison, raw wrapper responses and five fault verdicts. A separate KPP1 replay report lists supplied census version and per-group input IDs, union, intersections, missing/extra exported members and `savedDocument` evidence from historical capture.
- **Constraints/value:** preserve many-to-many selection provenance rather than assigning one guessed ID per merged face. FBX may drop arbitrary attributes, so failure to recover a mapping must remain visible. This experiment cannot prove Revit native-group or IFC-group export preservation; it tests the program's downstream contract. Reuse existing orientation/readback checks rather than broadening generic audit benchmarks.

## Open questions for the user

1. Which frozen KPP1 IFC (schema/exporter version, view/phase/options, loaded links) can be paired with a matching TwinPack/census snapshot? Without it, E1 measures synthetic transport only; no live export is requested here.
2. For further “group” work, is the needed contract KPP1 export selection sets, native Revit Model Groups/types, or both? Current KPP1 automation establishes only the first.
3. Which currently unavailable source contains PSU275 racks and the missing transformer detail? Neither a new bridge nor an offline parser can supply absent design evidence.
4. Who will own the shared Revit capture window and authorize document switches on copies? The existing one-owner rule is clear; a cross-client enforcing broker is not yet established. APS remains deferred unless cloud upload and budget are separately approved.

## Public source register

All URLs below were fetched successfully (HTTP 200) in this card. Reading documentation/code verifies its contents, **not** compatibility with the installed plugin, persistence, geometry quality or multi-agent safety. GitHub branches/docs can change; code links W8–W10 are pinned. Upstream API resolved KenLP `main` to `4d273c6053be449e2066d0373d10b47c236de7ad` and the successor monorepo to `86cf7057785f2423fc0d0892c9a5d9c93deb1aa3` during retrieval.

- **W1 — Autodesk Revit 2025 External Events (READ-WEB, official):** https://help.autodesk.com/cloudhelp/2025/ENU/Revit-API/files/Revit_API_Developers_Guide/Advanced_Topics/Revit_API_Revit_API_Developers_Guide_Advanced_Topics_External_Events_html.html
- **W2 — KenLP bridge documentation (READ-WEB; runtime behavior remains SOURCE-CLAIM):** https://github.com/KenLP/RevitMCPServer/blob/main/README.md ; https://github.com/KenLP/RevitMCPServer/blob/main/docs/ARCHITECTURE.md ; https://github.com/KenLP/RevitMCPServer/blob/main/docs/API_COVERAGE.md
- **W3 — Autodesk Automation APIs (READ-WEB; cloud capability SOURCE-CLAIM):** https://aps.autodesk.com/automation-apis
- **W4 — IfcOpenShell geometry processing (READ-WEB documentation):** https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html
- **W5 — IfcOpenShell placements/storey elevation (READ-WEB documentation):** https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/placement/index.html
- **W6 — IfcOpenShell unit scale (READ-WEB documentation):** https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html
- **W7 — IfcOpenShell element relationship utilities (READ-WEB documentation):** https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/element/index.html
- **W8 — KenLP level reader (READ-WEB/code):** https://github.com/KenLP/RevitMCPServer/blob/4d273c6053be449e2066d0373d10b47c236de7ad/src/RevitMCP.Core/Commands/ListLevelsCommand.cs
- **W9 — KenLP floor creation (READ-WEB/code):** https://github.com/KenLP/RevitMCPServer/blob/4d273c6053be449e2066d0373d10b47c236de7ad/src/RevitMCP.Core/Commands/CreateFloorCommand.cs
- **W10 — KenLP native group creation (READ-WEB/code):** https://github.com/KenLP/RevitMCPServer/blob/4d273c6053be449e2066d0373d10b47c236de7ad/src/RevitMCP.Core/Commands/GroupElementsCommand.cs
- **W11 — Deprecated public server/plugin notices (READ-WEB):** https://github.com/mcp-servers-for-revit/revit-mcp/blob/main/README.md ; https://github.com/mcp-servers-for-revit/revit-mcp-plugin/blob/main/README.md
- **W12 — Successor monorepo README (READ-WEB; supported tools/versions SOURCE-CLAIM):** https://github.com/mcp-servers-for-revit/mcp-servers-for-revit/blob/main/README.md
- **W13 — Autodesk IFC exporter/linker README (READ-WEB; no group-preservation guarantee established):** https://github.com/Autodesk/revit-ifc/blob/master/README.md

## Verification of this card

Only this Markdown file was intentionally changed. No DCC experiment was executed. Required harness command: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_d7aac992`.
Final line: **`1 failed, 1910 passed, 2 skipped, 12 deselected, 1 warning in 189.56s (0:03:09)`**. Failure: `tests/qa/test_from_spec_decor.py::test_a_corner_pilaster_passes_every_check`, assertion reports `orientation = 1`. This was observed before adding this document; no code fix is in scope and no all-green claim is made. The suite was run because the harness mandates it despite this research card requesting no full tests. `git diff --check` is the document's final whitespace check.
