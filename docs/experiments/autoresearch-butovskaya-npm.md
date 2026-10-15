# Autoresearch: Butovskaya school NPM from live Revit (#118, lane 3 of 3: Claude + `autoresearch` skill)

Status: experiment report. `delivery_passed=false`. Visual acceptance is the user's (renders below).
Object `butovskaya-sosh1000` (`jobs/REGISTRY.md`), job folder `jobs/butovskaya-sosh1000/`, branch
`job/butovskaya-sosh1000-npm-autoresearch`.

Round 3 (this report's main part) is the **conforming run**: step 0 is the TwinPack mesh export the user authorized
on 2026-10-15 (option a, the agent exports through the add-in), and every number of the loop is measured against
the Revit element meshes. The first attempt's box run is kept at the end as non-conforming exploration
(review round 1, P1-1).

## Result

| | First build (setup) | Final (exp 16) |
|---|---|---|
| `silhouette_err_m2` (2 x + 2 y + top) | **1029.978** | **170.512** (-83.4 %) |
| per view x / y / top, m2 | 11.553 / 14.967 / 976.938 | 25.891 / 37.517 / 43.697 |
| IoU x / y / top | 0.9905 / 0.9941 / 0.8618 | 0.9787 / 0.9853 / 0.9929 |
| open edges / non-manifold edges / non-manifold vertices / open loops outside the allowed kinds / overlaps / n-gons | 0 / 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 / 0 |
| winding_bad_edges | 0 | 0 |
| triangles (<= 150 000) | 137 672 | 124 976 |
| levels, worst diff (<= 0.02 m) | 0.0 | 0.0 |
| guard (all of the above, `check_mesh` per mesh too) | pass | pass |

21 of the 25 iterations ran in the round-3 time box; 3 kept, 16 discarded, 2 crashed
(build error or killed after a time-out). The setup build reads the TwinPack snapshot's element boxes (the box run's
best build, unchanged); its top view fills the 45-degree courtyards and notches of the plan (top IoU 0.86), which is
what the mesh reference shows and the box reference hid.

## Step 0: snapshot (live Revit, read only, once) - mesh route

- `py -3 C:/Users/artsafro/hermes_kanban/scripts/revit_exec.py --ping`: add-in 0.8.40, 94 commands (92 built-in +
  2 pack), auth on. `--cmd twin_floor_manifest` (dry-run route): `twin-manifest/1` for
  `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025`, 8 bands, Revit internal coordinates = project base point = survey point.
- Export: `node tools/source/measure_spec_revit_twin.mjs C:/x/butovskaya/twin-v001` (TwinPack `twin_floor_manifest`,
  `twin_export_floor` per band with every wall function, `get_document_info`, `list_levels`, `list_elements`
  OST_Roofs, `get_element_info` per roof), run once under the Revit lock of `revit_exec.py` (card t_20f3c6f7).
  The script calls the pack commands through `revitClient.callRevit` the way CAPABILITIES.md describes;
  `twin_export_floor` writes files only into the new folder. **Document modified: false before, false after**
  (`twin-data.json`). No `--commit`, no sync, no save. **81.3 s** for the 8 bands.
- `jobs/butovskaya-sosh1000/scripts/snapshot_twin.py` turns the export into the loop's snapshot
  `C:/x/butovskaya-snapshot-twin/` (local, git-ignored, nothing in `data/`): one mesh per band piece of an element
  (`band-<n>/<kind>_<revitId>`, the band's clipped geometry), the 8 levels, hashes; 6.1 s. It fails closed (exit 2,
  `blocked.json`, no snapshot files) on a missing export, a modified document, no band or level, a missing or
  truncated band file, a non-triangle or out-of-range face, an empty object, clip fallbacks, an export with no triangle in any band (`no_geometry`, review round 2),
  and refuses a second run into a published snapshot (tests below). `scripts/evaluate.py` takes it unchanged
  (`reference: mesh`, hash-checked on every run; a reference with 0 pieces / 0 triangles, or with counts the
  hashed dump does not hold, is rejected).

| Category | Elements | Band pieces | Triangles | In the box snapshot (first attempt) |
|---|---|---|---|---|
| OST_Walls | 4 269 | 5 110 | 163 684 | 4 447 (178 not in the export: 151 curtain-wall hosts (`Витраж`), whose geometry is their panels and mullions; 11 finish layers `ADSK_Отделка_по блоку 25`; 8 interior aerated-concrete walls; 8 other finish or masonry walls) |
| OST_CurtainWallPanels | 1 371 | 1 579 | 19 580 | 1 523 (the 152 not exported had no geometry box either) |
| OST_CurtainWallMullions | 4 202 | 4 502 | 67 744 | 4 210 (8 without geometry) |
| OST_Roofs | 22 | 22 | 971 | 22 |
| OST_Floors | 53 | 59 | 3 808 | 53 |
| OST_Windows | 336 | 347 | 879 136 | 346 (10 without geometry) |
| OST_Doors | 447 | 488 | 626 352 | 459 (12 empty door openings `Проем` without geometry) |
| OST_Cornices (wall sweeps, `Выступающие профили`) | 2 869 | 8 987 | 150 708 | not read in the first attempt |
| **total** | **13 569** | **21 094** | **1 911 983** | 11 060 |

Coverage: every envelope category of the program is in the export as real tessellated geometry, including curved
walls, curtain panels and mullions, roofs and the cornice profiles; nothing is a box. Gaps: curtain-wall host
walls are represented by their panels and mullions only; 12 door openings without geometry; the export is cut at
the bands, so pieces of one element meet at the band boundaries and the bands leave **1 mm gaps** (-2.101 / -2.1,
-0.011 / -0.01, 4.399 / 4.4, ...); in the facade views these are horizontal slits of the reference (about 0.06 m2
per gap and view), which any continuous model pays for. Three floor pieces lie outside the building zone of
`evaluate.py` (x -67 ... 60, y -30.5 ... 29.5 m) and are left out of the etalon: `floor_2466029`, `floor_3588401`,
`floor_3588412` (site pieces up to 204 m away), as in the first attempt.

Hashes (sha256):

| File | sha256 |
|---|---|
| `elements.json` (snapshot) | `6337cc4a5b911f25f1b87280061947e6e9cf40469f7f6c45a814c18692114ee9` |
| `levels.json` (snapshot) | `f923e4c71f14a17de7902bdf3e5f130cdef168b394fde9e3a41f93ccba02ffd5` |
| `snapshot_dump.json` (snapshot) | `4d71d19ce79b180d6074ee6f0d66df9010a51a0ef9b78c9704f7f272f4b1a72a` |
| `twin-data.json` (export) | `b8d4bf61995040d6f3c6bef3af7d96b292c83f2e629e3370d37eecf4f822f37e` |
| `band-1/reference.obj` (export) | `5c28d39eb2a074b95b3c6d739689a0f26c451e63dad8fce659ab5b59c5c425cf` |
| `band-1/floor.json` (export) | `a685318a8fa5769d5cd003a757eb6e8d3a88e8fd87bb737971ec67357272152b` |
| `band-2/reference.obj` (export) | `4706aa43ea6b8c68814c87fe0a66bfc390c4f9bc3619ce06767dfdda60c2ec5f` |
| `band-2/floor.json` (export) | `3c2d5f34892e495d94ba7c2200f925b8a7f603a1a1805cd4f7eda70b4d9aef30` |
| `band-3/reference.obj` (export) | `ba276ebca0efe2c828216044208c8ea1038a18942a266b1f1536ce6cd17720f1` |
| `band-3/floor.json` (export) | `e85b83abfa03ce8849bacf2991b02d41e76736996d702b1d712172b6af6646fe` |
| `band-4/reference.obj` (export) | `5b9540b0ce0144012a45bad3407923d6071e3f818cbf1336ac7c6e3bf6796d17` |
| `band-4/floor.json` (export) | `dea56a5c2be5f3aac88dac889a0bb578f76967ff07cb77da34eff51c157c1341` |
| `band-5/reference.obj` (export) | `6d686f1735b6e19af904b6a05fec4b497ca2450b8ccdb8ce095220813e6bd975` |
| `band-5/floor.json` (export) | `78973f5a1e8848576b80d9d10055e4c3352cbb67f482afd5c9cbd7f0847fa7e7` |
| `band-6/reference.obj` (export) | `ae1dedb96ef4268142ad066517df2275946f6590e2a2aa7292536db42640b623` |
| `band-6/floor.json` (export) | `1b56d9f3e6fd5ba92d3450e3f31a00a7535569f93235522c906864cc83eab299` |
| `band-7/reference.obj` (export) | `53cddaf9e2f35ba85611e0e4d74377ddf1587c0f4f124cdf0aeb3d0913aa5184` |
| `band-7/floor.json` (export) | `0d29f35e9ede4b028db86245a5b3dd1f416c70d0cb9f17b24a17fe942179cc17` |
| `band-8/reference.obj` (export) | `e1c6c8c9f0c77f48f194fe8de7e0b26bbd3609c96ea6f39747ddf936d6a64b39` |
| `band-8/floor.json` (export) | `f38fca743e03cf81b943a6c7c56fcaa2e6dc65a961a77f5057c2bbe3a75c6f92` |
| `etalon_silhouettes_mesh_4d71d19ce79b180d.json` (etalon silhouette cache) | `91172882bdba72eb30a43c264129021d25c7c0ae5bdcba7a6af2e35baf2d36d6` |

## Program (fixed after step 0)

- Model: `jobs/butovskaya-sosh1000/scripts/build_npm.py`, the only file the loop edits; it reads the snapshot only.
- Metric `silhouette_err_m2` (`scripts/evaluate.py`, unchanged since review round 1 except that the default snapshot
  is now the mesh snapshot): `check_silhouettes`' rule with its own `twinqa.geometry.measure.silhouette`, read as
  an area: area(model XOR snapshot meshes) per view; facades are mirror pairs (`measure.VIEWS` x, y, top), so the
  five views sum as `2 err_x + 2 err_y + err_top`.
- Guard, the repo's checkers unchanged: `check_mesh` on the whole model and on every mesh (bench-b01-box tolerances,
  weld 3 mm); `winding_bad_edges` per mesh; `check_budget` 150 000; `check_levels` 0.02 m against the snapshot
  levels; non-DCC suite at the start and the end. `delivery_passed=false` on every record.
- Keep = strictly lower metric **and** the guard passing (`scripts/loop_step.py`, tests below). The guard takes
  4-15 min on a 120-150 k triangle model (the machine ran the other two lanes), so it runs only when the metric is
  strictly better: a discard by metric needs no guard, and the decision is the same as running both every time.
  For candidates whose metric was better but whose welded edge count already showed open or non-manifold edges
  (the same 3 mm weld as `check_mesh`; on exp 2 it reproduced `check_mesh` exactly: 7 241 open, 580
  non-manifold), `check_mesh` was not run and the row says so; they could not be kept either way.
- Method: skill `autoresearch` classic mode, `Metric: silhouette_err_m2 (lower)`, `Verify: loop_step.py`
  (`evaluate.metric` + `evaluate.guard`), `Iterations: 25`. Candidates were built speculatively while the guard of
  the previous one ran; each row was decided against the best kept row at that moment.

## Model (final)

One mesh `SM_butovskaya_sosh1000_body` made of separate closed prisms (pattern `primitive-first`: one primitive per
part). The height range is cut at 54 thresholds (the 8 levels + the 44 piece tops / bottoms with the most plan area,
0.05 m z grid). The plan region of a layer is the union of the plan footprints of the snapshot pieces covering at
least half of it (the union of each piece's projected triangles; the convex hull for windows, doors, curtain panels
and mullions; wall sweeps are not body), plus every floor / roof piece overlapping the layer by 5 cm (thin slabs
outside the walls: the entrance canopies), simplified by 0.15 m, holes filled (rooms), on a 0.05 m grid, pinch points
removed. Neighbouring layers differing by less than 2 m2 are one prism (53 layers -> 44 prisms). Each prism is offset
5 mm inward and stands 3.1 mm above the one below, past the 3 mm weld, so no two shells share an edge. Up caps
roof id 21, walls and down caps facade id 1, flush opening planes id 11 (window) / 12 (door) cut into a wall quad
where an opening box fits one quad (710 window and 431 door plane pieces). `LEVEL_<name>` helpers at the 8
snapshot levels. Parameters: the top block of `scripts/build_npm.py`.

## Experiments

| # | Change | silhouette_err_m2 (x / y / top) | Guard: open / nm edges / nm verts / open other / overlaps / winding | Triangles | Status |
|---|---|---|---|---|---|
| 0 | first build (setup): build_npm.py of the box run's exp 15 (layers at levels + 44 box tops, grid 0.05 m, flush opening planes) reading the TwinPack snapshot's piece boxes | **1029.978** (11.553 / 14.967 / 976.938) | 0 / 0 / 0 / 0 / 0 / 0 | 137672 | baseline |
| 1 | plan regions from the projected piece meshes (SOURCE mesh: union of triangle footprints per layer, holes filled), no simplification | **86.56** (10.103 / 5.594 / 55.165) |  /  /  /  /  /  **fail** (check_budget fails (199 910 > 150 000); the topology checks were not run) | 199910 | discard |
| 2 | exp 1 + region simplify 0.1 m (SIMPLIFY_M) | **85.725** (10.089 / 5.494 / 54.558) | 7241 / 580 / 606 / 1124 / 0 / 4 **fail** | 118900 | discard |
| 3 | exp 2 + K_EXTRA 60 (more box-top thresholds) | **85.696** (10.089 / 5.494 / 54.53) | 8921 / 584 / 780 / 1278 / 0 / 7 **fail** | 136326 | discard |
| 4 | exp 2 + snap-rounding noding of neighbouring layer outlines (crossings and near vertices inserted into both rings), K_EXTRA back to 44 | crash: GEOSException TopologyException: side location conflict (the inserted points made self-intersecting rings) | | | crash |
| 5 | exp 2 + faces at each threshold from the noded arrangement of both outlines (float crossings shared by walls and faces) instead of a snapped difference | **85.67** (10.089 / 5.494 / 54.504) | 0 / 364 /  /  /  /  **fail** (edge count of the welded mesh (the same weld 3 mm as check_mesh; on exp 2 it reproduced check_mesh exactly: 7241 boundary, 580 non-manifold): 0 open, 364 non-manifold edges (pinches at vertex-on-edge touches, layers touching edge to edge) -> guard fails; check_mesh not run) | 125430 | discard |
| 6 | exp 5 + pinch test on the noded outline (vertex on another edge) and a 1.5-unit uncontact strip | **85.688** (10.094 / 5.497 / 54.506) | 0 / 354 /  /  /  /  **fail** (welded edge count (weld 3 mm): 0 open, 354 non-manifold (layers whose outlines run 0.8 mm apart: the union of each layer simplified separately) -> guard fails; check_mesh not run) | 128042 | discard |
| 7 | exp 6 with each piece footprint simplified (0.1 m) instead of each layer union, so layers holding the same pieces share one outline | crash: timeout: the layer regions were not done after 5.5 min (unsimplified unions, 2x the whole previous build); killed | | | crash |
| 8 | exp 6 + outlines of neighbouring layers snapped to each other (GEOS snap, 1.5 units, both ways) | **None** ( /  / ) | 0 / 4354 /  /  /  /  **fail** (318 234 triangles (> 150 000) and 4 354 non-manifold welded edges (the snap undid the uncontact strips: layers touch edge to edge again); build 9 min; metric not computed) | 318234 | discard |
| 9 | exp 6 regions, but every layer is its own closed prism (walls on its rings, caps top and bottom), 4 mm gap over the prism below (past the 3 mm weld); no snap | **150.473** (20.452 / 27.532 / 54.506) | 0 / 119 /  /  /  /  **fail** (151 576 triangles (> 150 000) and 119 non-manifold welded edges (pinch points the unpinch squares do not remove: a square corner lands on a diagonal edge); check_mesh not run) | 151576 | discard |
| 10 | exp 9 + unpinch falls back to closing the region by 1-2 units; no uncontact strips for prisms | **161.407** (20.627 / 27.283 / 65.587) | 0 / 40 /  /  /  /  **fail** (153 956 triangles (> 150 000), 40 non-manifold welded edges left; check_mesh not run) | 153956 | discard |
| 11 | exp 10 + every prism outline offset 5 mm inward (touching parts come apart) + K_EXTRA 44 -> 30 (fewer layers, fewer gaps and triangles) | **240.999** (40.143 / 47.58 / 65.552) | 0 / 9 /  /  /  /  **fail** (9 non-manifold welded edges left (pinches the offset itself creates); check_mesh not run) | 110964 | discard |
| 12 | exp 11 + octagon cut (r 0.3 unit) at any pinch left after the offset; K_EXTRA back to 44; region simplify 0.1 -> 0.15 m | **204.468** (27.98 / 41.474 / 65.56) | 0 / 1 / 0 / 0 / 0 / 0 **fail** | 124136 | discard |
| 13 | exp 12 with region simplify back to 0.1 m | **233.194** (35.942 / 47.862 / 65.587) | 0 / 13 /  /  /  /  **fail** (13 non-manifold welded edges (weld 3 mm edge count); check_mesh not run) | 132860 | discard |
| 14 | exp 12 + floor / roof pieces join every layer they overlap by 5 cm (thin slabs outside the walls: entrance canopies) | **184.666** (28.127 / 42.357 / 43.697) | 0 / 0 / 0 / 0 / 0 / 0 | 126744 | keep |
| 15 | PRISM_GAP_M 4 mm -> 3.1 mm (just past the 3 mm weld: thinner slits in the facades) | **172.154** (26.149 / 38.079 / 43.697) | 0 / 0 / 0 / 0 / 0 / 0 | 126744 | keep |
| 16 | neighbouring layers differing by < 2 m2 merged into one prism (their union): fewer gaps | **170.512** (25.891 / 37.517 / 43.697) | 0 / 0 / 0 / 0 / 0 / 0 | 124976 | keep |
| 17 | COVER_F 0.5 -> 0.3 (a piece joins a layer when it covers 30 % of its height) | **169.762** (25.963 / 37.415 / 43.005) | 0 / 3 /  /  /  /  **fail** (3 non-manifold welded edges (weld 3 mm edge count); check_mesh not run) | 114836 | discard |
| 18 | MERGE_M2 2 -> 10 m2 (more near-equal layers merged, 44 -> 36 prisms) | **163.54** (24.923 / 34.794 / 44.106) | 0 / 3 / 0 / 0 / 0 / 0 **fail** | 114516 | discard |
| 19 | exp 18 with MERGE_M2 10 -> 40 m2 (34 prisms) | **167.583** (25.77 / 34.165 / 47.714) | 0 / 3 / 0 / 0 / 0 / 0 **fail** (guard run on its own (three candidates in parallel, same evaluate.guard)) | 111040 | discard |
| 20 | exp 18 with K_EXTRA 44 -> 56 (more thresholds now that near-equal layers merge) | **164.755** (25.079 / 35.18 / 44.237) | 0 / 6 / 0 / 0 / 0 / 0 **fail** (guard run on its own (three candidates in parallel, same evaluate.guard)) | 119216 | discard |
| 21 | exp 18 with the prism offset 5 mm -> 3.5 mm (PRISM_SHRINK_U 0.07) | **161.567** (23.508 / 35.223 / 44.106) | 0 / 3 / 0 / 0 / 0 / 0 **fail** (guard run on its own (three candidates in parallel, same evaluate.guard)) | 111772 | discard |

Raw records: `jobs/butovskaya-sosh1000/autoresearch/results-twin.json`; the table is
`scripts/report_experiments.py`. Every guarded row passed `levels` (0.0 m).

What happened. The mesh reference changed the picture at once: the box run's best build scores 1029.978 against
the meshes (top 976.9 m2: element boxes of the 45-degree wings fill the courtyards and notches of the plan). Plan
regions from the projected piece meshes reach about 86 m2 in one step (exps 1-2), but the stack builder that made
the box run's single closed mesh assumes axis-parallel outlines: with diagonal and curved outlines the crossings of
neighbouring layers fall off the grid, and the snapped faces leave 7 241 open and 580 non-manifold edges (exp 2).
Exps 4-8 tried to keep one closed stack (snap-rounding, a noded arrangement of both outlines, a pinch test on the
noded outline, per-piece simplification, snapping layers together): the arrangement closed every open edge (exp 5)
but 350-4 400 non-manifold edges stayed where layers touch edge to edge or run 0.8 mm apart. Exps 9-14 gave that up
for separate closed prisms per layer run with a gap past the weld; the first guard pass came at exp 14 (184.666),
after the floor / roof pieces outside the walls joined the layers. The gap costs silhouette area (slits in the
facades), so exps 15-16 thinned it (3.1 mm) and merged near-equal layers (170.512). Merging more (exps 18-21, best
metric 161.567) brought back 3-6 non-manifold edges and failed the guard. COVER_F 0.3 (exp 17) failed it too.

Left in the final model (per view x / y / top): the slits of 43 prism gaps in the facades (about 0.2 m2 per gap in
x, 0.4 in y); the basement band (-3.7 ... -2.1 m), where the model ends higher than the reference over long stretches
(8 m2 in x, 15 m2 in y); parapet caps at 19.2-19.4 m; one floor slab outside the plan at x -34.6 ... -27.8 m
(23 m2 top); wall sweeps (cornices) are in the reference but not in the body.

## Renders (final model and mesh snapshot, orthographic, 5 px/m)

| View | Model (exp 16) | Snapshot meshes |
|---|---|---|
| South | ![](autoresearch-butovskaya-npm/model-south.png) | ![](autoresearch-butovskaya-npm/snapshot-south.png) |
| North | ![](autoresearch-butovskaya-npm/model-north.png) | ![](autoresearch-butovskaya-npm/snapshot-north.png) |
| East | ![](autoresearch-butovskaya-npm/model-east.png) | ![](autoresearch-butovskaya-npm/snapshot-east.png) |
| West | ![](autoresearch-butovskaya-npm/model-west.png) | ![](autoresearch-butovskaya-npm/snapshot-west.png) |
| Top | ![](autoresearch-butovskaya-npm/model-top.png) | ![](autoresearch-butovskaya-npm/snapshot-top.png) |

Flat-shaded painter's renders (`scripts/render_views.py`): facade beige, roof grey, window planes blue, door planes
brown. They show the silhouette and the opening planes, not materials. The snapshot renders are the reference
meshes themselves (round 1 showed boxes here).

## Checks beyond the guard

- Probes (`scripts/probe_invariants.py`, round 3): read-only snapshot route 57/57 write / unknown commands refused before a request; the loop never
  calls Revit (static 15/15 over build_npm, evaluate, loop_step; runtime no Revit / HTTP module); deterministic
  build 1/1 (two fresh builds byte-identical, sha256 `4b7ef69d8e57...` = the evaluated exp-16 dump); keep rule and
  `delivery_passed=false` 20/20 records (crash rows have no metric); guard numbers of every kept build 4/4.
- Snapshot procedure: `tests/test_butovskaya_twin_snapshot.py` 24 tests (Acceptance table in the PR), RED at
  923671c (collection error: no `snapshot_twin`), GREEN from cdd8c7e; the keep rule of `loop_step.py`
  (`test_loop_keep_rule`). Round-1 tests `tests/test_butovskaya_sosh1000.py` 24 still pass.
- Non-DCC suite (`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider`): 2 369 passed,
  9 skipped, 12 deselected, exit 0 (332 s).
- The welded edge count used to pre-screen candidates (weld 3 mm, grid cells) missed the 3 non-manifold edges of
  exp 18 that `check_mesh` (distance weld) found; it was never used to keep anything, only to skip `check_mesh` for
  candidates it already failed.

## Cost

- Wall time of round 3: 21:17-00:30 (about 3 h 10 min, the card's runtime cap 4 h). TwinPack export 81 s, snapshot 6 s,
  etalon silhouettes of 1.9 M triangles about 5 min once (cached). One experiment: build 1.5-4 min (9 min for exp 8),
  metric 20-30 s, guard 4-10 min alone and 9-10 min with three in parallel (the other two lanes ran on the machine).
- Tokens (Hermes session of this card's round-3 run, `state.db`, at the end of the loop): input 424  output 169 057  cache read 51 602 149  cache write 701 808; 211 API calls  249 tool calls; estimated 17.21 USD (the PR and review hand-off steps after this are not in it).
  Round 1 (the box run): input 242, output 105 301, cache read 22 481 846, cache write 710 252, 10.15 USD.

## Verdict on the tool

- The `autoresearch` classic loop is the right shape for this job: build -> metric -> guard -> keep / discard with the
  repo's own checkers made every result mechanical, and the guard stopped 16 of the 21 candidates, every one "better" by
  the metric but not manifold or over budget - exactly the OBJ03 failure the issue was written against.
- The reference decides what the loop learns. On element boxes it optimised towards boxes (17.6 m2 that meant
  nothing); on the meshes the same build is at 1030 m2 and the useful work was geometry robustness, not parameters.
- Evaluation cost bounds it again: the guard (`check_mesh`) takes minutes per candidate, so 21 iterations fit the
  time box and candidates were built speculatively while the previous guard ran.
- The metric still sees only silhouettes: the gaps between prisms are paid for, but openings, recesses, triangle
  economy and "one closed mesh" are not. A next program should state whether stacked closed shells are an accepted
  NPM form, and add opening coverage or a triangle term.

## Open items (for the user)

1. Visual acceptance of the final model (renders above; dump `C:/x/butovskaya-npm-twin/exp16_dump.json`, local).
2. The final model is separate closed prisms with 3.1 mm gaps, not one closed mesh: accept this NPM form, or ask for a
   noded stack builder (exps 4-8 show where the snapped one fails with 45-degree and curved outlines).
3. Opening planes are flush (pattern `opening-plane` asks a 0.4 m recess in `npm_min`) and split per prism.
4. Wall sweeps (cornices) are in the reference but not in the body; the basement band ends high in places.
5. Horizontal faces are CDT triangles; no FBX, materials table or UV: geometry only.

## Appendix: first attempt, element boxes (non-conforming exploration)

The first attempt (16:30-19:25) ran before a mesh route was known: the add-in's read API (`get_element_geometry`)
returns per element a bounding box, volume, area and face count, no tessellation, so the snapshot
`C:/x/butovskaya-snapshot/` holds one axis-aligned box per element (11 060 elements, 175.6 s, 63 elements/s, 0
failures; `elements.json` `9d80655d...`, `levels.json` `4e984c3a...`, `snapshot_dump.json` `d0a364f8...`). Against
those boxes the loop went 334.066 -> 17.584 in 20 iterations (4 kept). Review round 1 (P1-1) classed this as
non-conforming: `scripts/snapshot_revit.py` now fails closed on a bbox-only answer and `scripts/evaluate.py` reads a
box snapshot only with `--exploratory-box-reference` (`"conforming": false`). The round-3 setup build is that run's
best build: measured against the meshes it scores 1029.978, because element boxes of the 45-degree wings fill the
courtyards in plan. Its experiment table: `scripts/report_experiments.py --box` (`autoresearch/results.json`).
