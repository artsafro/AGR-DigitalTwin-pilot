# Authorized cut experiment — actual textured v014 candidate (#1326)

**Status: NOT technically passed; visual direction pending. No replication.**
This is a working scene on a separate copy, not final delivery, a Max acceptance
scene, a completed FBX export, or a request to waive any red numerical gate.
Artem's new-cut permission is in `geometry-cut-approval.json`; earlier seam,
cohort and opening questions remain settled. Initial pilot contract: [D275].

## Actual result

- Scene: `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/cut-v014/stylobate_cut_candidate_v014.blend`.
- Four actual textured close-ups (straight wall, corner, floor join, niche):
  `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/cut-v014/textured-candidate-sheet.png`.
  These are **unlit Diffuse-only** views, not a Normal/ERM/shading acceptance.
  A real 480x351 preview is attached to card t_d517d7c6, attachment 19; exact-byte
  SHA256 `0d2a8af2e16ac77e7fbb5948e0201f76618c126f559409f4a1dd4b0930b9ddcc`.
- Compact metrics/hashes/continuation: `cut-result-v014.json`.
- Drive `SHA256SUMS.txt`: **129/129 files verified**, including raw readbacks,
  before/after QA, script snapshots and the recovered original carrier/mask data
  (copied before the historical scratch can be pruned). No binaries enter git.

Blender 5.1.2 background was chosen to keep daytime Max untouched. Original scenes,
accepted delivery and Bricks1 maps remain hash-identical (**10/10**). There is no
extra tile, geometry replication, density reduction or change to other finishes.
The active material's new joint Normal field is neutral; historical groove normals
are **not preserved** and are not being passed as equivalent.

## Cut / representation manifest

The operation separates the approved 10-mm joint footprints from the common brick
field, rather than trying to overwrite incompatible joint masks in one atlas pixel.
Convention: joint fully inside its owner, intended centre **5 mm inward**.

- All **2,015 source face identities**, including **771 ID1** inputs, remain traced.
- **1,244 protected faces** retain exact XYZ, original loop indices, UV and material
  assignments in the saved/reopened scene. Final selected mesh inventory: **3,202
  polygons**, of which **1,958** are brick/joint output pieces.
- **631 source faces** have ideal joint-zone cuts; the pre-native partition records
  **1,012 boundary segments**. These are not the final edge count.
- Complete **saved-result** new-edge inventory, with XYZ endpoints, source/output
  faces, incident-face count and role:
  `cut-v014/all-new-edge-locations.json`: **1,027 joint-boundary segments**, **2,840
  source-boundary subdivisions**, **679 connectivity-or-unmatched internal edges**.
  It deliberately includes unresolved edges rather than calling every edge a valid
  cut. Its SHA256 is in the compact report and external seal.
- Hole connectivity is explicitly tessellated; convex quads are retained only when
  both native diagonals are nonsingular. Near-collinear corner removal records a
  **20 micrometre native-corner bound**, retained XYZ and area delta per piece.
  This is not a global surface certificate; source-to-result surface QA remains due.
- Nominal density was frozen at **512.1 px/m**, an inward native-storage/legal-bound
  guard over the compact source target 512, not a fit-scale search. Brick physical
  repeat stays exactly `48 * 3.15 / 38`; the Bricks1 input bitmaps are unchanged.
- **37 low-plinth triangles**, all on original faces whose maximum Z <= 0.25001 m,
  receive explicit rigid native charts under the standing minor-part seam rule.
  Float32 encoding chooses at most two adjacent representable values, not integer
  pixels or an automatic density scale; maximum encoding error **0.000203415 px**.
  Every change is listed in `rectification.json`; main-wall UVs are not rectified.
  The constant joint field moves upward by one pixel to retain a measured border.

## Fresh section-5 measurements, not historical receipts

| Metric | Measured result | Gate |
|---|---|---|
| Directional density on native tessellation | **3,616/3,616** triangles in 512–1706; min **512.001075834**, max **519.174393104 px/m** | Passing measured band |
| Spread / anisotropy | `(p95-p5)/p50` = **0.003039537%**; max **1.013953826** | Passing measured targets |
| Main-wall brick phase | **546** main-wall triangles; vertex max **0.000118475 px**; **365** main continuous source edges / **7,665** paired samples, max **0.005426309 px** | Passing sampled main-wall result; not all-map full delivery certification |
| Other brick phase | All triangle-vertex max **0.000838897 px** against fixed source chart | Measured; minor seams listed separately |
| UV domain / unique-image separation | All target UVs inside 1001; zero mirrors, degenerates or invalid UV polygons; brick/joint gap **41.309667 px**, minimum border >32 px | Passing measured candidate domain |
| Occupied union / padded union | **50.169482466% / 52.553834512%**, native triangle union, 16 px per-side buffers | Measured usage, no minimum-fill claim |
| UV islands | Exact shared-endpoint component definition: **500 source / 1,251 result** | Measured, not logical chart or representative counts |
| Joint-field maps | Actual PNG bytes: **798/798** joint polygons' bboxes inside the configured constant field for each of D/ERM/N | Field-content check only, NOT a groove/false-joint classifier |
| Joint centre / width / coverage | **651/651** source carrier paths paired, **31,899** finite samples; raw probe has **44 missing**, apparent centres up to **15 mm**, widths **5.205–40 mm** | **NOT passed**: intersecting joint footprints/junctions are unresolved; do not relabel these as clean 10-mm centre receipts. 42 interior-mask units retain old 5-mm-grid uncertainty |
| xView, source -> result | Stair: existing 4 overlapping faces unchanged. Wall: **0 -> 516 overlapping faces**. Result total **520 faces, 2,297 overlapping vertices, 167 bow-ties** | **FAIL — new cut topology must be repaired** |
| Visual verdict / export | Actual result sheet and reopened Blender copy exist; Artem verdict, final FBX/Max copy/readback absent | Open; no replication |

The xView failure is inside this card's cut scope and is **not** filed as an
out-of-scope issue, waived, or hidden behind green density. Initial diagnosis:
749 used-vertex pairs within 2 mm in raw saved geometry; **735 <=20 micrometres**,
731 original/new pairs. Native xView also counts split fans. Next repair should
canonicalize only proven source-vertex duplicates and conform split edges, not
blindly weld all 2-mm pairs or alter accepted source/delivery files. Fourteen
larger close pairs still need individual evidence. Protected boundary loop changes,
if required for conforming, must be reported rather than claimed bit-identical.

## Repair evidence and tests

- Cut API RED **b461172c** -> exact strip GREEN; subsequent witnesses include empty
  geometry, closed interior zones/source fans, picometre overlay fragments, and a
  geometry collection whose boundary is None.
- First real v006/v007 partitions refused 62/45 faces; v008 accounted for all 771.
  Native v008 then exposed 184 invalid polygons / 187 degenerate triangles.
- Full edge strips before clipping removed endpoint spurs. v010: zero invalid
  polygons, two degenerates and one mirror. Native constrained cells plus rejecting
  singular quad fans give v013 zero of all three, but 37 density failures.
- Rigid plinth charts + bounded directed float32 encoding give v014 the fully
  measured legal band above. A deliberately unrepresentable skinny synthetic
  triangle remains an error; its failure was not repaired by relaxing thresholds.
- Affected suite: **185 passed / 1 deselected / 0 failed** (exact command in JSON).
  Final helper-only confirmation after documentation/type cleanup: **20 passed**.
- No full suite, eval receipt, PR or review request yet: task acceptance is incomplete.
  Run the full suite once through suite_slot.py only before the first actual review.

## Visual direction question / continuation

**Artem: does this actual candidate's visual direction (courses, panel-joint
placement, corner and niche appearance) match what you want?** This asks for the
mandatory picture verdict only; it does not ask you to approve the red topology,
waive joint metrics, increase the tile budget, or decide another minor seam.
Opening remains only after **«открой»**, never an automatic daytime Max switch.

After the visual direction: repair cut topology and junction-aware joint coverage,
certify surface and all-map correspondence, prepare/read back a final FBX/Max copy,
then run one full suite/evals/hostile probes, merge current main without rebasing,
recheck D275, push and open the one #1326 PR for dt-reviewer. Do not reproduce the
current candidate across the building or describe it as technically accepted.
