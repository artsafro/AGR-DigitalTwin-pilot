# vyatskaya-tow02 review (#514): our export-v005 vs the user's hand-finished 013_Main

Date 2026-10-21. Read-only on both models; evidence in git-ignored `outputs/review-v002/` (`diff/DIFF.md`,
`xview/*.json`, `xcheck/XCHECK.md`, `time/TIME.md`). The user's files were hashed before and after every run, unchanged:
`for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` `2fd80081…1da68`, `for_placement/sceene.max` `d4e20926…59f5`
(whole site, 40 objects; 013 = `SM_Vyatskaya_Vl_47_49_013_Main`, Editable Poly; 014 = its mirror). Ours
`export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbx` `ff8994dc…080a`.

## 1. What the user changed (measured)

Frames: the user's 013 = ours + translation (4951.864, 14903.346, 165.443) m; 92.4 % of vertices within 0.1 mm.

| Change | Where | Numbers | In the user's list |
|---|---|---|---|
| Top-floor overlaps removed by topology | band199 + top glass, z 65.4-76.25 | 153 of our 185 xView faces stay within 1.1 mm; top tris 5 584 -> 5 320, one facet 60 -> 4 tris | yes (under-cut, extra edges) |
| Top ledge/walls moved | top, z 72.16-76.23 | ~31 m2 moved 31-35 mm along the normal | yes |
| Balcony glass railings rebuilt | 37 units, z 11-66.6 | shell 20 mm -> 8 mm off the coping, 1 333 -> 3 956 tris | yes |
| Roof / terrace glass railings moved | z 69.4-77.6 | ~77 m2, 30-110 mm along the normal | yes (railings) |
| Colours | coping 283 m2, roof 27 m2, band199 | textures pixel-identical; UV moved to a dark atlas area outside every layout rect (163 -> 48), 3.34 px/m | yes (UV, colours) |
| Fins sunk | all 26, bottoms z 0 -> -0.808 | 26 m2 bottom caps gone, 124 m2 new | **no** - question 1 |
| Louvre bottom row raised | z 6.900 -> 6.932 | 138 tris; removes the 16 louvre/soffit contacts | no (overlap fix) |
| Body wall quads removed | z 51.8-57.8 | 9 quads, user surface 153 mm behind | **no** - question 2 |
| Windows, body, soffit | - | body_glass max 0.03 mm, UV shift 0 | yes (kept) |

## 2. xView (3ds Max 2024, separate instance, `scripts/xview_review.ms`, Faces 5 mm / Vertices 2 mm)

| Model | Faces | Vertices | Note |
|---|---|---|---|
| ours export-v005 (poly) | 185 | 0 | full list `xview/ours_v005.keep` |
| ours, Mesh + Weld 2 mm | 341 tris | 0 | weld merges 0 vertices: our defects are topology, not doubles |
| user 013, FBX (tris) and sceene.max (poly) | 0 | 10 | 5 coincident pairs (0.0 mm) at band corners z 69.45 / 76.25 |
| user 013, Mesh + Weld 2 mm | **0** | **0** | 5 vertices merged; the user's pre-export step |
| user 013, Mesh + Weld 2 mm, back to Poly | 0 | 10 | Poly splits the non-manifold corners again (user, 2026-10-21) |

The user's model is the NPM base after "Mesh + Weld 0.002 m" before export; never round-trip it through Editable Poly.
Weld fixes Overlapping Vertices only, never Overlapping Faces (user, 2026-10-21).

Where our 185 faces were: band199 141 (edge-on-edge, T-vertex and point contacts at the unwelded band/glass joints),
top glass 12 large faces (~278 m2, same contacts), louvre/soffit 18 at 6.9, AC railing glass / baskets / coping 10,
coping/railing 2 at 69.5.

## 3. Checkers against xView on the same meshes (`xcheck/XCHECK.md`)

| Checker | ours (185 truth) | user (0 truth) | Time on ours |
|---|---|---|---|
| `dt_ai.ops.inv_xview` `xview_faces` (main since #370, 2026-10-20 14:24) | 185 / 0 FP / 0 FN | 0, vertices 10 = xView | 52 s, no DCC |
| user's Blender add-on `xview_overlapping_faces_improved.py`, 5 mm | 40 / 0 FP / 145 FN | 0 | 16 s |
| our builder's Blender check (area rule, xview-v002/v004) | 0 | - | - |

The add-on skips boundary-only contact (136 FN) and gates normals by face size (0.08-0.23 deg vs xView 0.81 deg, 9 FN):
a hit is real, a 0 is not a pass. `inv_xview` must be run on local coordinates (float32 site coordinates give 3 FP).

## 4. Why our checks missed each defect

| Defect the user fixed | Our check said | Cause class | Cause |
|---|---|---|---|
| 185 contact overlaps (top, louvre, railings) | 0 / 0 | **wrong tool** | A job-local Blender check (projected area > 0) instead of `inv_xview` (contact rule, 185/185); the branch was cut before #370 and synced with main only after the job (`fd399e7`, 2026-10-21 20:38); `docs/domain/validation.md` already described the rule |
| Fallback to Blender at all | "tolerances are dialog-only" | **wrong conclusion** | xView 0.01 m default seen once; `OverlappingFaces.tolerance` was settable (found later, xview-v005) |
| Fix loop stopped twice (v019-v025, v026-v030) | Blender 121 -> 0 | **early stop** | stop criterion was a metric never calibrated against xView |
| 304 T-vertices + 12 bow-tie point contacts left "by design" | allowed | **wrong conclusion** | contacts of separate parts in one joined mesh are xView overlaps; weld at export does not remove them. The 12 bow-tie corners (user decision 2026-10-21: not welded) were moved 3 mm into the wall (`skip_point_contacts`) - less than the 5 mm face tolerance, so xView still flags them: a separation must exceed the tolerance, or the contact must be rebuilt |
| Balcony railing shell 20 mm off, 4 mm from baskets | 0 | wrong tool | same as row 1 (4-12 mm gaps, contact rule) |
| Coping / roof colour | - | open | question 3 |

## 5. Time (`time/TIME.md`, estimates)

35 h 22 min wall-clock, ~11 h 40 min without waiting for the user, ~8 h 20 min of agent work. First pass 54 %, rework
after feedback 32 %, QA 10 %. Top sinks: overlap QA in the wrong tool (218 min wall, 10-21 12:00-15:38, and the user's
hand finish still needed); the engine route on a shell-less panelised source (90 min, day 1); the main session idle
on long background agents (13 waits, ~223 min) and re-derivation after lost cfg / context.

## 6. Questions for the user

1. Fins sunk 0.808 m below z 0: a rule for placement on relief (all towers, which depth) or this site only?
2. 9 body wall quads at 51.8-57.8 removed: what was wrong there (duplicate behind another surface?)
3. Coping, roof and band199 moved to the dark atlas area: is dark the source colour (our mapping error) or a design choice?
