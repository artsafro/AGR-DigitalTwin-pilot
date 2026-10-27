# building-body - variants

OKS body mesh (walls, slabs, roof) from the sources (area sheet [docs/domain/areas/body.md](../../domain/areas/body.md)).
Benchmarks: kpp1, ac08, tow02 (`benchmark/methods/benchmarks.json`). Our own code only; no team script text.
Batch: `tools/methods/body/run_benchmarks.py` (source sha256 check -> source readback -> contours -> build ->
`tools/methods/run_variant.py`); outputs under `C:/x/methods/building-body/<bench>/<variant>/`, DCC logs as text
in `docs/evidence/727-building-body/`. Budget [D010]: one mid-poly master <= 150 000 triangles per OKS FBX.

Shared "drawing" input of the two from-contour variants (`tools/methods/body/contours.py`, written to
`C:/x/methods/building-body/<bench>/contours.json`, marked `"synthetic_drawing": true`): the benchmark set has
no DWG plan per object, so plan contours and level heights are **measured from the source mesh**, the same
way for every variant. Levels = z of horizontal faces holding >= 5 % of the largest horizontal area (0.05 m
rounding, levels closer than 0.5 m merge) plus the lowest / highest vertex; per band the sections at 5 / 25 /
50 / 75 / 95 % of its height are grown by 0.75 m, their outer outline filled and shrunk back (wall gaps up to
1.5 m close), united with the band's own caps (faces looking down at its bottom level, up at its top level), simplified by 2 cm; pieces
under 0.5 m2 are dropped and listed. kpp1: 9 bands, ac08: 2, tow02: 13; no empty band.

## 0. source-as-is (reference)

- Idea: the benchmark source FBX itself, measured the same way; every other row reads against it.
- Tool: none (copy). Script: `tools/methods/body/run_benchmarks.py` (`BASELINE`).
- Limits: no build, so no wall time (null with the reason).

## 1. kernel-prisms - our kernel from drawings

- Idea: one closed prism per level band and plan contour, stacked; the body from plan contours + level heights.
- Tool: our kernel `dt_ai.ops.contour.extrude_polygon` (numpy + shapely constrained-Delaunay caps, holes kept,
  outward normals; the `contour_rebuild` operation's backend, `src/dt_ai/ops/contour.py`); Blender only writes
  the FBX (`body_blender.py export-mesh`).
- Inputs: `contours.json`. Steps: `tools/methods/body/kernel_prisms.py <contours.json> <mesh.json>` -> FBX with
  one mesh `<stem>_Main`, one material slot.
- Limits: prisms are not welded or unioned, so adjacent bands touch with coincident caps (xView overlapping
  faces); no openings, no decor, no roof slope (flat band tops); inner courtyards are filled by the contour step.
  The `src/dt_ai/parts` module named in the issue is the parts-list model (gate 1), not a geometry builder; the
  geometry primitive of our kernel is `dt_ai.ops.contour`.

## 2. blender-gn-union - Blender Geometry Nodes from level contours

- Idea: the same contours, extruded per level and unioned into one shell in Geometry Nodes.
- Tool: Blender 5.1.2 bpy + Geometry Nodes. Script: `tools/methods/body/body_blender.py gn-union`.
- Steps: band polygons -> cap faces at z0 (`mathutils.geometry.tessellate_polygon`, holes kept), face attribute
  `band_h`; node tree Extrude Mesh (faces, offset = (0, 0, band_h)) + Flip Faces of the caps as bottoms -> Join
  -> Merge by Distance 0.01 mm -> Mesh Boolean Union (Exact, self intersection) -> Merge by Distance 1 mm; modifier
  applied, coplanar boolean seams dissolved (0.1 deg), triangulated, FBX.
- Limits: "boolean openings" of the issue are not cut: the benchmarks carry no opening schedule (no DWG), so the
  cutter set would be invented; same flat-band and courtyard limits as variant 1.

## 3. max-pymxs-cleanup - 3ds Max pymxs edit-poly clean-up of the supplied FBX

- Idea: keep the supplied body and clean it: weld, isolated vertices, open borders.
- Tool: 3ds Max 2026.3 pymxs in `3dsmaxbatch` through `~/hermes_kanban/scripts/dcc_batch.py` (shared lock),
  on a copy of the source (`source_copy.fbx` next to the output). Script: `tools/methods/body/max_cleanup_pymxs.py`.
- Steps: import FBX; every non-UCX geometry object -> Editable Poly, weld vertices within 1 mm (system units via
  `units.decodeValue`), delete isolated vertices, Cap Holes modifier, collapse; UCX left as imported; FBX export.
- Limits: inherits every source fault it does not target (overlaps, inner faces); Cap Holes closes any open border,
  including an intended one; ~45 s Max start per object.

## 4. Revit export clean-up - not measured

- Not measured: the issue allows it only when a Revit-exported FBX is among the benchmark sources and no live
  Revit session is used. kpp1's `source_origin` is "Revit -> FBX (job scripts)", but its benchmark FBX is the
  finished VPM package v005 (already cleaned by the job scripts), not the raw Revit export; ac08 is "DWG
  drawings -> model", tow02 a supplied FBX. No raw Revit FBX exists in the benchmark set.
