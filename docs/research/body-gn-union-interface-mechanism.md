# Building-body GN: why exact UNION retains shared band interfaces

`delivery_passed=false`. Report-only diagnosis. No writer repair, no face removal, no chosen winding, no tolerance, receipt, gate or benchmark-row change. The contour input is `synthetic_drawing: true`. This is not a drawing-backed test of a real building.

## Summary

The unchanged weld→boolean interval reproduces #746: weld has 0 undirected index extras, and the exact self-union has 9,426 (1 same direction, 9,425 opposite). Turning only Hole Tolerant on leaves those 9,426 extras in place. The frozen 6.9 m band pair, under the same settings, produces 0 extras, so the twins are not a property of that adjacent pair alone. Upper-band `z0` was not snapped: the frozen extrude-index rule did not identify an endpoint, and that probe was not replaced with another match. Before the boolean, four nominal interfaces sit on two float32 heights one ulp apart (13.7, 30.7, 65.4, 69.45 m); the other shared heights are a single float32 value, and those single-height interfaces are where the opposite extras are counted, with 65.4 m the mixed case. The one pre-weld coordinate pair is bitwise-equal, distance 0, while Merge by Distance is Mode All, selection unlinked with default True, distance float32(1e-5); it is still one pair, not the 9,426. Verdict: **consistent but unisolated**. Counts do not certify the exterior or the normals.

## Findings

Labels: **verified** (this run or the pinned source read here) or **source claims** (the #746 report, not re-derived beyond the comparison below).

### Sources and versions (verified)

| Item | Value |
|---|---|
| Writer read | `24c94691e54736411d6f6d26c810c25d10505e90:tools/methods/body/body_blender.py` `_gn_tree` (lines 72–106) and cap construction (lines 145–169). Not modified |
| Prior stage report | `1d5f2b6914d57cf38ffa21096981b41a0549fcca:docs/research/body-gn-duplicate-introduction-stage.md` |
| Census | evidence `census.py` `61bdfae61aa575584e89a0895266daceed99a25cdeefbd2fb0782d32cd2f46d4`, imported unchanged. `detail.py` `f9d6cb35…` supplies Newell horizontal extras |
| Contours | `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e`, `synthetic_drawing: true`, 13 bands, no `openings` key, `schedule` length 0 |
| Blender | 5.1.2, build `ec6e62d40fa9`, built 2026-05-19 01:37:34, `--background --factory-startup --python-exit-code 1` |
| Frozen matrix | `C:/x/t_849d5b1a/matrix.json` SHA-256 `f74be99756c59bf1cd1594325f37f484a10b268a1f84425c466deb852308c2cd`. Same hash after the run |
| Probe script | `C:/x/t_849d5b1a/probe.py` SHA-256 `5b95306263979cd7a252fab02248a16cbe8e87d7252c37c3adc3c181928ab0b7` (the process that finished) |

Evidence hashes (**verified**): every line in `G:/Мой диск/AGR-evidence/t_f3e77f4a-body-gn-duplicate-stage/SHA256SUMS.txt` matches the file beside it (11 files, including `census.py`). That sums file does not list the contours. The card hash matches both `C:/x/t_f3e77f4a/in/contours.json` and `C:/x/methods/building-body/tow02/contours.json`. The working copy is `C:/x/t_849d5b1a/in/contours.json`. Its SHA-256 was the same before and after the run. Evaluations used mesh copies (`copy` → `evaluated_get` → `to_mesh` → `to_mesh_clear`). No `mesh.validate` and no `mesh.update` on those results. `vertex.co` and float32 `foreach_get` differed by 0 on the weld and boolean meshes.

Two Blender processes were started. The first exited in the node-RNA dump before any building probe; its controls match the second process. The second process evaluated the frozen matrix once. The building probes were not repeated. Raw output: `C:/x/t_849d5b1a/run2.json`, log `run2.log`.

### Frozen matrix (written and hashed before either Blender process)

1. **unchanged** — full contours, writer defaults.
2. **hole_tolerant** — full contours, only `Hole Tolerant` set true.
3. **snap_z0** — full contours, only an upper band's JSON `z0` replaced by the lower band's Extrude Mesh endpoint; height becomes `z1 - new z0`. Endpoint rule: one unit quad at z=0 with `band_h=2` chooses exactly one of two index layouts (unmoved xyz in `[0,n)` and partner in `[n,2n)`, or the swap). That layout must then match every building vertex. A band must have one endpoint z. Otherwise the probe is blocked. `float32(z0)+float32(h)` is recorded and is not the snap value.
4. **pair_6_9** — only bands whose JSON `z0` or `z1` equals 6.9, settings unchanged.

No probe combines those changes. Controls, same definitions as #746 plus one pure reverse: clean triangulated cube; that cube plus a quad cube 3 m away; triangles `(0,1,2)` and `(0,2,1)`; #746 mixed cycles `(0,1,2),(0,1,2),(2,1,0),(1,2,0)`.

### Node settings actually stored (verified)

Extrude Mesh: mode `FACES` (enum `VERTICES/EDGES/FACES`), Individual unlinked default false, Offset Scale 1. Mesh Boolean: operation `UNION`, solver `EXACT` (enum also contains `FLOAT` and `MANIFOLD`). Sockets seen: `Mesh 1` unlinked, `Mesh` linked to the weld, `Self Intersection` unlinked default true, `Hole Tolerant` unlinked default **false**. The hole-tolerant tree is the same except `Hole Tolerant` default **true**. Merge by Distance 1e-5: Selection unlinked default true, Mode menu unlinked default **All**, Distance `9.999999747378752e-06` (float32 of `1e-5`). The 0.001 merge exists in the tree and is not the boolean tap.

### Controls (verified, both processes)

| Control | polys | idx extras | same | opp |
|---|---|---|---|---|
| Clean triangulated cube | 12 | 0 | 0 | 0 |
| Two boxes, 3 m apart (12 tris + 6 quads) | 18 | 0 | 0 | 0 |
| Reversed triangle `(0,1,2)` / `(0,2,1)` | 2 | 1 | 0 | 1 |
| #746 mixed cycles | 4 | 3 | 2 | 1 |

The reversed cycle is an opposite extra, not a same-direction extra. Coordinate extras match the index extras on these controls.

### Unchanged baseline (verified)

| Stage | verts | polys | idx extras (same/opp) | coord extras (same/opp) | degenerate idx/coord |
|---|---|---|---|---|---|
| Extrude | 6,852 | 6,776 | 0 | 0 | 0/0 |
| Weld (row 7) | 7,198 | 10,126 | **0** | 1 (0/1) | 0/0 |
| Boolean (row 8) | 19,176 | 32,053 | **9,426 (1/9,425)** | 9,356 (1/9,355) | 0/489 |

Boolean horizontal extras (**verified**, `detail.py`): 9,423 horizontal, 3 vertical, 0 other, area 3,782.442. By rounded z: 6.9: 882, 10.3: 1,105, 17.1: 1,345, 20.5: 1,431, 23.9: 1,413, 27.3: 1,502, 65.4: 806, 72.2: 792, 76.25: 147. These are the #746 row-7 and row-8 figures, including the per-height extras and the area (**source claims** matched, not merely the two headline counts). `baseline_matches_746` is true. Wall time for this probe, including the extrude tap: 12.359 s. Boolean evaluation itself was 0.035 s.

### Pre-weld coordinate pair, separate from the boolean extras (verified)

One coincident-coordinate group on the weld output, and no index extras. Faces `(620, 621, 3605)` and `(620, 6714, 621)`. Vertices 3605 and 6714 are bitwise equal (`355e6f425edac943cdcc2441`): float32 `(59.84199905395508, 403.70599365234375, 10.300000190734863)`, distance 0. Neighbours 620 and 621 are one ulp higher in z, `10.30000114440918`. The identical printed coordinate is the stored float32 value, not a short print of two different values. The weld node that produced this mesh has Mode All, selection default true and unlinked, and distance about 1e-5, which is larger than 0. The two indices remained. This report does not promote that one pair into the cause of the 9,426 boolean extras.

### Interface z before and after the boolean (verified)

Flat faces: every vertex shares one float32 z. Extrude tops, weld (caps plus tops), and boolean:

| Nominal z | Weld float32 z (face count) | Residual | Boolean horizontal extras at round(z, 2) |
|---|---|---|---|
| 6.9 | `6.900000095367432` (503) | 0 | 882 |
| 10.3 | `10.300000190734863` (561) | 0 | 1,105 |
| 13.7 | `13.699999809265137` (330) and `13.700000762939453` (267) | 1 ulp, `9.5367431640625e-7` m | 0 |
| 17.1 | `17.100000381469727` (668) | 0 | 1,345 |
| 20.5 | `20.5` (697) | 0 | 1,431 |
| 23.9 | `23.899999618530273` (675) | 0 | 1,413 |
| 27.3 | `27.299999237060547` (679) | 0 | 1,502 |
| 30.7 | `30.69999885559082` (347) and `30.700000762939453` (345) | 1 ulp, `1.9073486328125e-6` m | 0 |
| 65.4 | `65.4000015258789` (314) and `65.40000915527344` (19) | 1 ulp, `7.62939453125e-6` m | 806 |
| 69.45 | `69.44999694824219` (218) and `69.45000457763672` (203) | 1 ulp, `7.62939453125e-6` m | 0 |
| 72.2 | `72.19999694824219` (263) | 0 | 792 |
| 76.25 | `76.25` (61) | 0 | 147 |

The 65.4 m split is already in the extrude output (124 faces on the lower of those two values, 17 on the higher), so that band does not have a single extrusion endpoint. At 13.7 m and 69.45 m the extrude top is the higher of the two weld values; at 30.7 m the extrude top is the lower one. The other value is the neighbouring cap, one ulp away. All four gaps are smaller than the 1e-5 weld distance. This measurement is of face planes, not of pairwise vertex distances, so it does not by itself show that a vertex on one plane was inside the weld radius of a vertex on the other.

After the boolean the same 18 float32 heights are still present. Single-height interfaces carry the opposite extras. The three fully split heights 13.7, 30.7 and 69.45 m contribute none. 65.4 m is both split and a large extra bin; the extras were not separated onto one of the two exact heights.

### Hole Tolerant only (verified)

Weld brief is identical to unchanged, including the one coordinate extra. Boolean: verts 19,176, polys **32,055** (unchanged 32,053), index extras still **9,426 (1/9,425)**, coordinate extras still 9,356 (1/9,355), coordinate-degenerate 491 (unchanged 489). Horizontal extras, area and the rounded-z bins are unchanged. The only flat-face count that differs is the lower 13.7 m plane: 756 faces instead of 754. Wall 8.272 s. Hole Tolerant does not remove the retained interfaces.

### Snap of upper `z0` (verified as blocked)

The unit quad extruded from 4 verts to 8, and neither frozen layout matched (0 of 4). Predicted `float32(0)+float32(2)` is hex `00000040`. No building endpoint was accepted. `snap_z0` did not run a boolean. No band height was changed. Changed-height list: empty, status `blocked`, reason `extrude layout unavailable or vert count is not 2x`.

### Pair at 6.9 m only (verified)

Kept band indices `[0, 1]` (JSON `z1`/`z0` equal to 6.9). Weld: 1,149 verts, 1,563 polys, 0 index extras, 0 coordinate extras. The 6.9 m plane is the same single float32 value as the full model, with the same 503 faces. Boolean: 1,729 verts, 1,669 polys, **0** index extras, **0** coordinate extras, 0 degenerate. Faces on that z become 609, still one height, with no opposite cycle extras. Wall 0.938 s. The full-model twins at 6.9 m (882 extras, 2,373 faces on that height) do not appear when the other bands are absent. Zero extras here is not a check of the exterior surface.

## How it applies to this repository

- `tools/methods/body/body_blender.py` (pinned `24c94691`, lines 72–106) is the tree that was copied: Extrude Mesh, flip, join, weld `1e-5`, Mesh Boolean UNION / EXACT / self-intersection, then the unread 0.001 merge. The boolean output is still the first stage with the 9,426 undirected extras. This diagnosis does not change that file.
- `docs/domain/areas/body.md` BODY-I (outward visible faces), BODY-J (duplicate ceiling) and BODY-N (triangulated readback) are the rules the twins touch. BODY-S is the ledge case where part of an interface is exterior. Nothing here passes or fails those rows.
- #746's open choices stay open: repair versus a new variant, which winding is kept on a real ledge, whether overlap area is measured, and whether the receipt keeps counting twinned polygons. This report does not choose them.
- Evidence outside git: `G:/Мой диск/AGR-evidence/t_f3e77f4a-body-gn-duplicate-stage/` and the scratch copy `C:/x/t_849d5b1a/` (`run2.json`, `matrix.json`, `probe.py`).

## Proposed next tasks

1. **Finish the blocked z0 snap as another report-only probe.** Scope: on a scratch copy of the same contours, give each cap face an attribute Extrude Mesh already carries to its top, read that top's float32 z, and run one boolean after setting each upper JSON `z0` from the lower band's measured top, with height recomputed as `z1 - z0`. Do this only where the lower band has a single top z; record 65.4 m if it still has two. Do not change the writer, tolerances, winding, receipts or rows, and do not treat a new extra count as a correct exterior. Value: it runs the intervention this matrix blocked, which is the remaining way to separate a float32 plane gap from the multi-band self-union. Effort **S**. Advances #727.

2. **Leave the writer change unscheduled.** Scope: no repair and no new GN variant until the user has the snap result above and has decided the four choices #746 already listed (repair versus new variant, exterior-ledge winding, overlap-area diagnostics, receipt semantics). This task does not pick those. Value: it keeps an unisolated boolean count from becoming a production edit. Effort **S**. Archive: no roadmap link.

## Open questions for the user

- Where a lower band is wider, only part of the shared plane is exterior (BODY-S). A later fix would still need you to say whether the exterior part stays, and with which normal. This run does not say.
- The 797 triangle extras #746 found only after triangulate, at 13.7 m and 69.45 m among other heights, sit on the 1 ulp splits measured here. Whether a later pass should measure overlap area, rather than cycle keys, is still your question.
- Should the receipt keep counting post-triangulate polygons that include twins? Unchanged here.
- The snap probe did not run. Do you want the attribute follow-up above, or is the blocked index rule enough to stop that line of testing?

## Verdict

**Consistent but unisolated.** Hole Tolerant is not what keeps the 9,426 extras. The 6.9 m pair does not reproduce them. A 1 ulp float32 gap is present exactly on the interfaces that do not contribute cycle extras, except 65.4 m, which is split inside its own extrusion and still has extras. The experimental snap that would have moved `z0` was blocked, so the float32 gap was observed and not isolated. Changed counts are not an exterior or normal result.

## Reproduction

```text
# matrix.json hashed before the run:
# f74be99756c59bf1cd1594325f37f484a10b268a1f84425c466deb852308c2cd
& "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" @(
  "--background", "--factory-startup", "--python-exit-code", "1",
  "--python", "C:/x/t_849d5b1a/probe.py",
  "--", "C:/x/t_849d5b1a/run2.json"
)
```

The script imports the frozen `census.py` (directed cycle, undirected cycle, extras, `QUANT=1e-6`). The tree is the pinned `_gn_tree`, with the tapped output linked to the group output, evaluated on `me.copy()`. Hole Tolerant is set only by `boo.inputs["Hole Tolerant"].default_value = True`. The 6.9 m probe keeps bands with `z0 == 6.9` or `z1 == 6.9`. The quad layout test is in `probe.py` and is what blocked the snap. Full script hash: `5b95306263979cd7a252fab02248a16cbe8e87d7252c37c3adc3c181928ab0b7`.
