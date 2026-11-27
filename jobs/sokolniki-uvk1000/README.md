# sokolniki-uvk1000 - #1784 building by the lattice method

Step 1 (lines sheet before building): openings list from the Revit FBX by the shared step
`tools/methods/body/revit_fbx_dump_blender.py` (Blender 4.4; 5.1.2 crashes on this FBX) ->
`tools/methods/body/openings_from_revit_fbx.py` with `openings_config.json` (this job's only file) -> lines by the
#1736 core `plan_adapter_dwg.lines_from_facades` + `lines_sheet.render` (PR #1770 head 8279609f, read-only).

```
blender44 -b --factory-startup --python tools/methods/body/revit_fbx_dump_blender.py -- C:/x/sokolniki-npm/intake/oks/src_copy/sokolniki_ar_r23_v1.fbx C:/x/ev_1784/sok_dump.json
uv run python tools/methods/body/openings_from_revit_fbx.py C:/x/ev_1784/sok_dump.json jobs/sokolniki-uvk1000/openings_config.json C:/x/ev_1784/sok_open_d.json
```

Result: 8 593 objects -> 59 facade lines (46 with elements), 1 644 objects in the openings spec, 184 exterior walls,
1 231 insets (rooftop cage, mesh fence, canopies, roofs, fins), 5 534 dropped with reasons. Global levels 47 (all
opening edges, snap 0.10 m). Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step1/` + `SHA256SUMS.txt`.
The global-lines sheet is historical. Artem's 2026-11-21 decision (issue #1784 comment) supersedes it.

## Step 1 v002 — volume proposal, no body build

`G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step1-volumes-v002/sokolniki-step1-volumes.pdf`
contains a colour keyplan, elevations by volume with visible level counts per facade, and a source-only
appendix for 30 unbound preliminary planes. The accompanying `volume-lines.json` accounts for all 59
preliminary planes and 427 source rectangles. `SHA256SUMS.txt` was verified for all 19 files
(manifest SHA-256 `6018da5feb51df2b7219ea7f180fa8421f057beb3f0d2723066c221e76833316`).

| Volume | Floor/line levels (excluding upper boundary) | Roof finish, m |
|---|---:|---:|
| N — north wing | 9 | 13.22 |
| D — main school block | 12 | 17.42 |
| S — low south block (kindergarten, provisional ID) | 9 | 11.12 |
| H — upper hall | 1 | 22.02 |

The four plan polygons are closed; five shared seam segments match in XY. H sits above D; this
is a roof interface, not another vertical seam. F05 (D06/D07) has 12/4 visible levels respectively,
excluding the upper boundary. This is plan closure, not proof of a welded mesh or opening topology.
The floor datums come from the FBX slab survey, since the two PDF elevation sheets do not give spot
heights. The PDF supplies the finish legend and visual elevation reference. Stations use
`lines_from_facades` from read-only #1770 (pinned `8279609f`, adapter file unchanged at `c97cf3ec`).
The external render driver is evidence-only, not a job builder.

The sheet proposes 225 opening cuts with at most three levels per storey and only matches within
0.20 m; no cut was moved beyond its source elevations in this run. 16 low doors (heads at +2.175 m)
cannot fit the selected floor/sill/head triplets within 0.20 m. They remain orange, not cut or waived.
The merged curtain-wall bboxes (including F05) and secondary planes are review items, not cuts;
the elevation outlines are schematic until those are resolved. F07/F21 are omitted from the envelope.
Modelling split [D336]: folded cassettes are texture, plain blank panels are finish-zone candidates,
and lamellas, roof cage, mesh, canopies and roofs are insets. NPM windows are body cutouts with separate
textured planes, no lattice lines on the planes.

Status: waiting for Artem's visual decision on v002 and on the conflicting door heads; no body built.
Ground, live DCC sessions and `C:/x/sokolniki-npm/` were not changed.

## Step 2 — body through the shared lattice core ([D375])

Artem accepted v002 on 2026-11-23 (and the +2.175 m door local cuts on 2026-11-22): [D375].
The core #1736 was used read-only from the PR #1770 head (`c97cf3ec`) while building v002-v005; since #1770 merged it
is loaded from `tools/methods/body/` on main.

```
uv run python tools/methods/body/volume_body.py C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step2/build-v004 --core <core>/tools/methods/body
blender44 -b --factory-startup --python tools/methods/body/volume_body_blender.py -- C:/x/ev_1784/step2/build-v004/meshes.json C:/x/ev_1784/step2/build-v004
uv run dt qa xview C:/x/ev_1784/step2/build-v004/body_quad.fbx --out .../xview_quad.json --profile NPM
uv run python tools/methods/body/volume_body_sheet.py C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step2/build-v004 <sheet dir>
```

Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step2-body-v004/` (`sok-step2.pdf`, 2 iso views and
elevations of every visible side with the closure result per volume, local-cut cells outlined orange, uncut
source rectangles dashed red; `metrics.md` table against the night v020; `SHA256SUMS.txt`, 23 files).

Result (quad copy): 4 volumes, 3 771 faces, 7 831 triangles after triangulation (v020: 51 737), 0 facade
triangles, every ring closed (N 10/10, D 13/13, S 10/10, H 2/2 levels, all stations continuous), 0 defect cells,
0 non-manifold edges, xView NPM 0/0 PASS, V004 has no fail (co-directional clearance `review`: 0 pairs under 20 mm).
Not in this body yet: insets [D336], 47 curtain-wall bboxes left uncut in v002 (F05 is blank), 16 `zone` panels.

## Step 2 v005 — decisions on the v004 comparison ([D378])

Artem 2026-11-24 accepted the five recommendations of `step2-compare-v004` ([D378]). The body is rebuilt from the
lattice with `body_config_v005.json` (no mesh repair):

```
uv run python tools/methods/body/volume_body.py C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step2/build-v005 --core <core>/tools/methods/body --config jobs/sokolniki-uvk1000/body_config_v005.json
```

- D02 (F04): the seven `crosses_visible_band` windows open from the seam side's `visible_from` (N top +14.30) to their
  head +16.44 - a local sill, the mirror of the [D375] local head; the front below keeps its v004 extent.
- F05: two `contour_cut` runs from the Revit curtain panels (sections D06/D07): D06 +7.525..+18.47 and D06+D07
  +13.50..+18.47, welded into one mouth (no zero-thickness transom, one glazing seat polygon); the glazing is a step-3 inset.
- F06 / 22daf24: an opening narrower than its source rect must be listed in `agreed_edge_clamps` (0.268 m) or the
  build fails; the local head +2.175 m stays.
- F13: the four window pairs share one mouth each, seat depth 0.394 m (`reveal_m_by_name`; Revit frames at
  -0.05..+0.094 and +0.25..+0.394 m).
- #1802: a seam hides only the band both volumes share (`[max base, min top]`); mate ends must coincide within 1 mm.

Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step2-body-v005/` (`sok-step2-v005-compare.pdf`, 14
sheets v004 | v005 | Revit, 7 sections; `compare_v005.json` with the t_57b332a4 measure, seat depths 0.15 / 0.394 m;
`SHA256SUMS.txt`, 23 files, manifest `274dc654…`; decision renumbered D376 -> D378 in review r1). Result: 4 volumes, 3 849 faces, 8 019 triangles after
triangulation, 0 facade triangles, 0 non-manifold edges, 0 bow-tie vertices, rings closed, xView NPM PASS. Walls equal
v004 on 21 of 22 measured facades; F04 missing wall +2.874 m2 = Revit wall inside the 7 new D02 window rects (frame
overlap, same rule as every cut). No opening ID got worse; 7 D02 windows went from missing to shifted. Waiting for
Artem's picture approval before step 3 (insets).

## Step 3 — insets on the accepted body v005 ([D378])

Artem 2026-11-24 ~14:15 started step 3 on the accepted v005: lamellas, roof steel cage, mesh and canopies = separate
insets, cassette folds = texture, the F05 outer glazing = an inset with its own ends closing the gap to the face.
The skeleton `oks-npm` is configured by `skeleton.json` (5 hooks, `skeleton_guard` exit 0); the body is not rebuilt:

```
blender44 -b --factory-startup --python-exit-code 1 --python jobs/sokolniki-uvk1000/hooks/inset_obb_blender.py -- C:/x/sokolniki-npm/intake/oks/src_copy/sokolniki_ar_r23_v1.fbx jobs/sokolniki-uvk1000/insets_config.json C:/x/ev_1784/step3/revit_obb3.json
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py C:/x/ev_1784/step3/revit_obb3.json C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step3/build-v006
blender44 -b --factory-startup --python-exit-code 1 --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- C:/x/ev_1784/step2/build-v005/body.blend C:/x/ev_1784/step3/build-v006/insets_meshes.json C:/x/ev_1784/step3/build-v006
uv run dt qa xview C:/x/ev_1784/step3/build-v006/body_v006_quad.fbx --out .../xview_quad.json --profile NPM
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py views C:/x/ev_1784/step2/volume-lines-v002.json <views.json>
blender44 -b --factory-startup --python-exit-code 1 --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- render <model> <views.json> <renders> v005|v006|revit
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py decor C:/x/ev_1784/sok_dump.json <decor_table.json>
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet <renders> <views.json> <build-v006> <decor_table.json> <new.pdf>
```

Modelling split [D336]: plinth=one_with_body; inset=roof_cage, roof_mesh, glass_canopies, lamellas_RAL8023,
F05_outer_glazing; texture=folded_cassettes, mullions, stemalit, finish_layer; reason=NPM, accepted body v005 untouched,
step-3 composition of [D378]; windows stay body cutouts with their v005 planes (trimmed to the accepted openings);
exception: flashings (D336 insets) and railings left out of step 3 - questions on the sheet.

Result (quad copy `body_v006_quad.fbx`): 5 inset objects, 6 122 quads, 12 244 triangles (Revit cage alone 3 152 968):
cage 610 columns -> 540 boxes (66 exact Revit duplicates, 4 touching pairs joined) and 498 beams -> 436 diamond tubes;
101 mesh planes; 10 canopy sheets; 7 lamellas; F05 glazing over 198 Revit panels, a 7-step sawtooth 0.03..1.70 m in
front of D06/D07, clipped to the v005 mouth, top/bottom closures and end quads to the face. Body hash N/D/S/H before =
after; master_topology pass for all 5 inset objects (body n-gons = accepted v005); xView NPM 0/0/0 PASS; FBX readback ok.
3ds Max was not run: native Max checks `not measured`. Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step3-insets-v006/`
(`sok-step3-v006.pdf` 30 sheets: summary, decor table of all 53 Revit families with 4 questions, 27 facades
v005 | v006 | Revit, iso; `SHA256SUMS.txt` 97 files, manifest `cddc38a5…`). Waiting for Artem's picture approval.

### v006 not accepted -> v007 ([D410])

Artem 2026-11-24 ~16:00 rejected v006 («нет колон, нет пергол, нет декор панелей объёмных») and asked for a completeness
census first; on the census (~19:55, «Принимаю рекомендации», [D410]) he allowed roof wells inside the S/N/D parapets.

```
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py census C:/x/ev_1784/sok_dump.json C:/x/ev_1784/step2/volume-lines-v002.json <census.json>
uv run python tools/methods/body/volume_body.py C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step3/build-v007-body --core tools/methods/body --config jobs/sokolniki-uvk1000/body_config_v007.json
blender44 -b --factory-startup --python-exit-code 1 --python tools/methods/body/volume_body_blender.py -- <build-v007-body>/meshes.json <build-v007-body>
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py welldiff C:/x/ev_1784/step2/build-v005/meshes.json <build-v007-body>/meshes.json jobs/sokolniki-uvk1000/body_config_v007.json C:/x/ev_1784/step2/volume-lines-v002.json <well_diff.json>
blender44 ... hooks/inset_obb_blender.py -- <Revit FBX> jobs/sokolniki-uvk1000/insets_config.json C:/x/ev_1784/step3/revit_obb_v007.json
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py C:/x/ev_1784/step3/revit_obb_v007.json C:/x/ev_1784/step2/volume-lines-v002.json C:/x/ev_1784/step3/build-v007 --body-config jobs/sokolniki-uvk1000/body_config_v007.json
blender44 ... hooks/inset_write_blender.py -- <build-v007-body>/body.blend <build-v007>/insets_meshes.json <build-v007> v007
uv run dt qa xview <build-v007>/body_v007_quad.fbx --out <build-v007>/xview_quad.json --profile NPM
blender44 ... hooks/inset_write_blender.py -- render <model> C:/x/ev_1784/step3/views_v007.json <renders7> v007   (+ v006 / revit for C5)
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet7 <renders7> <renders v006> <census closeups> <views_v007.json> <build-v007> <build-v007-body> <decor_v007.json> <new.pdf>
```

- Census: 8 593 Revit objects, 0 without a rule (table 1 of the sheet). The census and the well proof are subcommands of
  `inset_sheet.py` and the renders are the `render` mode of `inset_write_blender.py`: the job keeps 4 listed hooks (<= 5, [D324]); `skeleton_guard` exit 0.
- Body v007 = the v005 lattice + `roof_wells` (`volume_body.py`, [D410]): the flat top cap of S/N/D becomes a parapet top
  band (0.15 m; 0.30 m on D06/D07 so the well wall stands behind the F05 window plane), inner well walls and a deck at
  the Revit roof finish 11.12 / 13.22 / 17.42 m; H is re-based 17.50 -> 17.42 onto the D deck (`base_by_volume`).
  `welldiff`: outside_diff 0 - only the three caps removed, 1 852 / 604 / 1 384 v005 faces of S/N/D unchanged, H only its
  base. v005 rebuilt with the same code is byte-identical (`meshes.json` sha256 equal). Body: 0 other open edges,
  0 non-manifold, 0 bow-tie, xView NPM PASS.
- Insets v007: pergolas = the roof cage (540 posts, 436 beams) now standing on the decks; 234 decor relief solids (10 planar
  quads: back, rim, 4 pyramid facets to the Revit apex truncated to a 5 cm top, 2 cm joint, 19 mitred corner pairs);
  4 F05 piers (boxes aligned to the D06 face, Revit front, 5 cm into the body) and 5 ground-floor glazing strips 2 cm in
  front of the face up to the mouth sill 7.525 m (Revit glass stands 1.6-2.5 m deeper, inside the accepted body);
  232 flashing quads; 3 roof hatches. 8 741 quads, 17 482 triangles, 0 non-quads; xView NPM 0/0/0 PASS (assembly).
- 3ds Max was not run: native Max checks `not measured`. Evidence:
  `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step3-insets-v007/` (`sok-step3-v007.pdf` 35 sheets: summary, table 1,
  27 facades v006 | v007 | Revit, 5 close-ups C1-C5, iso; `SHA256SUMS.txt`). Waiting for Artem's picture approval.

### v008 — strictly by the accepted modelling plan sokolniki-v002 (#1896)

Artem 2026-11-25 accepted the scene split v004 and the modelling plan `sokolniki-v002` (decision row comes with
PR #1899, id pending renumber). v008 follows every plan row (geometry / inset / texture / not shown):

```
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py C:/x/ev_1784/step3/revit_obb_v007.json C:/x/ev_1784/step2/volume-lines-v002.json <build-v008> --body-config jobs/sokolniki-uvk1000/body_config_v007.json --plan "G:/Мой диск/AGR-evidence/1896-oks-modelling-plan/sokolniki-v002/modelling_plan.json" --dump "G:/Мой диск/AGR-evidence/1867-scene-prepare/sokolniki-v004/dump.json" --body-meshes <build-v007-body>/meshes.json
blender44 ... tools/methods/body/volume_body_blender.py -- <build-v008>/body_meshes.json <build-v008>/body
blender44 ... hooks/inset_write_blender.py -- <build-v008>/body/body.blend <build-v008>/insets_meshes.json <build-v008> v008
uv run dt qa xview <build-v008>/body_v008_quad.fbx --out <build-v008>/xview_quad.json --profile NPM
blender44 ... hooks/inset_write_blender.py -- render <build-v008>/body_v008.blend C:/x/ev_1784/step3/views_v007.json <renders> v008
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet8 <renders> "<renders7>;<renders>;<v007 closeups>" C:/x/ev_1784/step3/views_v007.json <build-v008> <modelling_plan.json> <new.pdf>
```

- `--plan` drops every Revit object whose verdict is texture / not shown (1 decor panel [2284113] of layer 09,
  640 + 98 curtain glass, 11 piers, 147 BM slats); the F05 ground glazing is built from 89 panels instead of 129.
- `--body-meshes` moves the v007 body's WINDOW faces (Windows 362, Doors 20, Glazing 2, by the nearest planned Revit
  object) and the 4 ROOF decks into own inset objects, not welded to the body; body + insets face multiset = body v007.
- Mullions and stemalit = texture; railings NOT built (own card t_086564bb). Budget: body 8 099 + insets 18 510 =
  26 609 triangles (plan ~40 000). xView NPM 0/0/0 PASS; Max not measured.
- Open for Artem: 4 of 232 windows, 17 of 33 doors and ~598 of 885 curtain-wall glass panels (F05 has 287) have no
  opening in the accepted body (e.g. F01): an inset needs an opening, i.e. a body change.
- Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step3-insets-v008/` (`sok-step3-v008.pdf` 37 sheets:
  summary, 3 table sheets plan verdict -> v008, 27 facades v007 | v008 | Revit, 5 close-ups, iso; `SHA256SUMS.txt`).

### Body v006 — the missing openings cut ([D408]) + assembly v009

Artem 2026-11-25 ~12:20 («Да»): the accepted body was blind where Revit has windows (F01: three rows vs a plain wall).
Body v006 = the v007 body config ([D378] + [D410] wells) + openings generated by the 5th hook `hooks/body_openings.py`
(stage body/before), built by the shared lattice core (no mesh repair); the v008 insets are re-seated by the same
`--body-meshes` partition:

```
uv run python jobs/sokolniki-uvk1000/hooks/body_openings.py "<split v004 dump.json>" "<modelling_plan.json>" C:/x/ev_1784/step2/volume-lines-v002.json jobs/sokolniki-uvk1000/body_config_v007.json jobs/sokolniki-uvk1000/body_config_body_v006.json <openings_report.json>
uv run python tools/methods/body/volume_body.py C:/x/ev_1784/step2/volume-lines-v002.json <body-v006> --core tools/methods/body --config jobs/sokolniki-uvk1000/body_config_body_v006.json
blender44 ... tools/methods/body/volume_body_blender.py -- <body-v006>/meshes.json <body-v006>
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py C:/x/ev_1784/step3/revit_obb_v007.json C:/x/ev_1784/step2/volume-lines-v002.json <build-v009> --body-config jobs/sokolniki-uvk1000/body_config_body_v006.json --plan <modelling_plan.json> --dump <dump.json> --body-meshes <body-v006>/meshes.json
blender44 ... (body + inset_write_blender.py v009, render) as for v008
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet9 <renders9> "<renders8>;<renders>" C:/x/ev_1784/step3/views_v007.json <build-v009> <openings_report.json> <body-v006>/build_report.json <new.pdf> --decision D408
```

- Rule: every planned inset window / door / curtain-glass object (+ stemalit of the same field) is projected on its
  facade edge; not covered by a built rect and in the facade plane (depth <= 1 m; ground-floor entrance niches up to
  5 m with the reveal capped at 0.95 m, the core limit) -> touching panels (gap < 0.25 m) form one `contour_cut` rect;
  reveal = Revit glass depth (>= 0.08 m); edges snap to body levels in the core (0.20 m) else local sill / head on a
  10 cm grid; corner piers 0.30 m, the top 0.25 m and the [D410] parapet stay closed; a rect sharing a cell with
  another opening of different levels is trimmed to the next level (transoms over doors stay closed).
- Result: 47 new openings; windows 232/232, doors 22/33 in body openings (+5 behind the F05 piers), curtain glass
  483/885 in body openings + 133 by the F05 insets (rest: 153 behind volume seams, 85 interior glass walls > 5 m deep,
  14 in upper niches, 17 trimmed / transoms); body 9 681 + insets 18 752 = 28 433 tris; body 0 defect cells,
  0 non-manifold, 0 bow-tie, 0 facade triangles; xView NPM body and assembly PASS; Max not measured.
- Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step3-body-v006/` (`sok-body-v006.pdf` 24 sheets:
  summary, placed-vs-Revit table, 47 openings, 19 facades body v005 | v006 | Revit, iso; `SHA256SUMS.txt` 45 files,
  manifest `9e4f7501…`).
- **Accepted** by Artem 2026-11-25 ~14:00 («Да»): body v006 and assembly v009 ([D409]); the uncut fill stays uncut
  for the reasons on sheet 2. Next OKS stage: UV / materials / atlas on v009 (not started on this card).

## Step 4 — material IDs, UV and the NPM atlas on v009 ([D412])

Artem 2026-11-25 ~19:30 («Да», #1925): IDs / UV / NPM atlas on the accepted body v006 + assembly v009 [D409]. The skeleton
keeps 5 hooks: the work is the `uv` and `render atlas|checker` modes of `inset_write_blender.py`, `body_finish` in
`inset_build.py` and the `uvsheet` subcommand of `inset_sheet.py`; the spec is `uv_config.json`. Blender 4.4 for the master,
5.1 for the shared export (its FBX writer needs `SMOOTH_GROUP`):

```
blender44 -b --factory-startup --python-exit-code 1 --python jobs/sokolniki-uvk1000/hooks/inset_write_blender.py -- uv <step3-body-v006>/assembly/body_v009.blend jobs/sokolniki-uvk1000/uv_config.json C:/x/ev_1784/step2/volume-lines-v002.json <uv>
uv run agr vpm-to-npm --blender blender51 jobs/sokolniki-uvk1000/uv_config.json <atlas> --master <uv>/master_v001.blend --then-npm <uv>/master_v001.blend jobs/sokolniki-uvk1000/uv_config.json <atlas> <npm>/fbx NPM
uv run dt qa xview <uv>/parts_quad.fbx --out <uv>/xview_parts_quad.json --profile NPM     (+ the exported FBX)
blender51 -b --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- <npm>/fbx/NPM_Sokolniki_UVK1000_01.fbx <npm>/readback.json
blender51 ... hooks/inset_write_blender.py -- render <npm>/fbx/NPM_Sokolniki_UVK1000_01.fbx <views_uv.json> <renders> atlas|checker 26.1481,61.9071
blender44 ... hooks/inset_write_blender.py -- render <step3>/assembly/body_v009.blend <views_uv.json> <renders> v009     («До» for the before/after pages)
uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py uvsheet <renders> <uv> <atlas> <npm> <joined v009 xview.json> <new.pdf> --decision D412
```

- IDs: 14 finishes of the PDF passport. Body by volume and the existing lattice levels: N dark brick (0-0.6 porcelain), D light
  cassettes over a porcelain ground floor (to +3.84), S light cassettes over a dark brick ground floor (to +3.04), H light
  cassettes; the dark / light joints lie on the existing N|D and S|D corner verticals and levels (no new cut). Jambs, sills,
  heads, soffits = reveal RAL 9003; parapet tops and inner parapet / well walls = flashing RAL 7016; insets by their v009
  material (`material_map`). Canopy glass = `*_MainGlass`.
- UV: shared `tools/blender/vpm_uv.py` (edge-ring texel cuts, quad side <= 3.94 m minus the pattern period [D320], periodic
  metre projection, stacked islands); 15 textured n-gons larger than a tile are bisected on world-axis planes (hook
  `split_overflow`, shared edges, no vertex move). Flat-colour objects are not cut. Imposts / window frames stay texture.
- Result: 28 313 -> 32 731 triangles + 120 glass (target ~40 000, limit 150 000); accepted vertices moved max 0.0 m; UV
  overflow 0; open-edge length unchanged on every object, 0 non-manifold; xView NPM per object 0/0/0 PASS; V006 atlas padding
  PASS; FBX readback ok. The single `*_Main` of `dt derive npm` fails xView (957 faces / 4 406 verts) - the same join of
  v009 WITHOUT UV fails too (738 / 3 836): inset-to-body contacts, open for Artem at the delivery stage.
- SYNTHETIC look (shared painter joints, approximate RAL, no X folds / per-type frames / 20 mm mesh); address placeholder;
  Max not run. Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step4-uv-atlas-v001/` (`sheet-v002/sok-step4-uv-atlas-v002.pdf`
  11 sheets incl. «До» v009 | «После» atlas for F01 / F05 / iso from the same cameras; v001 sheet kept; atlas, master,
  NPM FBX, xView / readback, renders; `SHA256SUMS.txt` 55 files, manifest `ac7831f5…`).
  Artem 2026-11-25 ~22:40 ([D413]): material zoning + atlas layout of sheet v002 (14 IDs) **accepted**. The joined
  `*_Main` xView contacts are fixed at delivery: inset elements offset 1-2 mm off the wall plane + a before/after sheet
  proving the look is unchanged (not done here; the delivery FBX is out of scope). **Windows not accepted**: question
  sheet `step4-uv-atlas-v001/question-windows/sok-question-windows-v001.png` (sha `a44cc4ba…`; 6 types W1-W4 / D1 / CW,
  Revit | v009 | NPM atlas, 3/4 + straight-on, measured numbers; `SHA256SUMS.txt` 98 files); no window rework before
  Artem's answer.

### Windows as facade texture ([D417])

Artem 2026-11-26 ~10:10 («окна показываем текстурой на фасаде»): no frame / mullion geometry; the window / door insets
keep their flat v009 faces and get a whole-window drawing of their own Revit instance in the atlas:

```
blender44 ... hooks/inset_write_blender.py -- winscan <step3>/assembly/body_v009.blend <revit sokolniki_ar_r23_v1.fbx> <winscan.json>
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py wintex <winscan.json> jobs/sokolniki-uvk1000/uv_config.json jobs/sokolniki-uvk1000/uv_config.json
(then the step-4 chain above: uv -> agr vpm-to-npm -> xview / readback / render)
```

- `winscan` (read-only) pairs every v009 window / door face with the Revit instance whose box holds it (369 / 369 window
  faces, 22 / 27 door faces; 244 instances) and reads that instance's glass panes. `wintex` writes `uv_config.json`:
  finishes 07 / 08 become `pattern: elevations` (shared `tools/derive/finish_painter.py`): one drawing per type x size class x
  hand (07: 15 + `_face`, scale 0.33; 08: 9 + `_face`, scale 0.60), RAL 7016 profile, glass panes of the most frequent
  instance; `window_texture.instances` = one row per Revit instance. `uv` maps each face's corners by the instance box onto
  its drawing (explicit UVs, no cuts, no vertex moved); 5 door faces without an instance get the `_face` drawing.
- Result: 32 073 triangles (was 32 731: the window / door faces are no longer cut by the old periodic grid); max vertex move
  0.0 m; UV overflow 0; V006 PASS; xView per object PASS; readback ok. NPM density: windows ~31 px/m, doors ~56 px/m.
- Curtain walls: see the next section ([D418]).
- Evidence: `step4-uv-atlas-v001/windows-texture-v001/sok-windows-texture-v001.png` + `.pdf` (Revit | v009 | NPM before |
  NPM after on the question-sheet cameras, atlas regions, F01 before / after), atlas, master, NPM FBX, winscan;
  `SHA256SUMS.txt` 129 files. Accepted by Artem 2026-11-26 ~17:55 [D418].

### Curtain walls drawn by their Revit panels ([D418])

Artem 2026-11-26 ~17:55 («Принимаю»): windows W1-W4 + doors accepted as is; curtain walls - small ones (<= 1.6 x 3.4 m)
like windows, large ones as a grid with the Revit pitch; glass dark blue with gradient, frames RAL 7016 (provisional).

```
blender44 ... hooks/inset_write_blender.py -- cwscan <step3>/assembly/body_v009.blend <revit sokolniki_ar_r23_v1.fbx> jobs/sokolniki-uvk1000/uv_config.json <cwscan.json>
uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py wintex <winscan.json> jobs/sokolniki-uvk1000/uv_config.json jobs/sokolniki-uvk1000/uv_config.json --cw <cwscan.json>
(then the step-4 chain above: uv -> agr vpm-to-npm -> xview / readback / render)
```

- `cwscan` (read-only) takes every vertical v009 face of finishes 05 / 06 (97: 20 + 77) and the Revit curtain panels
  (`Системная панель ADSK_Стеклопакет` / `Стемалит`) of the Revit wall layer nearest to it within 2.5 m (the F05 ground
  wall stands 2.1 m behind its inset). `wintex --cw` joins touching coplanar faces into one wall (97 faces -> 60 walls:
  11 small `CWs_`, 36 large `CW_`, 13 F05 `CF_`) and draws each distinct wall from its own Revit panels in the 05 / 06
  tiles (`pattern: elevations`, shared `finish_painter`); 4 faces without Revit panels (Glazing 10-13, 2.2 m) get a 1 m
  grid with transoms at the Revit transom levels. UVs are explicit per wall box (no grid cuts; only the shared 4 m
  max-quad-side split).
- Result: 31 377 triangles (r4: 32 073); max vertex move 0.0 m; UV overflow 0; V006 PASS; xView per object PASS;
  readback ok. NPM density: 05 ~133 px/m, 06 ~84 px/m. Glazed doors inside the F05 walls read as RAL 7016 profile.
- Evidence: `step4-uv-atlas-v001/curtain-walls-v001/sok-curtain-walls-v001.png` + `.pdf` (Revit | before | after
  close-ups of a small, a large and an F05 wall; F05 / F01 / F04 / iso before / after; atlas), master, NPM FBX, cwscan;
  `SHA256SUMS.txt` 176 files.

## Step 5 — NPM delivery package v001 ([D419])

Artem 2026-11-26 ~21:40 («Да», #1966): the NPM package on the accepted master of step 4 (curtain-walls-v001,
`master_v001.blend` sha `013cf06b…`). The joined `*_Main` failed xView NPM (953 faces / 3 896 vertices): insets touch
the body. Delivery copy only, the accepted master is not edited:

```
blender44 ... hooks/inset_write_blender.py -- dump <cw-v001>/uv/master_v001.blend <d>/dump_v001.json
uv run python tools/derive/inset_offset.py <d>/dump_v001.json <d>/offset_plan_6mm.json --target-mm 6 --weld-anchor
blender44 ... hooks/inset_write_blender.py -- offset <cw-v001>/uv/master_v001.blend <d>/offset_plan_6mm.json <d>/master_v002.blend
uv run agr vpm-to-npm --blender blender51 jobs/sokolniki-uvk1000/uv_config.json <d>/atlas --master <d>/master_v002.blend --then-npm <d>/master_v002.blend jobs/sokolniki-uvk1000/uv_config.json <d>/atlas <d>/npm/fbx 0000
uv run dt derive --blender blender51 npm <d>/master_v002.blend jobs/sokolniki-uvk1000/uv_config.json <d>/atlas <d>/work/fbx 0000 --keep-quads   (quad WORK FBX)
uv run dt qa xview <fbx> --out <xview.json> --profile NPM          (delivery + work FBX)
uv run agr package-npm <d>/pkg --allow-incomplete                 (no Ground: diagnostic ZIP)
uv run agr build-manifest build <zip> --master oks=<d>/master_v002.blend --derivation <d>/npm/derivation --transform-name "..." --blender blender51
uv run agr validate <zip> --profile npm --scene --json --export-meta <v013.json> --master oks=<d>/master_v002.blend --npm-atlas <fbx>=<d>/atlas/npm_atlas.json
uv run agr validate <zip> --profile npm --scene --json --export-meta <v013.json> --master <work_quads.fbx>     (V003)
```

- `inset_offset.py` (shared, pure numpy over the xView kernel): body volumes (components with finishes 01/02/03) are
  anchors; every inset component moves rigidly off the face it touches until the planes are 6 mm apart (NPM xView
  face_m = 5 mm: a 2 mm offset leaves 341 inset-body + 40 inset-inset face pairs); a component pushed both ways moves
  per vertex (F05 outer glazing shortened at its ends, 1 cage post thinned), a mesh held between cage frames is
  pinned and the frames move; exactly coincident body-seam vertices are welded (20, no move, no bow-tie).
- Result: 382 insets moved (windows 228 x 6 mm, curtain strips 47 x 6-18 mm, doors 19, decor 38 x 1-9 mm, frames 42,
  fins 4, deck 4), max 18 mm; 31 377 + 120 glass triangles unchanged; pixel diff on the review cameras <= 0.014 %;
  xView delivery FBX 89 faces / 20 vertices, work FBX 52 / 20 - all at the body-volume seams (D|N +13.50: 0.9 mm
  level mismatch and coplanar overlap in the accepted body v006), 0 inset pairs.
- `agr validate`: V002 / V005 / V006 / V012 pass; V001 fail (no Ground, site placement out of scope); V003 fail on the
  work FBX (123 n-gons of the accepted body, 1 462 T-junctions review); V004 fail (49 887 self-intersections, before
  47 965: the pergola cage crossing itself 39 176, insets set into the body; 7 seam pairs < 5 mm). SINTEZ / Max xView
  not run (Max closed by day). Fences, UCX, GeoJSON: not in this package (README of the package).
- Evidence: `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step5-npm-package-v001/` (ZIP, work FBX, build manifest,
  master v002 + plans, xView / validate / self-intersection reports, before / after / diff renders, Russian summary
  `svodka-npm-package-v001.md` + `sok-npm-package-v001.png`; `SHA256SUMS.txt` 58 files, manifest `de36883e…`).
  Waiting for Artem's acceptance in 3ds Max (quads) and his answers on the body seams, V004 and UCX / GeoJSON.
