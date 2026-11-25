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

### v006 not accepted -> v007 ([D384])

Artem 2026-11-24 ~16:00 rejected v006 («нет колон, нет пергол, нет декор панелей объёмных») and asked for a completeness
census first; on the census (~19:55, «Принимаю рекомендации», [D384]) he allowed roof wells inside the S/N/D parapets.

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
- Body v007 = the v005 lattice + `roof_wells` (`volume_body.py`, [D384]): the flat top cap of S/N/D becomes a parapet top
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
