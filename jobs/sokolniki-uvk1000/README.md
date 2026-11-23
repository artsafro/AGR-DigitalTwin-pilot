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
The core #1736 is not merged; it is used read-only from the PR #1770 head (`c97cf3ec`).

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
