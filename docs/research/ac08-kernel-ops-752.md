# AC08 kernel operations on real geometry: before/after invariants and FBX readback (#752)

Date: 2026-11-02. Branch `improve/issue-752-kernel-real-ac08-before-after-invariants`.
Generated tables: `jobs/TEC26-OKS/AC08/kernel-ops-v001/evidence/kernel_ops.md`, full numbers
`.../evidence/kernel_ops.json`. Binaries (16 FBX, 16 readback JSON, states.json): Google Drive
`G:/Мой диск/AGR-evidence/752-ac08-kernel-ops/`, hashes in `.../evidence/SHA256SUMS.txt`.
Not a delivery verdict: technical QA only, `passed` is not claimed for any delivery.

## Input

Real AC08: `jobs/TEC26-OKS/AC08/max-dump-008.json`, sha256 `f1fc27dc...e45225` (pinned in
docs/experiments/hyp-663.md; Max 2026.3, "04-09 Geometry Final.max", layer 008, metres x 1.0). The driver checks the
hash before and after the run. Node `АС.08` (180 polygons, 193 vertices, UV channel 1, material ids 1/2/3) is split
into its 3 connected components: `AC08_body` (143 quads), `AC08_knob` (12 quads + 12 triangles),
`AC08_plate` (13 quads). The UCX node `Colizii_044` is in the drop list (collision hull). Every op runs on a fresh copy
of the source. Profile VPM-OKS; xView 2 mm / 5 mm; Context() default (no `ground_z`: the source has no ground surface).

## Command

```
uv run python jobs/TEC26-OKS/AC08/kernel-ops-v001/run_kernel_ops.py --work C:/x/ev_t_1483e1fa/v001
```
About 80 s: 19 ops, 17 states, Blender 5.1.2 export (`export_states_blender.py`, polygons + per-corner UV + material
slots) and `tools/blender/fbx_readback.py` once per FBX.

## Before (source)

| part | faces / verts | open edges | non-manifold | zero-area | tri / quad | quad offenders | xView v/f pairs | texel offenders | UV faces |
|---|---|---|---|---|---|---|---|---|---|
| AC08_body | 143 / 152 | 16 | 0 | 0 | 0 / 143 | 0 | 0 / 0 | 79 | 143 / 143 |
| AC08_knob | 24 / 25 | 12 | 0 | 0 | 12 / 12 | 1 | 0 / 0 | 0 | 24 / 24 |
| AC08_plate | 13 / 16 | 4 | 0 | 0 | 0 / 13 | 0 | 0 / 0 | 2 | 13 / 13 |

Kernel visibility on the source scene already fails: `no_visible_back_faces` = 3107 pixels (open body base and the
open knob let rays see inside), 20 open border edges not hidden (16 body + 4 plate), `no_close_overlap` = 0.
Cross-part xView face pairs: 0.

## Operations (kernel verdict and measured candidate after-state)

Applied by the kernel: **0 of 19**. Each op is either refused before any geometry change (3) or rolled back by
`check_operation` (16); the rolled-back candidate was still measured.

| # | op | part | verdict | after: changed part(s) | visibility: back-face px, open borders not hidden |
|---|---|---|---|---|---|
| 1-3 | keep | body / knob / plate | rolled back (source already fails visibility) | unchanged | 3107 -> 3107, 20 -> 20 |
| 4 | primitive_box | knob | rolled back | 12 tri, open 0, UV 0/12 | 3107 -> 3107, 20 -> 20 |
| 5 | primitive_box | plate | rolled back | 12 tri, open 0, texel 4, UV 0/12 | 3107 -> 3107, 20 -> 16 |
| 6-7 | embed_into_neighbour | knob / plate | refused: nothing lies inside the body after 15 mm | - | - |
| 8 | to_opacity_plane | plate | rolled back | 2 tri, open 4, UV 0/2 | 3107 -> 3108, 20 -> 20 |
| 9 | to_opacity_plane | knob | rolled back | 2 tri, open 4, UV 0/2 | 3107 -> 3108, 20 -> 24 |
| 10 | rebuild_by_contour | knob | refused: 4 degenerate triangles collapse under the 0.1 mm weld | - | - |
| 11 | rebuild_by_contour | plate | rolled back | 12 tri, open 0, UV 0/12 | 3107 -> 3107, 20 -> 16 |
| 12 | join_parts | body+plate | rolled back | 156 quads, open 20, weld 0 m, UV 156/156 | 3107 -> 3107, 20 -> 20 |
| 13 | join_parts | knob+plate | rolled back | 37 f, open 16, UV 37/37 | 3107 -> 3107, 20 -> 20 |
| 14 | join_parts | body+knob | rolled back | 167 f, open 28, UV 167/167 | 3107 -> 3107, 20 -> 32 |
| 15 | simplify_part | body | rolled back | 138 f (from 180), open 65, quad offenders 7, UV 121/138, 1 polygon merges material ids | 3107 -> 3107, 20 -> 65 |
| 16 | simplify_part | knob | rolled back | 169 f, open 32, UV 168/169 | 3107 -> 3107, 20 -> 32 |
| 17 | simplify_part | plate | rolled back | 174 f, open 32, UV 170/174 | 3107 -> 3108, 20 -> 32 |
| 18 | move_rigid (11 mm out) | knob | rolled back | faces unchanged, 0 xView, 0 clearance pairs | 3107 -> 3108, 20 -> 28 |
| 19 | move_rigid (11 mm out) | plate | rolled back | faces unchanged | 3107 -> 3107, 20 -> 20 |

Zero-area faces, non-manifold edges and xView pairs (vertex and face, per part and across parts) stay 0 in every
state. Seam ops weld nothing here (max weld 0 m): the three components do not share boundaries.

## FBX readback parity

16 of 17 states exported and read back; 16/16 equal within the declared float32 tolerance (vertices <= 1e-5 m,
area <= edge length x 1e-5 m, UV <= 1e-6, every count strictly). Strictly equal on every count metric: faces,
vertices, degrees, open / non-manifold edges, zero-area faces, twinqa topology defects, quad report, xView pairs,
texel offenders, UV coverage / mirroring, polygon index lists, material slots. Strictly unequal: `area_m2` and
`vertex_max_abs_dev_m` only (max vertex deviation 2.0e-6 m, max UV deviation 0).

## Failures (listed as failures)

1. The source AC08 fails the kernel visibility invariants (3107 back-face pixels, 20 unhidden open borders), so no op
   can pass `check_operation`; with a real ground surface (`ground_z`) part of the open base could be hidden — not
   assumed here.
2. `simplify_part` on the body merges polygons across material ids (1 polygon), loses UV on 17 of 138 polygons and
   raises open edges 32 -> 65; state S15 is NOT exported (no material id may be defaulted).
3. `embed_into_neighbour` (knob, plate) and `rebuild_by_contour` (knob) refuse on this geometry.
4. Ops that rebuild geometry (primitive_box, to_opacity_plane, rebuild_by_contour) carry no UV (0 of N faces).
5. Native 3ds Max xView parity (`tools/qa/xview_parity.py`): **not run** — this card launches no 3ds Max
   (Max-lock / max_exec rules). Repeat on the AC08 L4 building is a separate issue.
