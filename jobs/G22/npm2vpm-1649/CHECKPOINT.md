# G22 NPM-to-VPM regions — #1649 checkpoint

**v011 — aggregate xView counts improved on the copy; seam gate is still open.**
Subdividing the neighbouring edges at measured T-junctions gave 366 face
selections, 0 close vertices, and 2 bow-ties versus the source 370 / 0 / 4.
Eight of the 33 tracked source pairs still have candidate hits; the raw xView
verdict is FAIL. Do not promote this copy to a VPM master.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v011-conforming-seams/`
(18 verified files; manifest SHA-256
`2d35d6bb697b212fe07c1eee41d6aa0ace508a6ab605dd67fff093db614fc567`).
It includes the 33-spot sheet, the 22 edge splits, the fresh xView report, and
source-indexed residual measurements. The largest remaining near-parallel
projected overlap in one triangle pair is 0.00215121 m² (100923/136740).
No strict transverse intersection was measured in the 33 spots.

Normal authority is resolved: [D363] permits flat tangent-space Normal PNGs
RGB (128,128,255) for G22 only. Retain V007/C46 and its manual delivery review;
no other check is waived. [D362] records the earlier 460-face approval (called
D355 in the older evidence). The sealed v011 sheet and report use provisional
label D361 for the same Normal decision; the registry entry is D363.

## Historical checkpoint v010

The `npm-to-vpm` skeleton uses the immutable #1630 r2 inputs. All 12 outstanding
ownership dispositions were applied on a diagnostic Blender copy. Native readback
plus a strict intersection test found zero of the eight targeted transverse
intersections, but xView remains above the inherited counts. A local weld removed
the near-vertex pairs but increased bow-tie counts. It is not a master.

The shared VPM UV policy computes an isometric chart from world geometry. Blender
Cycles rebaked the G22 mesh001 #39124 witness onto a 4096 tile at 520 px/m; all 36
sampled points matched the bound Diffuse. This is a one-triangle proof, not a
Multi/Sub, a final tile allocation or a checker result. The two native source FBXs
contain three Diffuse/metallic/opacity/roughness sets and no Normal. VPM requires
Normal; C46/[D197] was not itself authority for G22. See [D363] above.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v010-metric-rebake-normal-STOP/`
(28 verified files, manifest SHA-256
`7ec083f3e1391fa8cb530c1debb00afe216f62c6860a3a17ed187b39a0867bdc`).
The v006 and historical colour runs below are retained for provenance.

## Historical source preflight (v006)

The v005 atlas layout was replayed through the shared `recover_regions` clipper
without regenerating or adjusting its borders. It assigned 147893 / 73137 / 51146
source faces, respectively, with zero gaps and zero splits; the other 293 / 167 / 0
are [D362]. The two previously approved zero-area drops are outside those counts.
Cell coverage is not a material approval; no palette tolerance was used for this map.

Fresh script-disabled Blender import and `dt qa xview --profile VPM-OKS --coords local`
on the two source FBXs report FAIL for both files. The Overlapping Faces selections
are 370 / 0 / 7 by mesh, separate from 557 / 6 / 51 candidate face pairs. Mesh 001
also has four bow-tie vertices. Mesh 002 in the original FBX still contains the two
zero-area polygons omitted in the UV replay; no additional drop was made.

Independent intersection using the r2 metre-local triangle coordinates confirmed
35 mesh001 pairs with projected overlap >0.001 m² and plane separation <1 µm. A
concrete witness is source polygons 108154 and 108462 (zero based): same plane,
0.028799661 m² in common, and neither face is in [D362]. Subdivision with unchanged
world surfaces cannot remove this positive-area overlap. Ask whether to correct the
confirmed overlaps on a separate copy, or receive corrected source FBXs. Do not
interpret the full candidate count as a deletion list.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v006-source-overlap-STOP/`
(source hashes, exact indices, report, and overlap sheet). Native VPM, metric seam
list, per-tile readback and SINTEZ checker remain outstanding.

[D362]: the exact 460 source triangles use one solid placeholder with their
mean source Diffuse colour. Do not rebuild their UV, rebake, or apply the texel
band to these triangles. This does not exempt any neighbouring triangle. Use
Blender only for any production continuation. The two zero-world-area source
polygons previously approved for removal remain accounted for by #1630.

## Shared primitives

- `tools.library.npm_ids.recover_regions` uses the existing facade segmenter
  and exact pixel-space intersections. A mixed leaf is subdivided by connected
  palette masks. A source triangle not fully covered remains a reported
  residual, rather than publishing part of the triangle or guessing a finish.
  Its explicit cell-layout lane also clips an externally measured partition;
  it rejects duplicate keys, unsupported kinds, invalid polygons and overlaps.
- `npm2vpm_core.fit_metric_region` uses a *new* metric chart in metres from the
  caller, prefers named panel/zone seam coordinates, clips geometry and UV
  together, and returns separate tile-local pieces. It does not derive such a
  chart from distorted NPM UVs or allocate the final finish/UDIM table.
- Next when the atlas partition is resolved: transfer pieces to a conforming
  native copy, lay out textured charts through `vpm_uv`, allocate per-piece
  IDs/tiles, and run Blender readback, checker and xView. No PASS is claimed.

## Historical RGB-tolerance control (superseded by v005)

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v002-colour-STOP/`.
The folder contains three atlas sheets, a tolerance matrix and exact original
polygon IDs with input SHA-256 bindings. The sheets use RGB8 max-channel
comparison (`distance < 18`); lower runs at `<6` and `<12` are retained.
The sealed diagnostic sheets retain the pre-publication decision label;
[D362] is the registry ID for that same approval.

| Mesh | Source after approved zero-area drops | Placeholder | Residual at <18 | Faces cut in UV at <18 |
|---|---:|---:|---:|---:|
| 001 | 148186 | 293 | 13135 | 5322 |
| 002 | 73304 | 167 | 10610 | 550 |
| 003 | 51146 | 0 | 3370 | 24 |

The narrow palette produces fragment IDs (108 used IDs on mesh001 at `<6`),
while broader tolerances still leave atlas footprints that cross blended,
patterned or unresolved swatches. Neither a majority vote nor converting all
unclassified pixels to one finish is a source-bound material decision. Request
a marked material boundary mask (with patterned/solid labels) for the marked
areas or an equivalent source material-ID map only if the geometric atlas replay
cannot resolve them. These historical counts are not final material IDs, tile
allocations or a geometry cut list.
