# AGR Tools 0.9.0 — 3ds Max 2024 / 2026

Own implementations. The 0.5.0 diagnostics adapt GeoAGR 13.64 functions with the permission of
their author (Artem). Only the logic in use is adapted (`checks_core.py`), not GeoAGR.ms; no team
scripts or encrypted plugins are distributed.
This is a diagnostic/export-copy tool, not a delivery validator or production job.

## Build and install

`python tools/max/build_agr_tools.py <new-path>/AGR-Tools-0.9.0.mzp` (MZP) or
`python tools/max/build_agr_tools.py --bundle <new-path>/AGR-Tools-0.9.0.bundle.zip` (plugin package:
unzip into `%APPDATA%\Autodesk\ApplicationPlugins`; uninstall = delete `AGR-Tools.bundle` and the
`[AGRTools]` section of `3dsMax.ini`). PNG icons are rendered from the SVG sources with PySide6
(`uv run --with PySide6 ...`), or taken from `AGR_ICON_PNG_DIR`.

Open the panel: menu **AGR Tools** (Max 2025+), macro `AGRToolsOpen`, or
`python.Execute "agr_tools_runtime.panel()"`.

The builder prints SHA256; sorted ZIP_STORED entries, fixed timestamps/permissions,
LF normalization and exclusively created output make repeated inputs reproducible.
Existing files (including input aliases) are never overwritten. No Git LFS.
Drag the MZP into Max or run `fileIn "...mzp"`. Restart for startup registration.
Category **AGR Tools** exposes the actions and **AGR Tools** dialog launcher;
add them to a toolbar with Customize User Interface. Headless installation registers
macros without opening a dialog. No Python dependencies need to be installed in Max.

## Rollout (text)

```
AGR Tools
[xView check]
[Pre-export clean-up (dry-run)]
[Apply preview to new export copies]
[MatID check]
[UV integer-tile nudge (dry-run)]
[Apply UV nudge to new export copies]
[UDIM -> NPM atlas (dry-run)]
[Apply NPM atlas to new export copies]
[UCX collision (dry-run)]
[Apply UCX to new export copies]
[Texel readout]
[Checked export]
[Names check NPM/VPM]
[Triangle limits per FBX]
[Textures check (all objects)]
[Pivot check]
[GeoJSON check]
<JSON report in Listener; offending object names and component IDs>
```

Selection is checked when nonempty; otherwise all geometry. Unsupported objects,
empty scenes/meshes, failed native checks and missing UV channel 1 are errors,
never a clean result. Objects are identified by unique Max handles as well as names.

- **xView check**: native OverlappingVertices at **2 mm**, OverlappingFaces at
  **5 mm**; check evaluated temporary copies, select original offending objects.
  Scene units are converted; native tolerance values are restored. Unbaked
  uniform/nonuniform/mirrored and parent transforms are baked only on a detached
  disposable copy before checking physical distances (Reset XForm + collapse). No topology
  conversion of working objects. Pilot #370 / BODY-J/K; native xView semantics,
  not the kernel's additional projected-area diagnostic. Exactly 2 mm vertices
  follow native Max's strict boundary; a float32 ambiguity band (relative 2e-7)
  around exactly 2 mm returns an explicit error, never clean, without changing
  either native finding threshold. A face ambiguity-only probe at 5 mm ×
  (1 + 2e-7) rejects additional near-boundary faces with an explicit error; its
  results never become findings. The kernel intentionally uses inclusive vertices.
- **Pre-export clean-up**: first shows a dry-run from the existing
  `twinqa.export_hygiene.repair_plan` (generated stdlib-only slice, not a rewrite).
  CA owners: node, base, modifiers, recursive material tree; clear UDP except map
  names; name channel 1 `UV`; remove extra map channels per the existing hygiene
  policy (reg p.31 §2.1.1 / pilot #547). Apply requires an unchanged preview and
  creates independent export-copy nodes/materials; it never cleans originals.
  Reports planned actions and re-inspected results. Nothing is saved/exported.
- **MatID check**: face IDs >= **1001**, unassigned ID 0, missing materials,
  unresolved or empty Multi/Sub slots, and a face ID not listed in `materialIDList` even when the FBX
  export would wrap it (`empty_slot`, #844); lists face IDs and selects offending nodes.
  Pilot #548 / D030. This is not the complete semantic 1–35 reading-scheme gate;
  no arbitrary ID remapping, empty-slot fallback or UDIM renumbering is done.
- **UV integer-tile nudge**: dry-run reports channel-1 islands and integer period
  steps from the bundled `uv_nudge.py` slice. Each material needs an explicit
  node user property `AGR_UV_PERIODS` (`name=pu,pv` or `name=none`, `;` between
  entries). A missing name is an error naming that material. Optional
  `AGR_UV_TARGET` (default tile 1001, the library default). Apply writes the
  shifted channel-1 coordinates on a new export copy and reads them back.
  Originals stay untouched. A zero step is not a finding.
- **UDIM -> NPM atlas**: dry-run reports the UDIM tiles and the atlas cell
  layout from the bundled stdlib port of `npm_atlas_udim.py`. Apply remaps
  channel 1 on a new export copy and, when the material has a diffuse bitmap,
  binds the generated atlas (diffuse, plus a separate opacity bitmap when the
  packer emits one). Flat Kd colours stay flat colours. Diffuse alpha, material
  opacity and a grey opacity map follow the Python tool. `map_d` without
  `map_Kd` raises `map_d without map_Kd is not supported` before any copy is
  created. Bitmap coordinates are supported only when they are neutral:
  U/V tiling 1, U/V offset 0, U/V/W angle 0, U/V mirror off, U/V tile on
  (the default), map channel 1. Any other value, a non-finite number
  (NaN or infinity), or a coordinate that cannot be read raises
  `unsupported map coordinate: <material name> <map slot> <setting>=<value>`
  in the dry-run, before any export copy, atlas file or replacement material
  is created. The slot is `diffuse` or `opacity`. Floats match within 1e-9.
  A non-neutral transform is never baked into a clean atlas. Required node properties: `AGR_ATLAS_MODE` (`ground` or `oks`) and
  `AGR_ATLAS_SIZE` (`1024` or `2048`). Inputs the Python tool refuses (tile
  crossing, unmapped material, empty mesh, non-finite coordinates, padding
  below 8 px, both diffuse alpha and `map_d`) raise a named error. UV readback
  must match the Python tool within 1e-6; a difference of exactly 1e-6 is an
  error. Bitmap pixels are read one scanline at a time. Atlas PNGs are saved
  at gamma 1 with `outputColorConversion:#noConversion`, so an OCIO scene
  keeps the stored 8-bit pixels and alpha.
- **UCX collision generator**: dry-run reports the variant
  `docs/methods/ucx-collisions/WHEN.md` recommends for the object kind, the
  piece count, and the triangles against the [D012] limit, then the bundled
  UCX audit verdict. Geometry is the evaluated world-state mesh in metres
  (`snapshotAsMesh`, including the node transform and the modifier stack).
  With no modifiers that mesh must match object-space vertices times
  `objectTransform`; a mismatch is an error. A near-convex box uses
  single-hull: the convex hull of the vertices, not their axis-aligned box.
  A flat hull (volume below 1e-6 m³) is still thickened to the facade box;
  a volume of exactly 1e-6 m³ is `at_threshold`. A passage or other
  non-convex body (facade-frame volume more than 5% outside the mesh) uses
  kernel-boxes. A near-convex body with 2 to 6 level bands uses slice-prisms.
  The outside fraction exactly at 5% is `at_threshold` and is an error.
  Optional node property `AGR_UCX_KIND` (`near-convex-box`, `passage`,
  `non-convex`, `tight-budget`, `few-levels`) overrides the measurement.
  `part-boxes` and `part-hulls` are not offered: an unmapped kind is an error
  that names it. Apply writes the collision onto a new export copy
  (`<mesh>_AGR_ucx_`). Each piece is named `UCX_<export>_NN`, bound to that
  export mesh: source `name_control` produces `name_control_AGR_ucx_` and
  `UCX_name_control_AGR_ucx__01`. The export name and every piece name are
  reserved, and the piece audit must pass, before any node is created. A
  failed audit raises `ucx audit failed` and creates nothing. If the export
  name or any piece name is already in the scene, or two selected meshes
  would claim the same name, apply raises `occupied name <name>` before
  creating a node. The emitted node's world bounds are read back.
  Originals stay untouched. A preview is kept only while the evaluated
  geometry, transform, handle, name and properties still match; a 10 m move
  is a stale preview and creates nothing. A triangle count exactly
  equal to the budget is a failure, never a pass. The audit name mask is
  shown in the verdict; these button names are `UCX_<export>_NN`.
- **Texel readout**: read-only min and median px/m per mesh and per material.
  The node needs `AGR_TEXEL_PROFILE` (`NPM` or `VPM`) and `AGR_TEXEL_MAP`
  (`name=pixels`, `;` between entries). A missing material name is an error
  that names it. Nothing in the scene changes. Values match
  `texel_density_readout.py` within a relative 1e-6; a difference of exactly
  1e-6 is an error. Bands are the locked intervals, inclusive at the edges:
  VPM 512–1706 px/m and NPM 10–40 px/m. A zero area or a zero map size is
  `at_threshold` and is an error.

## 0.9.0 placement, Flora/MAF, textures, checks, batch export and light (#979)

Nineteen buttons of plan version 0.9, in the block tabs under «Проверить и выделить» (read / select) and
«Исправить — копии / undo / новые файлы», each a `runtime.ui('<tool>')` macro, a menu entry and an MCP tool
`agr_<block>_<name>` (MCP: `mode: preview` only):

- place: `place.replace` and `place.drop_to_ground` (one Undo record), `place.schedule`, `place.flora_repair`
  (copies), `place.maf_checks` (read);
- textures / UDIM / atlas: `tex.erm_normal_check`, `udim.slots` (read), `tex.finish_map`, `udim.matid_unwrap`,
  `atlas.groundel` (copies), `atlas.flora` (new files);
- checks: `qa.address`, `qa.normals`, `qa.sintez`, `qa.facade_compare`, `qa.procedural_objects` (read);
- export / scene / light: `export.batch` (new files), `scene.maps_usage` (read), `light.check` (selects the
  offenders, one Undo record restores the selection).

Thirteen shipped buttons were reworked after the team-script audit and lab 0.9 (L05–L08): `tex.format_fix`,
`tex.placeholders`, `scene.missing_maps`, `qa.names_fix`, `ucx.triangulate`, `export.pivot_place`,
`udim.ids_to_udims`, `export.zip`, `qa.package`, `export.cleanup`, `qa.zero_area`, `scene.census` and the 0.2
atlas `atlas.npm`, which now packs on the `npm` profile: the atlas shrinks to its content at the same texel
(Ground 35 px/m), the diffuse is a 24-bit RGB PNG and the opacity a separate 8-bit grey PNG, both new files whose
headers are read back. Behaviour changes for 0.8 users are listed in `CHANGELOG.md` (0.9.0).

## 0.8.0 delivery edits on copies (#908)

Thirteen buttons of plan version 0.8 in the section «Сдача (копии)» and in their block tabs, each a
`runtime.ui('<tool>')` macro and an MCP tool `agr_<block>_<name>`: `scene.missing_maps` (read-only),
`model.triangulate`, `ucx.triangulate`, `ucx.rename`, `export.pivot_place`, `tex.format_fix`,
`tex.placeholders`, `qa.names_fix`, `udim.ids_to_udims`, `qa.package` (read-only, pilot validator),
`export.ground_fbx`, `export.geojson_write`, `export.zip`.

Every editing button works in two presses: **preview** (nothing changes, the report lists `done`,
`skipped` with a reason and `ambiguous`) and **apply**, which accepts only the preview of the same tool
and selection and refuses when its hash or the scene state changed (`edit_core.py`). Edits go to export
copies (`*_AGR_export_*`, own layers) or to new files; nothing is overwritten (`new_path()` versions or
refuses). One run = one Undo record, the selection is restored; an error inside the run is re-raised
after the Undo record closes. Only `ucx.rename` renames UCX nodes in place (one Undo record).
MCP: editing tools take `mode: preview`, and `mode: apply` only with that preview.

## 0.7.0 pre-delivery checks, rail and «Путь» (#860)

Twelve read-only checks (plan version 0.7), each a button of its block tab, a `runtime.ui('<tool>')`
macro and an MCP tool `agr_<block>_<name>`. Full button help (what, when, mode, requirement ids) is the
«Путь» tab in the panel and `docs/agr-tools/GUIDE.md` in the repo; both are generated from
`agr-tools-suite.json`, which ships in this package. Inputs: `AGR_EXPORT_PATH` (FBX kind, no default),
`AGR_ZERO_M` (±0.000 in metres for the perimeter drop, no default), `AGR_ROOF_SET=1` (one extra texture set
for a usable roof). Thresholds are pinned to `standards/*.yaml` by `tests/max_tools/test_agr_tools_suite.py`.

## 0.5.0 diagnostics (read-only)

The five buttons never edit the scene. They read `snapshotAsMesh` copies, `usedMaps` and PNG headers
on disk. The model kind (NPM/VPM, OKS/Ground) comes from each node's `AGR_EXPORT_PATH` FBX name.
A node without a mappable FBX name gets `fbx_unmapped`; it is never given a default kind. A value
exactly at a limit is `tri_at_limit` / `at_threshold`, which is a finding, never a pass. Skipped
items are listed in `plan.dropped` with a reason. Defects D1-D8 and the source lines are in
`CHANGELOG.md`.

Review-level codes count as non-pass. Every review-level code in this package is
`at_threshold`, `tri_at_limit`, `name_conflict` and `tex_overlap_review`
(`REVIEW_CODES` in `checks_core.py`). A report whose only finding is
one of them has status `fail`, and a person reviews that finding. The schema stays
`pass` or `fail`. A `review` status may come later only if the UI needs it.

| Requirement id | Button | Status in 0.5.0 |
| --- | --- | --- |
| NPM-1.3-2.b, VPM-1.3-2.b, NPM-2.10-2, VPM-2.10-2.a | Names check | checks (Latin, digits, `_`; space/dot/Cyrillic named) |
| NPM-1.3-3.b, NPM-1.3-4, VPM-2.10-2.b, VPM-2.10-3 | Names check | checks (capital letter, digits apart; address dictionaries not shipped) |
| NPM-2.10-1, VPM-2.10-1 | Names check | checks (≤ 254) |
| NPM-2.10-3.3.a-c, NPM-2.10-3.4.a-b, NPM-2.10-3.5.a | Names check | checks (SM/T/M masks, OKS 001..020, SlotNumber 1..7) |
| NPM-2.10-3.5.b | Names check | review (`name_conflict`, conflict #17) |
| VPM-2.10-4.3, VPM-2.13-1.d | Names check | checks (T_…_{Diffuse,ERM,Normal}_{Slot}.{UDIM}; UCX_SM_…_Main/Ground_NNN) |
| NPM-2.3-6.a, NPM-2.3-6.b | Triangle limits | checks per FBX (150 000 / 180 000) |
| VPM-2.3-9, VPM-2.3-10 | Triangle limits | checks per FBX (1 000 000 without UCX; Ground by `AGR_SITE_AREA_HA`) |
| VPM-2.13-7.a | Triangle limits | checks (UCX budget, conflict #3 formula) |
| NPM-2.5-1.a, NPM-2.5-2.a, NPM-2.5-3, NPM-2.5-5 | Textures check | checks (PNG, 256..2048 square, ≤ 3 MiB, no alpha) |
| NPM-2.5-4 | Textures check | checks (≥ 8 px between islands of one atlas, across the objects of one FBX) |
| VPM-2.5-1.2, VPM-2.5-1.6, VPM-2.5-1.9, VPM-2.5-1.4.a | Textures check | checks (2048/4096 or 256 placeholder, alpha only in Diffuse, 8 bit, D+ERM+N per tile) |
| VPM-2.5-1.5 | Textures check | checks (16 px at 2048, 32 px at 4096, per atlas and UDIM tile) |
| — (3ds Max 2026.3 FBX export, measured #827) | Textures check | resolves a face matID outside `materialIDList` as the export does: wraps by the highest listed ID, `(id - 1) mod n + 1`, then that ID must be listed; advisory `tex_matid_wrapped` (`matID 3 -> sub 1`). The MatID check and export `empty_slot` do not wrap: an unlisted ID blocks (#844) |
| VPM-2.5-1.5 (repeating islands), VPM uv.repeating_islands_may_overlap | Textures check | review (`tex_overlap_review`: touching or overlapping VPM islands; padding applies only to islands with unique images) |
| VPM-2.5-2.1.3.a | Textures check | checks (UDIM from 1001 without gaps) |
| VPM-2.9-4.b, VPM-2.9-5 | Pivot check | checks (Z = 0 and one pivot per FBX, 1 mm) |
| VPM-2.9-4.c | Pivot check | UCX dropped with reason |
| VPM-2.9-4.a | — | not covered (X/Y centre; contradicts VPM-2.9-5 for glass) |
| VPM GeoJSON passport (`twinqa.geojson`) | GeoJSON check | checks via the pilot checker |

GeoJSON check opens a file dialog and runs `twinqa.geojson` in the project Python. The Python is
`AGR_PYTHON`, or `<repo>/.venv/Scripts/python.exe` when it is unset. A missing file, a wrong extension,
a broken JSON file or a crashing checker is reported as a `fail` finding, not raised as an error.

## Headless evidence

Run the synthetic fixture runner through the shared `dcc_batch.py max --file ...`
wrapper, never directly through 3dsmaxbatch. See `tests/max_tools/` and the committed
text evidence. Only new synthetic fixture copies are opened; no production asset.
An exit-zero wrapper alone does not prove a fixture pass: the runner asserts exact
results, writes the report exclusively and emits a completion marker at the end.

- **Checked export**: one button. The first press is a dry-run and writes
  nothing. The second press, on the same selection, writes one FBX when every
  gate passed. The node needs `AGR_EXPORT_PATH`, a new file path. An existing
  file, or a path that is the same file as the scene, the report or the
  `.partial` temp path, is refused and nothing is written. Gates run on every
  emitted copy, render meshes and `UCX_` hulls, in this order: pre-export
  clean-up preview, MatID check, xView gate, UCX audit when `UCX_` pieces are
  in the selection, then texel readout (report only; an out-of-band density
  does not stop the export). Extraction follows that order: cleanup is decided
  before any material read; MatID evidence (material name and empty slots) is
  read only after cleanup passes; texel is read only after cleanup, MatID,
  xView and UCX have all passed. A finding names only the node that failed.
  The Python CLI
  has no geometry writer: it exits nonzero with `unsupported writer` and
  creates no file. Only the Max exporter writes the FBX, and each exported
  copy keeps the planned node name (`SM_body`, `UCX_SM_body_01`), not an
  auto-renamed suffix. A failing
  gate stops the export and lists the gate, object names and component IDs.
  The FBX is binary 7.4, metres (`UnitScaleFactor` 100), Z-up. A JSON report
  is written beside it. Readback of object count, triangle count, material
  count and unit scale must equal the dry-run; a mismatch is an error in the
  report. Originals are not edited. The collision generator and the texel
  readout remain the 0.3.0 buttons above.

## Roadmap

First rollout complete: xView, pre-export clean-up, MatID, UV integer-tile
nudge, UDIM to NPM atlas, UCX collision, texel readout and checked export.
0.5.0 adds read-only names, triangle, texture, pivot and GeoJSON diagnostics.
0.7.0 adds 12 read-only pre-delivery checks, the block tab rail and «Путь».
0.8.0 adds 13 delivery edits on export copies / new files with preview → apply.
0.9.0 adds 19 buttons (placement, Flora/MAF, textures/UDIM/atlas, checks, batch export, light) and reworks 13.
No licensing, obfuscation, GeoAGR.ms copy or decryption is included.
