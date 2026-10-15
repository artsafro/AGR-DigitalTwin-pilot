# Autoresearch: Butovskaya school NPM from live Revit (#118, lane 3 of 3: Claude + `autoresearch` skill)

Status: experiment report. `delivery_passed=false`. Visual acceptance is the user's (renders below).
Object `butovskaya-sosh1000` (`jobs/REGISTRY.md`), job folder `jobs/butovskaya-sosh1000/`, branch
`job/butovskaya-sosh1000-npm-autoresearch`.

> **Non-conforming exploration (review round 1, P1-1).** Step 0 requires element **meshes**; the add-in's read
> API returns only bounding boxes, so step 0 is **blocked** by the issue's own rule ("If the export is too slow or
> blocked: stop and report with numbers"). Every number below is measured against per-element boxes, not the
> Revit solids, and is **not** a result of the fixed program. `scripts/snapshot_revit.py` now fails closed on a
> bbox-only answer (exit 2, `blocked.json`, no snapshot files) and `scripts/evaluate.py` refuses a box snapshot
> unless run with `--exploratory-box-reference` (output `"conforming": false`). A conforming run needs an
> authorized mesh export of the envelope (the user's decision; the card is blocked on it). Diagnostics of the
> blocked step 0: 11 060 elements listed, geometry read at 63 elements/s, 0 call failures; the geometry answer
> carries bounding box, centroid, volume, surface area, solid and face counts and no tessellation, and no
> read-only command of add-in 0.8.40 exports meshes (step 0 notes below).

## Result

| | First build (setup) | Final (exp 15) |
|---|---|---|
| `silhouette_err_m2` (2 x + 2 y + top) | **334.066** | **17.584** (-94.7 %) |
| per view x / y / top, m2 | 35.770 / 96.607 / 69.313 | 2.707 / 3.245 / 5.680 |
| IoU x / y / top | 0.9719 / 0.9626 / 0.9902 | 0.9979 / 0.9987 / 0.9992 |
| non-manifold edges / vertices, open loops outside the allowed kinds, overlaps, n-gons | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 |
| open (boundary) edges, winding_bad_edges | 0, 0 | 0, 0 |
| triangles (<= 150 000) | 64 278 | 141 132 |
| levels, worst diff (<= 0.02 m) | 0.0 | 0.0 |
| height layers | 9 | 53 |

20 of the 25 iterations ran; the loop stopped at the 3 h time box (below, "Cost"). 4 kept, 16 discarded.

## Step 0: snapshot (live Revit, read only, once)

- `python C:/Users/artsafro/hermes_kanban/scripts/revit_exec.py --ping`: add-in 0.8.40, 94 commands, auth on.
  Document `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025`, workshared, not modified, active view `{3D - artsafro}`.
- Commands used: `get_document_info`, `list_levels`, `list_categories`, `list_wall_types`, `find_elements`,
  `get_element_info` (one wall, to read what it returns), `get_element_geometry` - all read-only.
  `scripts/snapshot_revit.py` refuses any other command before a request is sent (probe 1). No `--commit`, no sync,
  no save.
- **What the read API gives:** `get_element_geometry` returns bounding box, centroid, volume, surface area, solid
  and face counts - no tessellation, and no read-only command exports meshes. The snapshot therefore stores one
  axis-aligned box per element; that is the "mesh" the etalon is made of. The building is orthogonal in project
  coordinates (plan render), so wall and curtain boxes are close to the elements; roof and floor boxes are coarse
  (fill ratio below). This limits what "silhouette error" means: it is measured against element boxes, not against
  the Revit solids.
- Speed: 11 060 elements in 175.6 s = 63 elements/s, 0 failed.

| Category | Elements | With a box in the zone | Fill ratio volume / box (median, p10) | Boxes with fill >= 0.9 |
|---|---|---|---|---|
| OST_Walls | 4 447 | 4 446 | 0.85, 0.02 | 47 % |
| OST_CurtainWallPanels | 1 523 | 1 371 | 1.00, 0.04 | 61 % |
| OST_CurtainWallMullions | 4 210 | 4 202 | 1.00, 0.17 | 55 % |
| OST_Roofs | 22 | 22 | 0.47, 0.19 | 9 % |
| OST_Floors | 53 | 50 | 0.58, 0.08 | 16 % |
| OST_Windows | 346 | 336 | 0.01, 0.01 | 0 % (family voids) |
| OST_Doors | 459 | 459 | 0.04, 0.02 | 0 % |
| **total** | **11 060** | **10 886** | | |

170 elements have no box; 4 boxes reach outside the building zone x -67 ... 60, y -30.5 ... 29.5 m and are left
out (wall 3588431, floors 2466029, 3588401, 3588412 - site pieces up to 204 m away). Levels: 8, -3.4 ... 18.6 m
(Этаж -1, техподполье, 01 ... 06). The wall parameter `Функция` is not reliable here (facade finish types read
"internal"), so the envelope is every element of the categories, not a function filter; interior boxes lie inside
and do not change a silhouette.

Snapshot `C:/x/butovskaya-snapshot/` (local, git-ignored, nothing in `data/`), sha256:

| File | sha256 |
|---|---|
| `elements.json` | `9d80655da52c87d28b5069ab4e6ced74963b1254c9c0cd7653b08908efb7979d` |
| `levels.json` | `4e984c3a97823898ad5f03a412e3d6855755cb07348d5ab03eaaa87579d3cc49` |
| `snapshot_dump.json` | `d0a364f8537969a8897e0634441db59880d9848a5ca6265a3818296a8ede392b` |
| `etalon_silhouettes_9d80655da52c87d2.json` (cache) | `d55b01a8657ee671d724fa6c0fb18f21dabe72030160f417b0ec0886c0518861` |

## Program (fixed after step 0)

- Model: `jobs/butovskaya-sosh1000/scripts/build_npm.py`, the only file the loop edits; it reads the snapshot only.
- Metric `silhouette_err_m2` (`scripts/evaluate.py`): `check_silhouettes`' rule with its own
  `twinqa.geometry.measure.silhouette`, read as an area: area(model XOR snapshot) per view. The adapter: the checker
  returns IoU; facades are mirror pairs in an orthographic projection (`measure.VIEWS` x, y, top), so the five views
  sum as `2 err_x + 2 err_y + err_top`.
- Guard, the repo's checkers unchanged: `check_mesh` on the whole model and on every mesh (bench-b01-box tolerances,
  weld 3 mm, `slabs=None`); `winding_bad_edges` per mesh; `check_budget` 150 000; `check_levels` 0.02 m against
  the snapshot levels; non-DCC suite at the start and the end (the loop edits only `build_npm.py`, no test imports
  it). Keep = strictly lower metric with the guard passing; deterministic (probe 3).
- Method: skill `autoresearch` classic mode, `Metric: silhouette_err_m2 (lower)`, `Verify: evaluate.py`, guard as
  above, `Iterations: 25`. From exp 4 on, experiments ran as parallel batches from the same kept base (one
  evaluation took 13-58 min); the best improving one of a batch was kept, improving siblings are listed as
  discarded with that note (greedy, one change per experiment).

## Model

One closed mesh `SM_butovskaya_sosh1000_body` (pattern `primitive-first`: one primitive per part - here a stack
of extruded plan regions). The height range is cut at thresholds (the 8 levels + the box tops / bottoms carrying
the most plan area on a 0.05 m z grid); the plan region of a layer is the union of the box rectangles covering at
least half of it, on a 0.05 m integer grid; edge-only contacts between layers and pinch points are filled by one
grid unit so the solid is manifold. Each wall strip is split only at the points of its own two heights, each
horizontal face is a CDT of its region with exactly those points, so faces meet edge to edge (0 open edges).
Up faces roof id 21, walls and soffits facade id 1, flush opening planes id 11 (window) / 12 (door) cut into a
wall strip where an opening box fits one strip (final: 207 window and 556 door plane pieces; a tall opening
crossing layers is cut into pieces or left out). `LEVEL_<name>` helpers at the 8 snapshot levels.

## Experiments

| # | Change | silhouette_err_m2 (x / y / top) | IoU x / y / top | Guard: nm edges / nm verts / open other / overlaps / winding | Triangles | Status |
|---|---|---|---|---|---|---|
| 0 | first build (setup): layers at the 8 levels, COVER_F 0.5, grid 0.05 m, flush opening planes | **334.066** (35.77 / 96.607 / 69.313) | 0.9719 / 0.9626 / 0.9902 | 0 / 0 / 0 / 0 / 0 | 64278 | baseline |
| 1 | thresholds: levels + 12 box tops/bottoms with the most plan area (z grid 0.1 m) | **220.873** (34.204 / 53.663 / 45.14) | 0.9732 / 0.9792 / 0.9936 | 0 / 0 / 0 / 0 / 0 | 75686 | keep |
| 2 | COVER_F 0.5 -> 0.25 (thinner boxes join a layer) | **243.587** (36.055 / 63.169 / 45.14) | 0.9718 / 0.9758 / 0.9936 | 0 / 0 / 0 / 0 / 0 | 75360 | discard |
| 3 | K_EXTRA 12 -> 24 box-top thresholds | **75.091** (18.569 / 16.136 / 5.68) | 0.9854 / 0.9938 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 125104 | keep |
| 4 | COVER_F 0.5 -> 0.75 | **305.544** (44.481 / 82.796 / 50.989) | 0.9651 / 0.968 / 0.9928 | 0 / 0 / 0 / 0 / 0 | 76388 | discard (tried in parallel on the exp-1 base, best 220.873) |
| 5 | BODY without OST_Doors | **226.788** (34.206 / 53.693 / 50.989) | 0.9731 / 0.9792 / 0.9928 | 0 / 0 / 0 / 0 / 0 | 69878 | discard (exp-1 base) |
| 6 | MIN_PART_M2 0 -> 1.0 (drop region parts under 1 m2) | **227.418** (37.447 / 53.692 / 45.14) | 0.9706 / 0.9792 / 0.9936 | 0 / 0 / 0 / 0 / 0 | 71950 | discard (exp-1 base) |
| 7 | K_EXTRA 24 -> 28 | **64.669** (13.369 / 16.125 / 5.68) | 0.9894 / 0.9938 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 140328 | discard (improved, beaten by sibling exp 14) |
| 8 | Z_Q 0.1 -> 0.05 (finer threshold heights) | **65.269** (17.172 / 12.622 / 5.68) | 0.9865 / 0.9951 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 125006 | discard (improved, beaten by sibling exp 14) |
| 9 | threshold weights from box tops only | **123.803** (19.287 / 21.537 / 42.155) | 0.9848 / 0.9917 / 0.9941 | 0 / 0 / 0 / 0 / 0 | 114908 | discard |
| 10 | threshold weight = box plan width+depth instead of area | **107.368** (13.016 / 36.335 / 8.665) | 0.9897 / 0.9859 / 0.9988 | 0 / 0 / 0 / 0 / 0, budget **fail** | 157746 | discard |
| 11 | COVER_F 0.5 -> 0.6 | **93.865** (21.16 / 22.805 / 5.935) | 0.9833 / 0.9912 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 122610 | discard |
| 12 | COVER_F 0.5 -> 0.4 | **75.091** (18.569 / 16.136 / 5.68) | 0.9854 / 0.9938 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 125916 | discard (equal, not strictly better) |
| 13 | walls split only at the points of their own two heights (zipper strips) + K_EXTRA 24 -> 40 | **51.98** (7.97 / 15.18 / 5.68) | 0.9937 / 0.9941 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 134336 | discard (improved, beaten by sibling exp 14) |
| 14 | zipper walls + K_EXTRA 24 -> 44 | **31.964** (4.19 / 8.952 / 5.68) | 0.9967 / 0.9965 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 138532 | **keep** |
| 15 | Z_Q 0.1 -> 0.05 | **17.584** (2.707 / 3.245 / 5.68) | 0.9979 / 0.9987 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 141132 | **keep (final)** |
| 16 | K_EXTRA 44 -> 48 | **26.411** (3.952 / 6.414 / 5.68) | 0.9969 / 0.9975 / 0.9992 | 0 / 0 / 0 / 0 / 0, budget **fail** | 150836 | discard |
| 17 | SNAP_M 0.05 -> 0.025 (finer plan grid) | **27.169** (3.59 / 8.421 / 3.147) | 0.9971 / 0.9967 / 0.9996 | 0 / 0 / 0 / 0 / 0 | 146808 | discard (improved, beaten by sibling exp 15) |
| 18 | extra thresholds at least 0.3 m apart | **59.868** (8.552 / 17.049 / 8.665) | 0.9932 / 0.9934 / 0.9988 | 0 / 0 / 0 / 0 / 0, budget **fail** | 193578 | discard |
| 19 | COVER_F 0.5 -> 0.55 | **50.709** (6.774 / 15.613 / 5.935) | 0.9946 / 0.994 / 0.9992 | 0 / 0 / 0 / 0 / 0 | 138318 | discard |
| 20 | threshold weights without floor slabs | **61.589** (10.014 / 16.448 / 8.665) | 0.992 / 0.9936 / 0.9988 | 0 / 0 / 0 / 0 / 0 | 145086 | discard |

Raw records: `jobs/butovskaya-sosh1000/autoresearch/results.json`; the table is `scripts/report_experiments.py`.
Every row passed `levels` (0.0 m) and had 0 open edges; "budget fail" = triangles over 150 000.

What moved the metric: thresholds (where the layers are cut) - 334 -> 221 -> 75; then freeing triangle budget by
splitting walls locally (125 k -> 92 k triangles for the same geometry) and spending it on more layers -> 32; finer
threshold heights -> 17.6. Everything about region rules (cover share, part filter, door boxes, weights) made it
worse. Left: 5 cm bands (parapet caps at 18.9-18.95 m), grid rounding slivers along the outline, a door box at
x 58.8 m that the model fills.

## Renders (final model and snapshot boxes, orthographic, 5 px/m)

| View | Model (exp 15) | Snapshot boxes |
|---|---|---|
| South | ![](autoresearch-butovskaya-npm/model-south.png) | ![](autoresearch-butovskaya-npm/snapshot-south.png) |
| North | ![](autoresearch-butovskaya-npm/model-north.png) | ![](autoresearch-butovskaya-npm/snapshot-north.png) |
| East | ![](autoresearch-butovskaya-npm/model-east.png) | ![](autoresearch-butovskaya-npm/snapshot-east.png) |
| West | ![](autoresearch-butovskaya-npm/model-west.png) | ![](autoresearch-butovskaya-npm/snapshot-west.png) |
| Top | ![](autoresearch-butovskaya-npm/model-top.png) | ![](autoresearch-butovskaya-npm/snapshot-top.png) |

Flat-shaded painter's renders (`scripts/render_views.py`): facade beige, roof grey, window planes blue, door planes
brown. They show the silhouette and the opening planes, not materials.

## Checks beyond the guard

- Probes (`scripts/probe_invariants.py`): read-only snapshot 57/57 write / unknown commands refused before a request;
  the loop never calls Revit (static 10/10, runtime no Revit / HTTP module); deterministic build 1/1 (two builds
  byte-identical, sha256 `2815eb65179a...` = the evaluated exp-15 dump); keep rule and `delivery_passed=false`
  21/21 records; guard numbers of every kept build 5/5.
- Non-DCC suite: at the start exit 0 (2 321 passed, 9 skipped by the progress dots); at the end 2 321 passed, 9 skipped,
  12 deselected, exit 0 (286.8 s).
- `check_orientation` (outward normals, report-only, not part of the fixed guard) on the final model: pass, 0 winding errors, 0 outside back faces, 25 632 faces judged by 5 833 127 rays (976.7 s).

## Cost

- Wall time: 16:30-19:25 (about 3 h); Revit snapshot 3 min; one experiment 3 min at 64-76 k triangles, 13 min at
  125 k alone, 30-58 min in parallel batches of 6-8 (the guard's `check_mesh` overlap test is quadratic in the
  triangle count; two other autoresearch lanes ran on the same machine). That is why 20 of 25 iterations ran.
- Tokens (Hermes session of this card, at the time of writing): input 242 (uncached), output 105 301, cache read 22 481 846, cache write 710 252; 120 API calls, 136 tool calls; estimated cost 10.15 USD (Hermes `state.db`, session of card t_20f3c6f7; the last steps of the hand-off are not in it).

## Verdict on the tool

- The `autoresearch` skill's classic loop fits a geometry job when the metric and the guard are scripts of the repo:
  modify -> build -> evaluate -> keep/discard was mechanical, every number is from the checkers, nothing is
  self-reported. The fixed program held: the evaluator, checkers, data and the Revit model were not touched by the
  loop (probes below).
- It is the evaluation cost, not the agent, that bounds the loop here: 20 iterations in 3 h, and parallel batches
  weaken the greedy rule (improving siblings of a better one are discarded without being combined).
- The metric is blind to what the NPM is for beyond the silhouette: opening planes, triangle economy and visual
  quality never entered keep/discard. The loop's best moves (more layers) raised triangles from 64 k to 141 k
  and cut tall openings into pieces per layer. A next program should add the opening-plane coverage
  (`check_opening_planes` needs a spec) or a triangle term to the metric.
- The step-0 limit matters most: the read-only Revit API gives boxes, so the target is "element boxes", not the
  Revit solids; a mesh export (IFC / FBX by the user, or a tessellating read command in the add-in) would make the
  same loop measure real geometry.

## Open items (for the user)

1. Visual acceptance of the final model (renders above; dump `C:/x/butovskaya-npm/run15/model_dump.json`, local).
2. Snapshot = element boxes (no tessellated geometry through the read API): accept as the reference, or export
   IFC / FBX for a mesh-based rerun.
3. Opening planes are flush (pattern `opening-plane` asks a 0.4 m recess in `npm_min`) and split per layer.
4. Horizontal faces are CDT triangles (the OBJ03 decision against triangulated horizontal faces was per object).
5. No FBX, materials table or UV; geometry only.
