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
| Fallback to Blender at all | "tolerances are dialog-only" | **wrong conclusion** | xView 0.01 m default seen once; `OverlappingFaces.tolerance` was settable (found later, xview-v005; `tools/qa/xview_dump.ms:24-33` on main since #380 already did it) |
| Fix loop stopped twice (v019-v025, v026-v030) | Blender 121 -> 0 | **early stop** | stop criterion was a metric never calibrated against xView |
| 304 T-vertices + 12 bow-tie point contacts left "by design" | allowed | **wrong conclusion** | contacts of separate parts in one joined mesh are xView overlaps; weld at export does not remove them. The 141 band/glass pairs all appear at build-v017 (`clean_glass`, §7 D); the 12 bow-tie corners (user decision 2026-10-21: not welded) moved 3 mm (`skip_point_contacts`, sized against the 2 mm vertex tolerance, not the 5 mm face one) only add hits to 11 of those pairs |
| Balcony railing shell 20 mm off, 4 mm from baskets | 0 | wrong tool | same as row 1 (4-12 mm gaps, contact rule) |
| Coping / roof colour | - | open | question 3 |

## 5. Time (`time/TIME.md`, estimates)

35 h 22 min wall-clock, ~11 h 40 min without waiting for the user, ~8 h 20 min of agent work. First pass 54 %, rework
after feedback 32 %, QA 10 %. Top sinks: overlap QA in the wrong tool (218 min wall, 10-21 12:00-15:38, and the user's
hand finish still needed); the engine route on a shell-less panelised source (90 min, day 1); the main session idle
on long background agents (13 waits, ~223 min) and re-derivation after lost cfg / context.

## 7. Root causes in the builder (`outputs/review-v002/rootcause/RAILINGS.md`, `LOUVRE_TOP.md`)

`inv_xview` on export-v005 (local coordinates): 166 pairs = the 185 xView faces. Per case: where the math broke.

| Case | Code | Where the math broke | User's fix | Rule |
|---|---|---|---|---|
| A. Roof / terrace glass vs coping | `build_top_blender.py` `coping_path` / `sweep_coping` l.1135-1252 (inner face = simplified wall line - constant `inner_m` 0.73); railings from their own polyline l.1381-1402; `fix_overlaps_blender.py` F12 l.535 | Two independent values coincide: railing setback from the coping path 0.7300 = `inner_m` 0.73 -> 10 coplanar faces; F12 then cleared 6 mm only at the overlap centroid of a 0.19 deg tilted face, leaving the near end at 0.62 mm | glass moved onto the coping top, 54-124 mm from the inner face (source 107-129 mm) | coping inner edge from the measured footprint; glass placed by the source relation; every vertex >= 10 mm from a parallel face of another part |
| B. AC basket glass vs basket front / coping | `build_decor_blender.py` `build_ac` l.228-313 (glass and basket from two separate envelopes, DP 12 mm each); `build_review_fixes_blender.py` `build_glass` l.343 (shell 20 mm, 5 mm embeds into floor and coping); F13 l.643 | Source gap 6.5 mm became 4.1-5.6 mm through two DP-12 mm simplifications; the 5 mm embeds make the faces share a z band; F13 moved the glass ends 3 mm and not the coping: 6.9 mm -> 3.9 mm (2 new pairs) | front = our inner face, shell 8 mm, 24-25.5 mm behind the basket front (slats show) | glass derived from the basket front (-25 mm, 8 mm shell); a fix moves every parallel neighbour within 10 mm by the same vector |
| C. Louvre bottom rails vs soffit, 6.9 | `build_review_fixes_blender.py` `build_louvre` l.444 (`rails_z[0]` = 6.900), l.517 embed 12 mm; `build_decor_blender.py` `build_soffit` l.719 (= body loop 6.900) | One level value feeds two parallel faces of different parts (0.000 mm apart); the 12 mm embed puts the rail end over the soffit | bottom rail box raised 32 mm | never reuse another part's face level for a parallel face; >= 6 mm off, embed only through perpendicular faces |
| D. band199 vs top glass, 68.9 / 75.7 | `clean_glass_blender.py` `clean` l.35-60 (build-v017: top_glass 509 -> 86 quads, TOW02_top untouched); `join_export_blender.py` weld 1e-5 m, `skip_point_contacts` 3 mm | The simplification changed one side of a shared seam (glass top edge -> 2 corners) and kept 1-30 band vertices on the other: 129 T-vertices 0-2.2 mm off the glass plane; build-v016 had 0 contact pairs, v017 141 | band strip one quad per facet on the glass corners (282 -> 24 tris), bow-ties collapsed to their midpoint | a simplification is applied to both sides of every shared seam in the same step; at join every vertex within 5 mm of a parallel face is welded into it or >= 6 mm away |

Common to all four: our checks sampled 7 points per face and measured the gap at the overlap centroid with an area > 0
rule, so boundary contact, edge bands and tilted ends were never candidates. The per-vertex contact rule of `inv_xview`
as the acceptance test of every builder and fix step would have stopped the chain at build-v017 (D), at build-v016 (C),
at build-v013 (A, B) and at F13 (B ends).

## 8. Which system the job ran on (`outputs/review-v002/system/SYSTEM.md`)

- Day 1 ran on a detached `a3e091b` in the main checkout; the branch was cut from it at 15:17 (6 h stale) and merged
  main only after the build (`fd399e7`, 10-21 20:38). 104 main merges landed in between. The 10-20 takeover listed #380
  (`inv_xview`, `tools/qa/xview_dump.ms`), D152 and #363 (TASK_TO_MODEL) in `git log HEAD..origin/main`; none was merged.
- The engine built 0 faces of the final model (spec-v002 and a BuildError). All geometry, UV and export came from
  job code: 7 059 tracked lines in `scripts/` plus ~11 450 untracked helper lines in `outputs/`.
- Shared checks already on the branch were never run: kernel invariants `no_close_overlap`, `no_visible_back_faces`
  (6 418 inward reveal faces lived from build-v013 to 10-21), `tools/qa/check_clearance.py`, `tools/blender/fbx_readback.py`.
  The job wrote ~1 900 lines of its own QA instead.
- Not used although their trigger fired: `analyze-architectural-source` + `source-inspector` (a source-class count would
  have stopped the 90-min engine route), `validate-delivery`, `independent-checker` on every Lego build (run once, on
  export-v005, it flagged the gap), `pattern-librarian`. `inv_xview` is still missing from `docs/agents/CAPABILITIES.md`.
- User rules of 2026-10-21 not recorded as `D<n>`: 1 cm tolerance, glass "4 points", embed / move >= 6 mm, weld only
  coincident seams, F8 option A, xView as the overlap truth, Mesh + Weld 2 mm before export.
- Worked and worth keeping: the fast pivot to the measured Lego build (master "4+"); sources never touched, every rerun
  versioned, user files hashed; reproduce the chain before fixing the builder; parallel measurement agents; exported
  FBX read back in a clean scene; findings into the backlog the same day.

## 9. Questions for the user

1. Fins sunk 0.808 m below z 0: a rule for placement on relief (all towers, which depth) or this site only?
2. 9 body wall quads at 51.8-57.8 removed: what was wrong there (duplicate behind another surface?)
3. Coping, roof and band199 moved to the dark atlas area: is dark the source colour (our mapping error) or a design choice?

## 10. Follow-up issues (created 2026-10-21, `ready-for-agent`)

| Issue | What |
|---|---|
| #527 | Overlap gate: `inv_xview` CLI in local coordinates, the postcondition of every build step |
| #528 | xView runner: `.max`, full face lists, Mesh + Weld 2 mm mode folded into `tools/qa/xview_dump.ms` |
| #529 | Branch freshness: no production on a detached HEAD; merge main before the first production step |
| #530 | Engine join: weld or separate beyond the face tolerance; seam-aware simplification |
| #531 | Attached decor placement: derive from the host face, no shared levels, >= 10 mm per vertex, rigid fixes |
| #532 | Analysis: which TOW02 job code becomes engine modules (EG6) |
| #533 | Intake: source-class step; `independent-checker` after every shown build; poll timeouts |
| #534 | Backfill the user's TOW02 rules into `docs/decisions.md` |
| #535 | Fast xView-exact checks: seconds, incremental per part, interactive Blender overlay |
