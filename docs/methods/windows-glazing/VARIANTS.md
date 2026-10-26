# windows-glazing - variants

Windows, frames and glass of an OKS (area sheet [docs/domain/areas/windows.md](../../domain/areas/windows.md)).
Benchmarks: kpp1, ac08, tow02 (`benchmark/methods/benchmarks.json`). Our own code only; no team script text.
Driver: `tools/methods/windows/build_variant_blender.py` (factory Blender 5.1.2); geometry:
`tools/methods/windows/windows_variants.py` (numpy). Batch: `tools/methods/windows/run_benchmarks.py`
(build -> package ZIP -> `tools/methods/run_variant.py`, outputs under `C:/x/methods/windows-glazing/`).

Common steps of every variant:

1. Glass source, first that applies: the `*_MainGlass` object (kpp1, 76 polygons); else the Main polygons
   white (> 0.5) at their UV centre on the untiled metallic map, glass white per reg p.9 §5.10 / WIN-08
   (tow02, 1517 polygons); else none (ac08: no glass in the source, `jobs/TEC26-OKS/AC08/MATERIALS.md`),
   so 0 openings and the model is exported unchanged.
2. `extract_openings`: glass polygons sharing an edge and coplanar (5 mm, 5 deg) form one opening; its
   rectangle is taken in the facade frame (u horizontal, v up, n outward from the plan centre). Dropped with
   a reason, never lost: horizontal glass (|n_z| > 0.7), a side under 0.2 m, fill under 0.6, zero area. The
   report lists the dropped polygon count (tow02: 303 of 1517, all "under 0.2 m" slivers).
3. The glass source is removed (the object, or the Main polygons) and replaced by the variant's windows;
   every other source mesh (body, UCX, accessories) and the source materials are kept; a non-mesh object is
   reported in `dropped_objects`. New UVs go to a new UDIM tile (tiled package: highest diffuse tile + 1;
   untiled tow02: tile 1002). The variant's new material gets our generated diffuse (`texture_pixels`),
   written next to the FBX and bound to its Base Color: tiled `<diffuse stem>.<tile>.png` 1024 px, untiled
   `T_<FBX stem>_<Frame|WindowAtlas|FrameTrim>.png` at the side of the single diffuse map (2048 px on tow02),
   packed into the ZIP. Export: triangulated FBX, same settings as the ucx class, to `<stem>.partial.fbx`.
4. Read-back gate before publishing: the partial FBX is imported into a clean scene; every unchanged mesh
   must keep its triangles, slot names and world bounding box (0.1 mm), no mesh may be missing or extra, and
   the new material must sample exactly the written PNG (same file, same sha256) on >= 1 polygon inside the
   new tile. Only then is it renamed to the output; otherwise exit 2 and nothing is published.

Measurement convention: glass = a model mesh named `*_MainGlass` (WIN-13); frame = polygons on a material
slot whose name holds `Frame` (`M_<Addr>_Main_Frame` / `_FrameTrim`; a delivery renumbers them per V012).

## source-as-is (reference row)

- Idea: measure a copy of the benchmark source with the same runner, so every variant is read as a delta.
- Tool: none (copy + package). Script: `run_benchmarks.py` (`BASELINE`). Limits: no build, so no wall time.

## modelled-frames

- Idea: real frame geometry around every opening plus a separate glass object.
- Tool: Blender bmesh ops (`_bmesh_frame` in the driver): per opening, in its own local frame (float32
  safety), `inset_individual` 60 mm ring -> grid `subdivide_edges` into ceil((w - 0.12) / 1.2) panes ->
  `inset_individual` 30 mm per pane (60 mm mullions) -> panes out -> `solidify` 70 mm, centred on the glass
  plane. Panes -> one `SM_<Addr>_MainGlass` (shared pivot, UV 0-1 per pane, WIN-12); frames joined into Main
  (slot `M_<Addr>_Main_Frame`, metric UV 0.25 UV/m or 1 / longest bar).
- Inputs: openings, UDIM tile. Script: `tools/methods/windows/build_variant_blender.py`.
- Limits: the frame sits in the source glass plane with no gap: a body that already has frames or reveal
  faces there overlaps it (xView faces); one profile for every window type; no transoms, no sills.

## atlas-planes

- Idea: one textured quad per opening, no frame geometry and no glass object (NPM `npm_min` style, WIN-03).
- Tool: our numpy code (`atlas_planes`). Window type = width x height rounded to 0.1 m; atlas = g x g cells
  (g = ceil(sqrt(types))) in the new tile with a 2 % margin; the generated diffuse draws frame and glass per
  cell. The quad is in Main (slot `M_<Addr>_Main_WindowAtlas`).
- Inputs: openings, UDIM tile. Script: `tools/methods/windows/windows_variants.py::atlas_planes`.
- Limits: no `MainGlass` (a VPM needs one, WIN-11); the plane is at the source glass plane, not at the
  full opening depth (WIN-03 default 0.4 m); quad corners are not welded to the reveal.

## inset-glass-trim

- Idea: keep the glass where the source has it (its inset), shrink it by 60 mm and draw the frame as a flat
  welded ring (8 vertices, 4 mitred bars) on a trim-sheet strip: frame depth 0, relief baked (reg p.32 §7).
- Tool: our numpy code (`inset_glass_trim`). Ring in Main (slot `M_<Addr>_Main_FrameTrim`), pane in
  `SM_<Addr>_MainGlass`; ring and pane share the inner edge and never overlap (unit test).
- Inputs: openings, UDIM tile. Script: `tools/methods/windows/windows_variants.py::inset_glass_trim`.
- Limits: no reveal is generated (relies on the body's own reveal, WIN-04 not checked); one trim width.

## Reproduce one row

```
uv run python tools/methods/windows/run_benchmarks.py --bench kpp1 --variant modelled-frames \
    --results C:/x/methods/windows-glazing/repro.jsonl
```

All rows: `uv run python tools/methods/windows/run_benchmarks.py` (4 x 3 runs, about 2 minutes).
