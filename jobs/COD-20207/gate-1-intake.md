# COD 20207 Ground — Gate 1 intake (issue #420)

Status: **Etalon importer repaired through copied-Max diagnostic export; footprint source authority needs a decision before build**. Real project data, not synthetic.
No Ground mesh, export, comparison pass or visual-review publication is claimed.
The draft below preserves the original intake. The approved answers and follow-up evidence are recorded in the appended resumed-intake section; original open questions are historical, not unanswered again.

## Sources and executed route

Only the supplied copies were opened. Desktop originals were not opened or modified.

| Input | Bytes | SHA-256 |
|---|---:|---|
| `C:/x/ground-cod-22/spozu.dwg` | 9933016 | `9b409b023a5dd494c91f6807e7aee392b6a684da48fac371209764770d5f764b` |
| `C:/x/ground-cod-22/gp.dwg` (optional, hashed only) | 92071 | `5f1155b8c317350515dcf0995c5dbcfb643f40c0d1dd28e2af1bd852e7f32300` |
| `C:/x/ground-cod-22/intake-v001/spozu.dxf` | See local file | `e11a4a120832996618f41d4a4cc46bef329bc1ca9b0f18cc6add2bd76fdf12e7` |

Executed from the issue worktree:

- `uv sync --extra cad`: exit 0.
- `uv run python -c "from adapters.cad.dwg import dwg_to_dxf,sha256; r=dwg_to_dxf('C:/x/ground-cod-22/spozu.dwg','C:/x/ground-cod-22/intake-v001'); print(r); print('DXF_SHA256',sha256(r.dxf))"`: exit 0.
- Existing conversion adapter copied the input again to `spozu.copy.dwg`, then ran the inspected `dcc_batch.py acad` session-lock wrapper: AutoCAD 2025 core console, `ACADVER=25.0`, `INSUNITS=6` (metres), 5.9 seconds, process exit 0, wrapper status `ok`. Receipt: `C:/x/ground-cod-22/intake-v001/spozu.acad.json`. Source hash verified unchanged by the adapter.
- `PYTHONPATH=. uv run python tmp/cod_intake.py`: exit 0. Read-only diagnostic using existing `adapters.cad.spozu._walk` (composed transforms and effective layers); full inventory: `C:/x/ground-cod-22/intake-v001/inventory.json`.
- Read-only hatch-region probe using existing `hatch_region` and `boundary_polygon`: exit 0. No repair applied; invalid source listed below.

Origin/main at intake: `45d56e9`. No `jobs/COD-20207` report or `adapters/cad/configs/cod_20207.yaml` exists there; acceptance is not already delivered.

## Drawing inventory

DXF AC1032; 280 layer-table entries; 1361 model-space top-level entities;
7166 visited model-space entities **including INSERT containers and expanded contents**;
0 traversal findings. Counts are not a guarantee that Civil proxy payload geometry is readable.

Layouts: `1_Ситуационный`, `2_СПОЗУ`, `3_ПОР`, `4_ПЗМ`, `5_Благоустройство`,
`6_СПИС`, `7_Транспортная схема`, `Model`. Proposed covering authority: `5_Благоустройство`
legend plus model-space hatches; vertical planning: `3_ПОР`, pending confirmation.

### Boundary candidates

Both are closed `ГП_Граница участка` LWPOLYLINEs, with the same area to rounding.

| Handle | Area m² | XY bounds (metres) | Observation |
|---|---:|---|---|
| `69002` | 5101.588 | (6570.83, 15385.29)–(6674.84, 15449.21) | Intersects all six covering-type groups; proposed working boundary |
| `5968B0` | 5101.588 | (9498.391069, 17275.841707)–(9602.401069, 17339.761707) | Zero overlap with every covering-type group; translated duplicate candidate, not silently discarded |

## Draft parts list — mappings for approval, not executable PartsList

Areas below are unions of **valid** top-level hatches clipped to candidate `69002`.
They are not additive coverage, an approved parts budget, or final surface measurements.
Legend labels are text read from `5_Благоустройство`, not inferred from colour.

| Proposed part / operation | Source layer | Hatches | Valid clipped union m² | Legend evidence / question |
|---|---|---:|---:|---|
| Asphalt / layered-cake plane | `ГП_Благо_ТИП_1` | 1 | 2430.264599 | `542F39`: asphalt drives, type 1 |
| Tile / layered-cake plane | `ГП_Благо_ТИП_2` | 8 | 361.511102 | `542F44`: tile sidewalks, type 2 |
| Reinforced tile / layered-cake plane | `ГП_Благо_ТИП_3` | 5 (1 invalid) | 125.603787 | `593455`: reinforced tile sidewalks, type 3 |
| Geogrid / layered-cake plane | `ГП_Благо_ТИП_4` | 5 | 491.897629 | `542F72`: geogrid, type 4 |
| Reinforced geogrid / layered-cake plane | `ГП_Благо_ТИП_5` | 1 (+2 proxies) | 9.025629 | `593451`: reinforced geogrid, type 5; proxies unresolved |
| Unclassified covering / operation pending | `ГП_Благо_ТИП_6` | 3 | 2.490864 | No type-6 label established; do not assume lawn |
| Drive curb / profile extrusion | `ГП_БР дорожный` | 5 LWPOLYLINEs | n/a | `542F6A`: БР100.30.15; exposed height and alignment require approval |
| Garden curb / profile extrusion | `ГП_БР сад` | 4 LWPOLYLINEs | n/a | `542FB1`: БР100.20.08; exposed height and alignment require approval |
| Relief / TIN projection | `ГП_Красная поверхность`, `ГП_ПОР_красная`, `ГП_Отметки поверхностей`, `ГП_Характерки` | n/a | not measured | 1 + 5 + 15 + 18 Civil proxy entities respectively; no readable design-Z list established |
| Boundary skirt / perimeter extrusion | `ГП_Граница участка` | n/a | pending boundary selection | At least 1 m per GND-03; project zero not established |

`ГП_Черная поверхность` also contains one proxy (existing-surface candidate, not selected as design).
`ГП_Благо_ТИП_3` hatch `4C5784` has a self-intersecting first loop at
(6642.69999287543, 15434.7342055753). It is excluded from the area above, **not repaired**.
Flora/MAF placement remains out of scope; inventory retains their layers rather than discarding sources.
No source is consumed by a production build at this stage.

## Questions to Artem (Gate 1)

1. Confirm boundary `69002` and use of model-space coverings with layout `5_Благоустройство` as legend authority; is `5968B0` only a duplicate/context contour? Confirm CRS and project-zero height (INSUNITS establishes metres only).
2. Confirm types 1–5 above. What is type 6, and which source supplies lawn/unhatched regions and building-footprint holes? Confirm material/texture identities from the handmade etalon rather than borrowing Vatutino's slots.
3. May self-intersecting hatch `4C5784` be repaired with `make_valid`, or should it be replaced by an authoritative contour? No Vatutino-specific repair permission is carried over.
4. Confirm design relief authority (`3_ПОР` / red Civil surface) and provide/authorize an export of design elevations or 3D surface if the proxy payload cannot be extracted by the existing route. Confirm exposed drive/garden curb heights and which edges require steps/ramps.
5. Approve the completed parts mapping before build (D111/D124/D125). Surface budget allocation, joints, master grid and any relief tolerance exceptions remain unapproved for this site; Vatutino-only D150 must not be reused.

The machine-readable public `PartsList` requires resolved operations/budgets/source coverage and explicit approval.
Do not create an apparently buildable config or fabricate those fields while these questions are open.
After answers: write/validate the actual parts list and `adapters/cad/configs/cod_20207.yaml`, then use the existing pipeline; record every required pipeline change.

## Pipeline findings and remaining acceptance

- Layer mapping is project data, but the six covering types, two boundary candidates, invalid contour and proxy-based relief require explicit handling.
- Existing DWG conversion and nested traversal work on this second drawing. No production-code change made.
- Existing Vatutino job scripts are still named/site-configured for Vatutino; reusability beyond the adapter has **not** been demonstrated.
- General surface/UCX/material/relief checks remain mandatory; the Vatutino-specific gap exception is not applicable.
- Handmade etalon inspection, matched-point height comparison, NPM/VPM/surface budgets, xView, materials, UCX, and Vatutino-v014 comparison are **not measured: Gate 1 awaits approval**.
- No scene is published to `C:/x/review/pending.json`: publishing an unbuilt/unapproved scene would be misleading.

Next worker: resume from these receipts and answers, keep all assets under `C:/x/ground-cod-22/`, use only copied etalons, and publish one PR only after the full acceptance is delivered. No PR opened for this partial intake.

## Resumed intake — Gate 1 answers and flatness conflict

Artem's approval is recorded in the card comment (2026-10-20, supplied by the orchestrator):
"этот граунд делаем плоским без рельефа, а так все рекомендации принимаю".
The orchestrator specifies **every covering plane at Z = 0.000**, DWG WCS metres,
no CRS transform, and simultaneously the same Vatutino pipeline/default joints.

Approved without reopening the original questions:
- Boundary `69002`; `5968B0` context only; `5_Благоустройство` legend authority.
- Coverings 1–5 as above. Identify type 6 against the etalon; if absent, tile (type 2),
  explicitly listed as an assumption. Unhatched region is lawn unless contradicted by the etalon.
- Footprints from copied `ЦОД_Обводки.dwg`, falling back to the copied etalon.
- `make_valid` authorized for hatch `4C5784`; before/after area remains to be measured.
- Flat by decision; Civil relief proxies excluded, relief comparison replaced by flatness.
- Drive/garden curb exposure 150/50 mm; no stairs or ramps. Vatutino default budgets/grid;
  no D150 exception. Material identities from this site's etalon, not Vatutino.

### Executed copied-reference intake (not production build)

`uv sync --extra cad`: exit 0. Copies hashed against read-only sources; manifest
`tmp/cod-etalon-manifest.json`. Original scenes were not opened in a DCC or saved.

- `C:\x\ground-cod-22\etalon\scene.max`: 2154496 bytes, SHA-256 `d81f0223365886cd72489fced66af12562257afc49d42584604eb9786093c8e6`.
- `C:\x\ground-cod-22\etalon\LP.max`: 4206592 bytes, SHA-256 `ced934b5164b00bf7e43335fe5061331b3380672d2f527971a553ba88abbdfbc`.
- `C:\x\ground-cod-22\etalon\hp.max`: 2656472 bytes, SHA-256 `63408e95d9aa0b16adc2d7aa3631772b00b6443601f9ab0909f300c2c461d2fe`.
- `C:\x\ground-cod-22\etalon\20207_АГР_ВПМ-НПМ.fbx`: 80472336 bytes, SHA-256 `fa1fe26051d639efd7d0bc1ed9ed5e40add28709b471b477de42ce7643f9d929`.
- `C:\x\ground-cod-22\footprints.dwg`: 6646821 bytes, SHA-256 `b37c85489c2b270e889723bd5089e8f2c8b8101b821ddc71ca5ba37deec7daa3`.

AutoCAD existing `dwg_to_dxf` route on `footprints.dwg` -> exit 0, 5.4 s;
`C:/x/ground-cod-22/footprint-intake-v001/footprints.dxf`, with native receipt
`footprints.acad.json`. Top-level inventory: 193 `spp2` and 117 `s3` polylines,
30 `АР_подложка`, 7 `s3`, 7 `spp2` hatches; building-outline authority is not
inferred from these layer names. The copied etalon remains the authorized fallback.

Headless 3ds Max 2026, metres, system scale 1, one process through `dcc_batch.py max`:
read `scene.max`, `LP.max`, `hp.max` sequentially, never saved. Initial diagnostic
failed on `LinkComposite` returning no snapshot mesh; diagnostic repaired to report
these unsupported nodes explicitly, not silently drop them. Second diagnostic wrote
`C:/x/ground-cod-22/etalon/native-inventory-v001.json` (317/4/25 geometry nodes).
Wrapper exit 0/status `ok`, but **native process exit 4294967166**, startup
`polyunwrapper` CLR error and missing Corona 2024 plugins remain in the raw receipt
`native-run-v002.json`. This is partial native inspection, NOT successful complete QA.

| Native named object | Render triangles | UCX pieces / triangles | Caveat |
|---|---:|---:|---|
| LP.max `SM_Tup_Skladochnyj_ZU_5_1_Ground` | 2817 | 0 / 0 | World bounds Z 158.727219–161.326645 m; not flat at zero |
| hp.max same Ground name | 48765 | 23 / 296 | Local bounds Z -2.675156–5.503055 m; GroundGlass separate, 4 tris |

These are named-object measurements, **not** final Ground-only surface/profile budgets:
hp Ground may contain merged details; do not compare these with surface-only triangles.
LP material names the site's `Ground_1` with relative `_d_1.png`/`_n_1.png` paths.
`scene.max` HP uses six `UDIM_1001..1006` physical-material slots and the site's maps.
The inventory does not yet establish the type-6 location/material or reusable material recipes.
No maps were replaced with Vatutino identities.

### New exact decision required: flat datum versus stacked planes

The approved comment says *every covering plane* Z=0.000, whereas the requested
unchanged method-C route intentionally overlaps a base plane with coverings at
+6/+12 mm. This is not a relief difference. `ground_cake.plan_layers` rejects
`step=0`; its default flat plan puts a tile on an asphalt base at +0.006 m.
The existing builder also gates co-directional overlapping planes at >=5 mm.
Making all of them coplanar would cause z-fighting and violate the retained gate;
cutting disjoint regions would change the approved layered-cake method.

Executed synthetic capability probe (not project data), exit **1**, expected rejection:

```python
from shapely.geometry import box
from dt_ai.geometry.ground_cake import plan_layers
b = box(0, 0, 10, 10)
cov = {"asphalt": [b], "tile": [box(1, 1, 2, 2)]}
slots = {"asphalt": "Asphalt", "tile": "Tile"}
p = plan_layers(b, cov, "asphalt", slots)
print([(l.covering, l.level, l.level * p.step) for l in p.layers])
# [('asphalt', 0, 0.0), ('tile', 1, 0.006)]
plan_layers(b, cov, "asphalt", slots, step=0)
# ValueError: step must be a positive finite number
```

**Question:** does "flat Z=0" mean the common project datum/relief is zero,
while method-C +6/+12 mm covering offsets are preserved (recommended for the same
pipeline), or must every visible covering surface be exactly Z=0, authorizing
nonoverlapping cut-out regions instead of the stacked method?
No guess, zero-spacing bypass, alternative mesher or production build was made.
No native startup/plugin settings changed; no pipeline code changed.

### Remaining acceptance / next worker

Resolve the single question above before building. Then complete etalon/map and
footprint interpretation, write the site config and validated confirmed PartsList,
parameterize only genuinely site-specific data in the existing route with tests-first
portability regressions, and produce both FBX plus independent readback/UCX/xView,
flatness, comparison tables and review publication. Actual end-to-end budgets,
full suite and regression-eval receipts are not claimed. No PR is opened and
`pending.json` is untouched: there is no built review scene yet.

## Resumed intake 3 — decision closed, extraction and importer stop

The card's final Artem answer (2026-10-20 23:5x) supersedes the literal-all-planes-zero
wording above: **common project datum zero, no relief, method-C +6/+12 mm offsets retained**.
No model decision is outstanding on that question. Other approved Gate 1 answers stand.

`adapters/cad/configs/cod_20207.yaml` now maps the six types, boundary `69002`,
make-valid for reinforced tile, and the two curb roles. Type 6 deliberately remains
separate pending spatial etalon identification (authorized fallback: type-2 tile).
Civil relief, Flora and MAF are not selected. Unmapped source content remains in adapter
findings rather than an ignore-all rule. This is a source map, not a confirmed executable
PartsList: footprint/material interpretation still has to finish before build.

### Executed commands and evidence

- `uv sync --extra cad`: exit 0.
- `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q tests/test_cod_ground_config.py -p no:cacheprovider --basetemp=C:/x/t_3e9518e5-config-red`:
  exit 1, **1 failed**, missing config; tests-first commit `59faf1a`.
- Same focused test with `--basetemp=C:/x/t_3e9518e5-config-green`: exit 0,
  **1 passed** after adding config. No full suite yet; no review requested.
- `uv run python -m adapters.cad.spozu C:/x/ground-cod-22/intake-v001/spozu.dxf --config adapters/cad/configs/cod_20207.yaml --json C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json`:
  exit 0. Raw console: `tmp/cod-adapter-console.txt`.
- `PYTHONPATH=. uv run python tmp/cod_regions.py`: exit 0 (read-only diagnostic).
  A correction to prior intake geometry was necessary: `snapshotAsMesh` already yielded
  world coordinates, and the earlier diagnostic applied `objectTransform` again.
  Subtracting LP node translation restores the native world bounding box within 5 mm;
  this correction is diagnostic only, **not** a verified general transform adapter.
  LP upward-face XY union: **5112.039331 m2**; approved boundary minus that union:
  **7.512981 m2**, predominantly two perimeter strips (4.630304 and 2.881004 m2).
  This does not establish building-footprint holes: LP Ground appears to extend beneath
  the building. Both top-level and nested closed footprint-DWG polyline probes found
  **0 intersecting candidates >10 m2 in the approved WCS boundary**. This is not proof
  the drawing contains no building; check its coordinate frame rather than invent holes.

Extracted covering unions (m2): asphalt **2430.264599**, tile **361.511088**,
reinforced tile **126.512169**, geogrid **491.897606**, reinforced geogrid **9.025632**,
type 6 **2.490864**. These are adapter unions, not final nonoverlapping surface totals.
Repair `4C5784`: adapter reports raw ring **0.908 m2 -> 0.908 m2** before boundary clip;
full repaired area **0.908375821539 m2**. Keep the raw adapter detail and remeasure
unrounded before/after if the final report needs a delta below its displayed precision.

### Environment repair attempted twice; no successful etalon FBX readback

Blender live bridge was unreachable; installed baseline reports **5.1.2 / ec6e62d40fa9**.
The copied reference FBX remains the card-authorized input, not an original scene.
The Max ping was reachable, but no live document was changed; its prior headless inventory
remains partial because of the recorded plugin errors/nonzero native exit.

Read-only Blender diagnostic `tmp/cod_fbx_intake.py` imports the copied reference and
would save mesh/UV/material inventories to a new `etalon/fbx-inventory-v001.json`.
Both actual attempts failed **before that output existed**:

1. `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python tmp/cod_fbx_intake.py > tmp/cod-fbx-intake.log 2>&1`
   -> **exit 11**, `EXCEPTION_ACCESS_VIOLATION`.
2. Same command with `--threads 1`, private `TMPDIR/TEMP/TMP=.../tmp/blender-process`
   -> **exit 11**, same fault address `0x00007FF6FCE4257F`.

Crash backtrace: `mesh_set_custom_normals` -> `mesh_normals_corner_custom_set` ->
`normals_calc_corners`; exception **0xc0000005**. This is FBX custom-normal import,
not an inferred suite concurrency/startup failure. No machine/plugin settings changed.
The two-failure rule stops further DCC attempts in this run. All commands were foreground;
no owned background CLI/DCC process remains running from these calls.

Next repair direction (NOT executed or claimed successful): in a fresh allowed attempt,
use an explicitly reported **diagnostic** `use_custom_normals=False` import of the COPY,
if appropriate, or obtain a clean Max-exported diagnostic copy. Preserve original normals
and the original failed receipts; disabling their import must not become normals-QA pass.
Do not change Blender version or global plugins without authorization.

### Hash inventory for this attempt

| File | SHA-256 |
|---|---|
| `C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json` | `5438c651b30a3b1f91a8f8f0d35d0acc9942cd1c9eccc313fc2b2f7201fc3700` |
| `C:/x/ground-cod-22/intake-v001/footprint-candidates.json` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `C:/x/ground-cod-22/intake-v001/etalon-lp-projected.json` | `78f5ca6fdca967fc09bd98684f82d8ec307a68304156d62d35f3320cf6afc94f` |
| `tmp/cod_fbx_intake.py` | `05e0be9aa62282f81999c1ad370323dc516686e3002026e42e0b7faa9aac65ec` |
| `tmp/cod-fbx-intake.log` | `36eda926096dbb972d2da7688d2b69a69a7ca40d391465c3439a0002494a8df5` |
| `tmp/cod-fbx-intake-retry.log` | `a2a53573bdeb329b4c4af36e3831ab633e92c7bce7e5dd41acff264b8db06ac7` |
| `tmp/blender-process/blender.crash.txt` | `34105309fd0a1c4d37bbf105674caac18a073846ef9d4dda9d20381a56e3460a` |
| `adapters/cad/configs/cod_20207.yaml` | `1c429cd235c627b552fc82bc2712f6ae4920496252f3cd381b95ffbbb9be35ed` |

### Remaining acceptance

No Ground build, mesh budget, xView/UCX/readback pass, texture-set interpretation,
Vatutino comparison, or `C:/x/review/pending.json` publication has been delivered.
The confirmed PartsList remains incomplete; do not build until the authorized etalon
fallback establishes footprint/material facts. No new production module or pipeline
change was made, only project source-map data and its regression. No PR opened.

## Final Gate 1 closure (Artem, card comment 2026-10-21 00:25)

Artem answered "да" to the orange **1670.085519 m2** largest unhatched
component as the building hole. **All other unhatched regions are lawn**.
The 373.983881 m2 of mapped coverings beneath Main roofs/canopies remain
coverings, not holes. The earlier footprint question below is historical and closed.
`parts.json` records the approved decomposition and default budgets; `build-settings.json`
contains flat datum zero, site covering slots and explicit lawn remainder. The unchanged
1000 m2 footprint threshold selects exactly the approved component (next largest 16.6 m2).
Type 6 uses the authorized type-2 fallback: atlas evidence shows the paved apron,
not a separately identified material. Slot labels describe semantic coverings, **not**
assertions that the atlas is a seamless material or that textures have been transferred.
No D150 exception is used. Relief steps skipped: flat by user decision; method-C
6/12 mm levels retained. Curbs retain approved 150/50 mm exposed sections.

## Resumed intake 4 — authorized importer repair, footprint decision

The orchestrator authorized a comparison-only import without custom normals and,
if that failed, a diagnostic export from the copied Max scenes. No authorization
was extended to changing originals or relaxing checks on our own eventual output.

### Actual repair commands / results

- Blender 5.1.2 / `ec6e62d40fa9`, empty factory scene, copied FBX in metres:
  `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --threads 1 --python-exit-code 1 --python tmp/cod_fbx_intake.py`
  with `use_custom_normals=False` -> **exit 139 / access violation**, not a successful
  readback. Receipt: `tmp/cod-fbx-no-custom-normals.log`.
- Live Max ping: reachable 2024 / safe mode. Its user document was **not** modified.
  The card's explicit copied-scene headless fallback was used instead.
- `python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tmp/cod_etalon_clean.py --card t_3e9518e5 --out C:/x/ground-cod-22/etalon/clean-export-run-v001.json`
  -> wrapper **exit 1**: diagnostic expected `#meters`, actual pymxs name string
  was `meters`; corrected the string normalization, no unit conversion.
- Same command with `clean-export-run-v002.json` -> wrapper **exit 0 / status ok**;
  all three copied scenes exported to new `LP`, `hp`, `scene` diagnostic-clean-v001
  FBX paths. Max 2026.3 / 28.3.0.30732, system metres, scale 1. Native **exit
  4294967166**, existing polyunwrapper startup CLR error and missing Corona plugins
  remain recorded. Wrapper success is **not** native clean-exit or complete-QA proof.
- Clean export reconstructs snapshot positions/faces/material IDs as diagnostic mesh;
  it does **not** preserve UVs/custom normals. Those files are not substitute etalons.
- `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --threads 1 --python-exit-code 1 --python tmp/cod_clean_readback.py`
  -> **exit 0**, three clean diagnostic FBX imported. `tmp/cod-clean-readback.log`.
  Native/clean Ground triangles: **LP 2817 / 2801; hp 48765 / 47677**. The differences
  mean these clean counts must never replace original etalon budgets. All **23 UCX /
  296 triangles** survived hp readback; scene.max selection had only GroundEl, no
  Ground/Main, so that export is not additional Ground evidence.
- Native UV diagnostic on copied LP (`tmp/cod_native_uv.py`, `dcc_batch.py max`,
  `native-uv-run-v001.json`) -> wrapper **exit 0**, native **4294967166** with the
  recorded startup error; wrote `LP-native-uv-v001.json`. Native positions agree with
  node world bounds; no second objectTransform applied. This diagnostic, not the
  UV-less clean exports, supplies the original geometry/atlas sampling below.
- `uv run python tmp/cod_reference_summary.py`, `tmp/cod_atlas_probe.py`,
  `tmp/cod_section.py`, `tmp/cod_footprint_overlay.py` -> each **exit 0**. Copies of
  both root Ground PNGs hashed against the sources; manifest
  `etalon/texture-manifest-v001.json`. `LP-atlas-plan-v001.png` samples the exact
  copied diffuse atlas at original triangle UV barycentres; it is **not a full
  textured render**. Type-6 positions appear on the light paved apron, but no named
  type-6 material identity is established; the approved type-2 fallback stays available.

Etalon normals comparison: **not measured (Blender custom-normals import crash)**.
Original receipts remain intact. No normals requirement on our output was waived.

### New source-authority question, not an environment blocker

The approved boundary is **5101.588000 m2**. The copied footprint drawing still has
no established intersecting authoritative WCS contour (previous probes recorded
zero candidates); the authorized copied-etalon fallback does not directly supply a
labelled ground-floor footprint either:

| Real-source measurement | m2 |
|---|---:|
| Largest SPOZU unhatched component (candidate building hole) | 1670.085519 |
| LP Main upward-face XY union (roofs/overhangs included, not a ground-floor footprint) | 2044.031217 |
| Candidate supported by Main projection | 1667.479134 (99.843937%) |
| Candidate outside Main projection | 2.606385 |
| Main projection over mapped SPOZU coverings | 373.983881 |

The Main mesh includes roofs, overhangs and other merged building details. Simply
using its projection as the footprint would remove **373.983881 m2 of explicitly
mapped coverings**. Using the hatch complement instead is the Vatutino-style
inference, but that is not the approved instruction to obtain a footprint from
this drawing/etalon. Neither option has silently become source truth.
Horizontal mesh sections at native Z=161.5/162/163/164 m polygonized only
1011.97–1016.35 m2 of fragmented wall/room regions; no closed authoritative outer
footprint was recovered by that diagnostic. No convex hull or guessed fill used.

**Decision requested:** approve the orange **1670.085519 m2 SPOZU unhatched
component** as the building hole (recommended, with the 2.606385 m2 etalon mismatch
reported), leaving other unhatched components as lawn; or supply/name the exact
authoritative ground-floor contour and its coordinate transform. Do **not** use
2044.031217 m2 of roof projection as a footprint by default.

Overlay: `C:/x/ground-cod-22/etalon/footprint-authority-v001.png`, SHA-256
`985ce65740ca7b670a16bb32f87cbbc68a4c1f22bded6485dacfbbf8737c4f0b`.
Machine summary with individual input/diagnostic-output hashes:
`C:/x/ground-cod-22/etalon/repair-and-footprint-v001.json`, SHA-256
`249b72a49c2ebb7c780540caba62dcce088680f785642021871f769a4888b459`.
LP/hp diagnostic FBX SHA-256 respectively
`fc8b89d887b206bdbceddca887e125078939a67a4af071e8d3419d62d5a4ad36` /
`d9653191e70336a5449434139c8bc3dfa6be9043fee512826efc7d493c862f6a`.
All large assets/diagnostics remain under the card-authorized external output root.

The importer obstacle is repaired for **diagnostic comparison**, not a new model
acceptance. Parts/build, true material transfer, own-output readback, flatness,
UCX/xView/budget comparison and review publication remain incomplete. No full suite,
PR or pending.json publication: stopping for this source/model decision before build.
