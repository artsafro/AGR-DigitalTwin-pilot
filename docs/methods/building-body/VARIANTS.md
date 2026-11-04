# building-body - variants

OKS body mesh (walls, slabs, roof) from the sources (area sheet [docs/domain/areas/body.md](../../domain/areas/body.md)).
Benchmarks: kpp1, ac08, tow02 (`benchmark/methods/benchmarks.json`). Our own code only; no team script text.
Batch: `tools/methods/body/run_benchmarks.py` (source sha256 check -> source readback -> contours -> build ->
`tools/methods/run_variant.py`); outputs under `C:/x/methods/building-body/<bench>/<variant>/`, DCC logs as text
in `docs/evidence/727-building-body/`. Budget [D010]: one mid-poly master <= 150 000 triangles per OKS FBX.

Every standalone writer (`contours.py`, `kernel_prisms.py`, `body_blender.py`, `max_cleanup_pymxs.py`) refuses,
before any side effect, an output or report that is or aliases (same path, hard link, symlink) its input or each
other (exit 4 / RuntimeError, nothing written).

Scope [D187] (user decision 2026-11-02): no drawing-backed input exists in the benchmark set, so every row of this
class is written with `run_variant.py --synthetic <reason>` (`"synthetic": true`, `"synthetic_reason"`; RESULTS.md
lists them under "Synthetic inputs and why"); `run_variant.py` refuses a building-body row without a non-blank
reason. Opening subtraction is a tested capability (variant 2), not measured on the benchmarks. Real DWG plans for
kpp1 / ac08 / tow02 were the follow-up #735; none exists (no DWG plan, no Revit `openings_spec.json`), so all
rows stay synthetic [D194]. RESULTS.md "Synthetic vs drawing" pairs each synthetic row with the drawing row of
the same object and variant (a row without the marker); a missing drawing row reads "not measured", never a number. Re-measure the kept outputs without rebuilding:
`uv run python tools/methods/body/run_benchmarks.py --measure-only` (one row:
`... run_variant.py C:/x/methods/building-body/kpp1/kernel-prisms/SM_Kpp_1.fbx --bench kpp1 --class building-body
--variant kernel-prisms --variant-report <out>.variant.json --synthetic "<reason>"`).

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
  applied; then openings (below); coplanar boolean seams dissolved (0.1 deg), triangulated, FBX.
- Boolean openings: `contours.json` may carry an opening schedule `"openings": [{"id", "min": [x,y,z],
  "max": [x,y,z]}]` (one axis-aligned cutter box per opening, validated fail-closed by
  `tools/methods/body/openings.py`: unknown key, duplicate id, non-finite or empty box -> error naming the opening).
  Each box is subtracted with a Boolean modifier (Difference, Exact), one at a time; an opening that removes no
  volume is an error naming it; the report lists `openings: [{id, removed_m3}]`. Capability tested on a SYNTHETIC
  schedule only (`test_blender_gn_cuts_a_synthetic_opening_and_the_readback_shows_it`: 4 x 4 x 3 m body, 1 x 0.5 x
  1 m notch -> removed 0.5 m3, read-back volume 47.5 m3, still one closed shell).
- Limits: the benchmark rows (R3, R7, R11) cut no opening: the benchmark set carries no opening schedule and no
  plan drawing, and a cutter set derived from the model would be invented architecture; same flat-band and
  courtyard limits as variant 1. On TOW02 (R11) the numbers are two layers of one file, not a stale total
  (source: [#743 report](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/8e28e3f1e99e654f0dd1aea8c6e425b746e12ee1/docs/research/body-gn-triangle-count-boundary.md),
  commit `8e28e3f1e99e654f0dd1aea8c6e425b746e12ee1`):
  - receipt and on-disk FBX `PolygonVertexIndex`: 54,388 triangles;
  - Blender 5.1.2 import `Mesh.validate` removes 14,942 duplicate undirected vertex-key copies (it keeps one polygon per key);
  - public loop-triangle readback and historical R11 `triangles.model`: 39,446.

  The report measured that 14,938 of the 14,942 extras are the opposite winding and 4 repeat the same directed cycle
  (report measurements, not rules of this method). The R11 xView counts were computed after importer deduplication.
  Equal counts do not establish shell or normal equivalence, and neither count is delivery acceptance. Whether the
  receipt format should change and which winding a rebuilt shell keeps are both still unresolved; `triangles`
  keeps its current meaning.

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
