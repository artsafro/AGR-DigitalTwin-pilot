# G22 NPM-to-VPM regions — #1649 checkpoint

## v020 — confirmed finish, source-plane trial (release STOP)

[D381] records Artem's v019 approval: keep face 130433 in the two lower pairs
and A in all fourteen upper pairs. The v019 Revit-derived orientation and wall
IDs are retained; the geometry was not shifted to the distant Revit plane.
For the seven over-limit pairwise cuts, rebuilt the non-overlapped B footprint
from the measured lattice. A common shadow mask per panel preserved the cut
across its diagonal. The conforming-edge replay split 12 adjacent faces on
their existing edges; it did not change their finish or coverage. Fresh
Blender readback found all six protected source signatures unchanged, and
maximum reconstruction deviation from a source plane was 0.001181 mm.

All 16 target pairs are gone. Raw xView face pairs went 534 to 523 and
source-lineage pairs 525 to 509, with no new lineage pair. The raw xView
face / near-vertex / bow-tie counts were 356/0/2 before, 373/0/14 on the
first trial, and 373/0/2 on the conforming trial. The affected faces were
subdivided in five remaining lineage pairs; the release verdict is still
FAIL. The master and original copies are unchanged; no FBX/ZIP or SINTEZ
release. No new finish question for the confirmed A faces.

Evidence: `G:/Мой диск/AGR-evidence/1649-g22-outer-pairs/v020/`, 41/41
verified files; manifest SHA-256
`e998745f319ae97bd38bc9dfd0011d6084cb429bb247d7127d5669ea826fcdd2`.
See `g22-v020-outer-pairs.png`, `pairs.csv`, `native-audit.json`, and
`remaining-xview.csv`. The 13 other deep v018 pairs remain. As a concrete
STOP witness, source pair 107979/108024 covers a whole native triangle of
108024 (0.185960 m², zero remainder), but deleting the triangle exposes two
existing attached edges about 0.994 m and 1.062 m long. The retained face
shares neither edge. The native edge inventory is in `full-footprint-witness.json`;
obtain a source-bound roof/reveal stitch before editing that junction.

## v018 — exterior-finish decision and native trim trial (STOP)

[D374] applies to every deep overlap: retain the confirmed exterior finish,
trim the neighbour by up to 275 mm on a copy, and require zero xView defects.
Keep the earlier explicit E finish selection as the E/19 trial control.

Script-disabled Blender 5.1.2 tested near-normal and raised exterior ray fans
on 41 pairs from the v017 ledger. Of the 29 deep pairs, neither fan confirmed
the exterior for 16: fourteen opposing-normal ID 11/11 pairs and two ID 3/3
pairs. This is not evidence that either hidden layer may be deleted. Request
one corrected mesh001 or a single exterior-finish reference for the group,
not separate finish decisions at each location.

The bounded trial replaced five parents with 19 children. Fresh native readback
confirmed both E/19 source pairs absent (100443/108605 and 100443/108606, up to
274.827 mm), with 148233 untouched world-local geometry/UV signatures and
unchanged transform. Six source pairs disappeared, three new pairs appeared;
xView changed from 356/0/2 to 354/15/6 (faces/near vertices/bow-ties), FAIL.
Unrepresentable cuts were not applied. Resume from the sealed v015 baseline,
not the v018 trial. No delivery FBX, package, final tile layout or SINTEZ receipt.

Private evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v018-outer-finish-STOP/`
(24 files, manifest SHA-256 `20a7ba95341e945cbd7d3c93888aa044527e6de479a56b05613c5e4d6f13351e`).
See `g22-v018-sheet-r2.png`, `pair-ledger-r2.csv`, `trim.json`, and
`verify.json`. The source manifest still verifies 32/32.

## v016 — native atlas replay, cut budget and remaining source overlaps

GeoJSON: customer-supplied, not in our package (Artem, 2026-11-21 08:28).
Carry this exact note into the delivery passport. The existing `agr package-vpm
--no-geojson` route supports the handoff; keep the validator and SINTEZ checks
unchanged and identify customer-side findings separately. The quad work FBX
(decision D366 on `origin/main`) is a sidecar, not a ZIP member. No release FBX/ZIP, validator receipt, or
SINTEZ receipt has been produced at this checkpoint.

Native replay on the sealed v015 copies gave zero unassigned faces: 148238 /
73307 / 51147 accounted for (including 293 / 167 / 0 D362 placeholders). No face
crossed a v005 colour-region boundary in these copies. These are **source-region
IDs**, not final Multi/Sub or exported tile assignments.

The in-memory 520 px/m triangle-by-triangle cut probe preserved area, winding,
edge metric, and tile containment. It found and then resolved one arithmetic
near-vertex cut collapse (mesh001 source polygon 38477); the shared kernel now
canonicalizes the cut line within four chart-coordinate ULPs and rejects any
remaining unrepresentable child. Applying these straight cuts independently
would raise mesh001 from 148238 to 150743 triangles before stitching, above the
150000 project target [D010]. A relaxed lower bound is 149363 (512 px/m, no
padding, existing source triangles retained, no conforming neighbour costs).
That gap does not prove that an optimized region-first layout cannot fit.

Raw xView remains FAIL outside the 33 repaired targets. On mesh001, 29 candidate
pairs have positive overlap even after eroding both projected boundaries by
50 mm; that is not a bulk deletion list. The strongest witness is source
100443 vs 108605 (E vs 19): 0.551948 m² projected overlap, 3.308 mm plane gap,
0.370415 m² remaining beyond both 50 mm boundaries. A UV cut or a <=50 mm trim
from the existing edges does not remove that core. The comparative result is
not the [D173] zero-count delivery rule. Resolve whether this handoff is a
comparative review candidate only or needs a scoped, finish-owned repair of
the larger inherited overlaps before release.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v016-native-coverage-and-budget/`
(17 files; manifest SHA-256
`2c1b4c3cf4f7cefad8586144d81df22c689b09002a82cbe004342d07cd8c4ae0`). See
`g22-v016-sheet.png`, `ids-and-cuts.csv`, `seam-probe-r2.json`, and
`residual-xview.json`. Resume with the sealed v015 Blender copies and the
source-bound v016 ledgers; no customer geometry, textures, or PNGs are in Git.

## v015 — scoped opacity and geometry readback

The §12.3 decision (orchestrator on t_2692a5c8, 2026-11-21 01:32)
was applied only to the three evidenced source triangles: mesh001/106249,
mesh002/32708, and mesh003/1132. The headless Blender 5.1.2 copy retains each
front triangle and adds one flipped back triangle, 8 mm behind it. Fresh
native readback verified lineage, offset and source UV correspondence. The
six 4096² Diffuse RGBA witness maps preserve source opacity on new isometric
520 px/m UVs, including texels on both sides of alpha 128. These are raster
witnesses, not final tiles or an exemption for other opacity-bearing faces.

A drop-only control on mesh002 reproduced the two bow-ties after removing
68903 and 69759. They were not introduced by alpha backs. Noding the adjacent
edges of source faces 68904 and 69760 closes the fans; no original vertex
moves. The existing middle vertices are 0.021 and 0.026 mm from the respective
long edges in the metre-local frame. The same frame measures small nonzero
areas on the dropped slivers, in contrast to the translated float32 world
coordinates used by the original exact-zero test. The drop authorization is
for those specific source indices only. The copied scenes now read back at
356/0/2, 0/0/0 and 7/0/0 (xView face selections / near vertices / bow-ties).
The 33 targeted pairs remain clear; the raw FAIL is retained.

The shared cell replay returned 0 residuals for the 147893 / 73137 / 51146
non-placeholder input faces using the v005 measured layout. This is source
coverage, not a final UV/ID assignment on the complete output mesh. Final
seams, tile allocation, Multi/Sub, exported FBX readback and Checker are open.
The authorized source manifest contains 32 verified FBX/PNG files and no
GeoJSON. The VPM ZIP and package Checker require project-authorized GeoJSON
for the _01/_02 deliverables; don't invent placement or required attributes.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v015-opacity-readback/`
(32 files; manifest SHA-256
`332bf5d18a77fe6992d7c9e9ecc48fdc0f825fd7c50b0fc7a6fb1dccbeb93a9d`). The
resume inputs are `opacity-01.blend` and `stitched-02.blend`. The Russian sheet
`g22-v015-sheet.png`, provisional ID table, native xView and removal/cut controls
are in the same directory. No client asset is tracked in Git.

**v013 — all 33 tracked seam pairs are clear on the repaired copy.**
The original VPM-OKS xView thresholds report 356 face selections, 0 close
vertices and 2 bow-ties versus 370 / 0 / 4 on the source. The two bow-ties are
inherited; raw xView is still FAIL. This is a comparative seam result, not an
absolute QA pass or a VPM export.

[D364]: the E face (100923) is unchanged. Finish 22 (136739/136740) was trimmed
in projection, including the axis-dropped footprint used by xView; maximum
reach from the original seam was 47.714 mm with the numerical allowance.
Local stitching/coalescing is recorded separately. A fresh native readback
found nine changed source lineages and 148212 unchanged input face rows, with
unchanged indexed adjacency among unaffected faces. Original hashes: 32/32.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v013-local-seams/`
(21 verified files; manifest SHA-256
`683864ae723b97d434d2acbe7da6e7f3805090c2ee6d4b31a20292ea225df935`).
Continue from `stitched-r3.blend` for mesh001. `native-audit.json` is the
before/after area and face-index ledger; `g22-33-pair-v013.png` is the seam
sheet. The atlas-to-VPM material/UDIM allocation and checker are still open.

## Historical checkpoint v011

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
  and exact pixel-space intersections. Mixed and majority-solid leaves are
  checked against connected native-resolution palette masks. A majority
  label cannot hide a second supported swatch. A source triangle not fully
  covered remains a reported residual; no partial triangle or guessed finish
  is published.
  Its explicit cell-layout lane also clips an externally measured partition;
  it rejects duplicate keys, unsupported kinds, invalid polygons and overlaps.
- `npm2vpm_core.fit_metric_region` uses a *new* metric chart in metres from the
  caller, prefers named panel/zone seam coordinates, clips geometry and UV
  together, and returns separate tile-local pieces. Any interior UV overlap
  in a tile blocks the entire plan and names the conflicting source triangle
  indices; boundary contact does not block. It does not derive a chart from
  distorted NPM UVs or allocate the final finish/UDIM table.
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
