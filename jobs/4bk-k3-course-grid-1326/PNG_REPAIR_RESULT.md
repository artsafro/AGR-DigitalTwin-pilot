# Independent PNG repair and exported checkpoint (#1326)

**NOT passed; no PR, replication or final delivery.** Continuation after `814da726`.
The four original staircase xView faces remain an explicit baseline [D292]; no
extra brick trimming below protected metal, no ID7 change. Prior seam permissions
and v014 Diffuse-direction acceptance remain settled; do not ask those again.

## Actual current artifacts

- Scene: `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/cut-v045/stylobate_cut_candidate_v045.blend`.
- Export: the same directory's `stylobate_pilot_v045.fbx`.
- Fresh-process export comparison: `fbx-readback.json`, `fbx-lineage-readback.json`;
  exported xView: `fbx-xview.json`.
- Native metric source is v043 `readback.json`; v045 changes only export visibility,
  and its fresh FBX readback matches every native XYZ/UV/material polygon. Do not
  substitute the earlier v043 FBX: its exporter silently omitted the hidden,
  selection-disabled wall. v044 refused the incomplete selection before saving.
- Source/native geometric replay: v042 `native-surface-comparison.json`; v043/045
  only change UVs/visibility afterward, not XYZ. This is sampled evidence, not an
  analytic Hausdorff certificate.
- Actual lit comparison: v045 `joint-normal-comparison-NOT-ACCEPTED.png`, with
  `lit-comparison-materials.json`. Same camera/light, correct DirectX-green display
  conversion, frozen source ID1 images relinked. The comparison crop deliberately
  excludes the source's missing protected-ID4 map; roof/other unused source image
  load errors are not evidence that those protected finishes were repaired.

Opening Max remains only on Artem's explicit **«открой»**; no daytime Max connection.
Own Blender 5.1.2 background was chosen to preserve his session. Sources/Bricks1
are unchanged: fresh hashes **10/10**. Binary evidence and drivers are outside git,
with seals and paths in `png-repair-checkpoint-v048.json`.

## Fresh measured table (research section 5)

| Metric | Actual measurement | Scope / status |
|---|---|---|
| Source accounting | 2,015 source identities; 771 brick, 1,244 protected | No original identity lost |
| Native output | 4,972 polygons, including 3,728 target polygons | Fresh native readback |
| FBX readback | **4,972/4,972** cyclic XYZ/UV/material matches; both objects; **0** unmatched native faces | UV max delta **0**, XYZ max **10.884011 µm**; one UV channel each |
| FBX transforms | Stair scale 1, wall scale 0.9999999404/1/0.9999999404; source wall orientation retained | Not claimed reset delivery transforms; this is a pilot export |
| Exported wall xView | **0** overlapping faces / **0** overlapping vertices / **0** bow-ties | Fresh FBX, not historical native QA |
| Exported staircase xView | Original **4** faces, **0** overlapping vertices/bow-ties | Explicit baseline [D292], **not global xView pass** |
| Target directional density | **3,792/3,792** triangles legal; **512.000304231–514.161132363 px/m** | Frozen target 512.1, no density fallback |
| p5 / p50 / p95 | **512.094296773 / 512.100007001 / 512.110141622** | Native v043 readback |
| Spread / anisotropy | `(p95-p5)/p50` **0.0000309409271**, max **1.004201523** | Within 2% / 1.02 |
| Mirrors / degenerates / invalid UV polygons | **0 / 0 / 0** | All target triangles/polygons |
| Main-wall brick vertices | 606 triangles, max **0.000119042 px** | Fixed full-repeat chart |
| Paired main-wall edges | **365 edges / 7,665 samples**, max **0.005399779 px** | Complete prior approved main-edge set; field extrapolation across joint strips, not a Normal-groove classifier |
| All brick vertices | Max **0.001136853 px** | Restored known full-repeat translations after cut-node movement; not pixel-snapped vertices |
| UDIM / margin / unique-class gap | 1001; min border **32.994030 px**; brick/joint-class gap **41.312648 px** | No scale/rotation/mirror to force fit |
| Union usage | Raw **50.169288%**, padded **52.567201%** | True geometric union, not summed boxes; no minimum-fill claim |
| Exact-endpoint UV components | **500 source / 1,291 result** | Not representative/chart counts |
| Targeted independent PNG mask repair | **62/62** source faces pass symmetric 5-mm buffered containment | Includes **4** genuinely expected-empty/observed-empty cases; not an all-face certificate |
| Expanded independent PNG comparison | **669/771 pass; 102 disagreements** | OPEN: **0.015250246 m²** missing / **0.002658919 m²** false beyond 5 mm |
| Surface replay | All **2,015** originals, both directions, 28 barycentric samples/triangle; worst **11.138959 µm** | No sample >20 µm; protected worst **9.501320 µm** |
| Protected finishes | **1,170 exact**, **74 boundary subdivisions** | Original corners/finish retained; subdivisions **not byte-identical** |
| Normal appearance | Candidate joint field `[128,128,255]`; source joint pixels have **3,871** RGB values | **NOT source groove/bevel equivalence**; actual lit comparison now exposes the difference |

The chosen joint convention is still an owner-side **10-mm** band, intended
centre **5 mm** inward. At clipped/junction samples compare complete intervals,
not an outside-face nominal centre. The old v020 **651/31,899** carrier receipt
is historical: **12** paths have owners in the changed 62-face set. Do not copy
its green total into a final v045 receipt without rerunning the correct oracle.
The old self-mask and constant D/ERM/N field checks also do not prove source
Normal equivalence or close the expanded PNG gate.

## What was repaired and what failed

1. Nominal axis rectangles represented only 58/62 independently traced interior
   PNG shapes. Source-end taper, not merely strip width, caused four rejections.
   New `vectorize_joint_footprint` groups nearby raster fragments, uses bounded
   hull simplification, anchors near tips to **unchanged** source corners before
   topology, and enforces both directions of the unchanged 5-mm source bound.
2. v027 fit 62/62 in planning, but native readback found 84 close vertices and two
   triangulation failures. After-the-fact coalescence (v032) cleared close nodes
   but created 13 wall overlap faces and five inverted low-cap cells. v034–039
   diagnostic repartition attempts were rejected, not promoted.
3. v040 removes obsolete protected boundary subdivisions before re-noding, uses
   the source-corner-anchored taper, and has zero wall face overlaps / five close
   node pairs. v041 coalesces **five explicit new-cut-only groups**, max movement
   **0.979033 mm**, reports **10** collapsed connectivity cells, no source lost.
   Original vertices do not move; original protected corners/materials remain.
4. v042 encodes every native triangle inside legal density bounds. A fresh phase
   probe then caught inherited pre-motion UV anchors shifting several minor
   triangles by **0.502162 px**. `restore_repeat_translation` recovers only the
   known full-repeat chart translation (refuses >1-px unknown class); v043 lowers
   all-brick phase to **0.001137 px**, without scale/rotation/vertex snapping.
5. v043 first FBX contained only the staircase. Fresh-process readback caught
   **504/4,972**, not success. v044 asserted incomplete selection and saved nothing.
   v045 explicitly enables target visibility/selection; both exported meshes
   independently match **4,972/4,972**; exported wall xView stays clean.

## Expanded source-mask findings: still in this card

The new all-face bitmap probe finds 102 differences: seven staircase faces, 27
low parts, 56 caps and twelve **50-mm floor bands**. The latter are vertical but
are not full-height main-wall panels: source IDs 60, 62, 66, 104, 168, 170, 172,
176, 178, 180, 214, 218. No full-height main-wall course failure was found.
Do not hide this behind the green 62-face interior subset.

`cut-v047/partitions.json` is an **unapplied** bounded plan for 98/102; no scene or
UVs were saved from it. Four refusals are stair source faces **458,462,493,499**:
nominal 30-mm thin ends, legacy PNG dark traces only about 0.8 mm wide on average,
with broad/diagonal raster bounding boxes. Original recovered units record no
carried/interior joint there. A semantic classifier must distinguish these legacy
raster traces from required 10-mm architectural panel joints; a raw colour marker
is not automatically an approved new geometry-cut path. Bricks1 itself has **0**
of the 16,777,216 source pixels matching this joint marker, so this is not a
simple brick-mortar false-positive explanation. Do not silently waive, delete,
or cut these witnesses merely to make the full-PNG oracle pass.

## Material target needing an explicit answer

The accepted v014 sheet was **unlit Diffuse-only**. It cannot establish that the
original panel-groove Normal may be flattened. Actual grazing-light v045 shows a
flat dark band; the frozen delivered source shows a bevel/groove. The old constant
joint field made stacking equivalent only to itself, **not to that source Normal**.
The generated source Bricks1 maps remain unchanged in either case.

**Question:** for the main-wall 10-mm panel joints, is a neutral/flat joint Normal
an accepted pilot target, or must the source groove/bevel Normal be restored?
Recommendation: restore the source groove/bevel, not silently treat Diffuse-only
approval as an all-map waiver. This is a finish/appearance target, not a request
to reopen seam ownership, cuts, density, one-tile budget or the staircase baseline.
The answer does **not** waive the 102 source-mask findings, final all-map interval
measurements, final image, reusable-driver publication or author/CI receipts.

## Verification and continuation

Tests-first commits: `2bc6af28` (missing taper API), `89216b9f` (immutable anchor),
`997e4e46` (source-corner raster tip), `739d229a` (stale cut-node phase).
Latest affected command is the previous report's affected list plus
`tests/test_course_grid_joint_tapers.py`, basetemp
`C:/x/t_d517d7c6-affected-green-v045`: **221 passed / 1 deselected / 0 failed**,
21.95 s. The initial D292-only failure was fixed by its required area-sheet anchor,
not a test exemption. New generated taper/phase probe: **100/100**, seed **1326**;
NaN/inf/partial/boolean, broad/outside joint and unknown-phase cases reject.

No full suite/evals/PR/review: acceptance remains incomplete. After the material
answer, finish the in-scope mask semantics/remaining geometry repairs and all-map
readback. Correct DirectX-green display conversion is needed in Blender preview
(the v045 comparison adds it in memory; the saved scene still has the earlier
preview connection). Preserve artifact versions; use v049+ for new production.
Then final picture/metrics, merge current main (no rebase), recheck D293/D292,
full suite **once through suite_slot.py**, eval receipt and path/invariant hostile
probes, push, one PR, and dt-reviewer. No global delivery QA pass is implied.
