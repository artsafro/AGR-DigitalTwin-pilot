# AGR Tools 0.3.0 — 3ds Max 2024 / 2026

Own implementations only; no team scripts or encrypted plugins are distributed.
This is a diagnostic/export-copy tool, not a delivery validator or production job.

## Build and install

`python tools/max/build_agr_tools.py <new-path>/AGR-Tools-0.3.0.mzp`

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
  unresolved or empty Multi/Sub slots; lists face IDs and selects offending nodes.
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

## Headless evidence

Run the synthetic fixture runner through the shared `dcc_batch.py max --file ...`
wrapper, never directly through 3dsmaxbatch. See `tests/max_tools/` and the committed
text evidence. Only new synthetic fixture copies are opened; no production asset.
An exit-zero wrapper alone does not prove a fixture pass: the runner asserts exact
results, writes the report exclusively and emits a completion marker at the end.

## Roadmap (not implemented)

Checked export. It needs its own fixtures, profile gates and measured
comparisons before adding a button. The collision generator and the texel
readout are the 0.3.0 buttons above. No licensing, obfuscation or GeoAGR
source/decryption is included.
