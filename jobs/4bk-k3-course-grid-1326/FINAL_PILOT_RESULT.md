# #1326 — scoped pilot readback and reusable finalization

**Two tiles by Artem's later approval [D304], not an unapproved one-tile fallback.**
**No replication or final 4BK delivery. No global `passed=true`.**

This supersedes the open technical continuation in the historical v166
[checkpoint](NUMERICAL_REPAIR_RESULT.md), not its immutable evidence. The current
artifact is `normal-v192/course_grid_finalized_QA_OPEN.blend` and its fresh FBX.
All relative external paths below start at
`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/`.

## Contract and answered permissions

- Scenario `oks-vpm`, check level `full`; first stylobate brick only. Tower brick,
  ID2 metal and final 4BK delivery remain outside this card [D309].
- Original sources are the frozen `job/4bk-k3-vpm` checkout at `06546d3d` and the
  delivered `K3_assembly_v006`/maps named in `intake.json`. They stay read-only.
- `faces.json` is the hash-bound, 2,015-face finish manifest. Artem explicitly
  selected **771 ID1 faces** (705 walls +66 stairs), protecting 1,244 ID4/ID7/ID10
  faces (`finish-approval.json`). The issue's generic ID2/ID3 vocabulary is not
  permission to renumber the actual delivered materials.
- Nominal colour joint: **10mm wholly inside the owning panel, centre5mm inward**.
  Keep original clipped endpoints/junctions, 38 courses/3.15m, Bricks1 bytes and
  frozen512.1px/m construction scale. Native/legal directional bounds win.
- Original Normal relief [D295], minimal planar outer-bevel support cuts [D303],
  and two sequential tiles1001/1002 [D304] are answered. No further cuts, extra
  tile, packing rotation, reflection, density fallback or protected trim was made.
- v096 Normal/joint/course direction [D310] and v160 thin colour cores [D317]
  are accepted separately. Keep both; neither is a global technical-QA waiver.
- Blender5.1.2 background is used because Max is Artem's during the day [D255].
  Opening remains only on «открой»; no live Max/Blender scene was touched.

## Current artifacts and independent readback

| Artifact | Path |
|---|---|
| Final native pilot, before review cameras | `normal-v192/course_grid_finalized_QA_OPEN.blend` |
| Exported working FBX | `normal-v192/course_grid_finalized_QA_OPEN.fbx` |
| Fresh native and clean FBX readback | `normal-v192/{readback,fbx-readback,fbx-lineage-readback,xview}.json` |
| Six actual linked4096PNG maps | `normal-v157/T_1326_Stylo_{Diffuse,ERM,Normal}.{1001,1002}.png` |
| Executed reusable bake replay | `normal-v180/T_CourseGrid_{Diffuse,ERM,Normal}.{1001,1002}.png` — **6/6 byte-identical** |
| Review scene, same geometry/maps plus cameras/light | `normal-v197/stylobate_final_review_v197.blend` |
| Four actual source/candidate lit pairs | `normal-v197/final-source-vs-candidate-four-views.png` |
| Frozen inputs/drivers/code/probe seals | versioned `normal-v167+`; final seal/checkpoint linked in `pilot-readback-v206.json` |

The finalizer initially exercised explicit fixed-node diagonals (v169/v183).
The **selected** final candidate instead uses **cyclic anchors only** on source
ID4 faces715/725/729: every directed boundary edge, polygon, XYZ, material and
vertex/UV association remains identical. No protected diagonal is added. Fresh
comparison proves **6,393/6,393 exact cyclic associations**, including all1,244
protected polygons. Native metadata readback v203 proves no custom normals,
edge seams or smooth-face changes were lost. The generic adapter now refuses
unsupported shading/attributes before mutation instead of silently dropping them.

The hardened adapter replay in v204 also matches the v192 imported dataset
**exactly on all6,393 records**, including every triangle/UV/material/source
association. A real Blender unsupported-attribute probe on a synthetic copied
scene (v205) refuses before output creation; both its input and the original
source remain unchanged.

## Research section5 — freshly measured on the final export

| Metric | Final measured value | Target / boundary |
|---|---|---|
| Original source identities / brick source faces | **2,015/2,015;771/771** | no missing face/finish |
| FBX native association | **6,393/6,393**,2meshes,1UV channel; UVdelta0; maxXYZ9.005µm | narrow import/association check, not delivery acceptance |
| Course/full-bond phase | maxall-brick **0.010218px**; main **0.005497px** | <=0.1px |
| Approved main-wall common edges | **365edges/7,665samples**,0missing; max **0.010631px** | <=0.1px |
| Directional density | **5,149/5,149 legal**, min **512.002938**, max **516.402080px/m** | every measured direction512–1706 |
| Density spread `(p95-p5)/p50` | **0.0000403117841**, i.e.0.00403117841% | <=2% |
| Max anisotropy / mirrors / degenerates | **1.008575737 /0 /0** | <=1.02; no mirror/degenerate |
| Actual per-face PNG positive/negative correspondence | **771/771**,0missing/false/piece refusals beyond5mm | complete face footprints, not only sparse centres |
| Local source-positive panel-joint probes | **31,837/31,837**, maxcentre **1.706348mm**, maxendpoint **3.412696mm** | <=5mm; every required positive probe retained |
| Source-empty clipped endpoint rays | **62 explicitly retained**:36both-empty negatives,26accepted source-cell tapers; max displacement **1.940609mm**,0beyond5mm | no fictitious centre/10mm strip is invented where the source has none; see below |
| Unique sampled / padded union1001 | **58.497058% /87.188895%**,236classes including shared brick | actual polygon union, not sum of stacked faces |
| Unique sampled / padded union1002 | **11.569224% /50.779407%**,516classes | no minimum-fill acceptance invented |
| True unique-class gap1001/1002 | **33.872931 /34.880765px** | >=32px at4096 |
| Tile border1001/1002 | **32.813274 /49.984375px** | measured nonzero margin |
| Topological UV components before/after | **500 /2,819**, edge-UV tolerance1e-7 | not logical group/representative count |
| Continuous source/export surface certificate | **2,015/2,015**,0uncovered/refused; conservative bound **19.197867µm** | existing20µm storage/readback envelope |
| New wall xView findings | **0contacts/0vertices/0area pairs/0bow-ties** | all three v160 area-only pairs repaired |
| Stair xView | raw6faces/4pairs; only approved original source pairs(73,467),(297,466), zero-based | explicit baseline[D296]; raw checker **FAIL remains** |

Evidence: `normal-v193/metrics.json`, `normal-v194/continuous-surface-bound.json`,
`normal-v195/phase.json`, `normal-v196/independent-all-faces-png-check.json`,
`normal-v188/local-carriers.json`, and
`normal-v198/source-endpoint-and-relief-readback.json`.
All raw producers keep their nonpassing aggregate flags; this table does not edit
those receipts into a global pass.

### Joint interval diagnosis is not a threshold waiver

The first full-face ray check also intersected unrelated opposite-edge joints
metres away. GEOS split connected1D intervals at touching raster-cell corners;
RED99c4c0b6 now regresses the measured1D union, while a real2mm gap still fails.
One exact ray landed in a ~1e-14m affine chart seam. REDe6845372 adds **explicit
0.1nm measurement-only snap rounding**, not a mesh/UV/PNG change and not a wider
5mm gate; max observed symmetric area change2.922e-10m² is recorded. Rounded-WKT
cache replay v187 was refused; v188 rebuilds from PNG bytes and stores exact WKB.

The complete schedule remains651carriers/31,899rays. **62rays have no source
colour interval** at the clipped/tapered endpoint, not a missing fabricated input
or a silently dropped check. Their centre is explicitly `null`.36also have no
output core;26have the already accepted v160 conservative colour-cell taper
[D317], all <=1.940609mm from the actual source endpoint. All31,837source-positive
rays pass, and all771complete source-face positive/negative masks pass separately.
The historical strict66red report is retained in v181, not rewritten.

## All-map / Normal / mips

- Across both saved4096maps, **6,596,755 Diffuse-core pixels** have **0ERM
  mismatches** (<=1RGB);0nonfinite or nonpositive-Z Normal pixels. v189 decodes the
  real maps and30diagnostic mip files, not a generated response substituted for
  missing DCC output.
- Direct frozen source Normal bytes -> classified signed relief -> decoded unit
  direction: **92,228active pixels**, maxerror **7.8682e-8** (v198). Baseline-equal
  quantized pixels are separate, not manufactured bevels;158one-byte residuals
  outside measured bevel remain unclassified, not new cut authority.
- Independent source-frame raster diagnostic covers771sources/13,268,325samples.
  Corrected raw-source masking removes false interior findings: maxinterior
  direction difference1.516551degrees,0above the diagnostic3degree marker.
  That marker is **not an accepted tolerance**. Three large boundary numbers came
  from forced representative pixels outside a subpixel staircase triangle, not
  valid inside-face pixel-centre samples; they remain explicitly invalid sampling
  evidence in v178 rather than being called a Normal pass. Frozen-field recovery,
  actual accepted lit views and six-map replay are separate evidence.
- Declared **BOX mips + bilinear** footprint:16px dilation minus raster/native
  guard leaves15.281893px. Levels0–3 reach<=12px and retain the declared guard.
  Level4 reaches24px and is **not certified**. The30decoded mip0–4 images are
  diagnostics; no arbitrary engine anisotropic-filter/distance guarantee or mip4
  production acceptance is claimed. Final full-delivery filter policy is outside
  this pilot, not a reason to lower density or silently add padding/tile budget.
- The generic green-ERM segmentation trial v181 is **invalid as a joint oracle**:
  ordinary source brick shares that RGB. Its red counts are retained. Numerical
  D-core/ERM coherence and source-bound Normal recovery replace that invalid
  classifier; the actual ERM map was not recoloured to satisfy it.

## Reusable execution and verification

See [REUSABLE.md](REUSABLE.md). The existing page-plan CLI plus new
`course_grid_bake.py` and `tools/blender/course_grid_finalize.py` actually executed,
not stubs. No new public `agr unwrap-atlas` flag or shared capability is claimed;
#1296 owns that integration. The selected finalizer is topology-preserving cyclic
serialization; the optional triangulation method remains explicit and tested.

Tests-first commits this continuation: a80687bf(native sliver),2f5ebb7c(bake CLI),
99c4c0b6(interval union),67a62c0c(explicit finalization),e6845372(measurement union),
aac90781(cyclic anchor),56033625(unsupported metadata). Hostile probes also exposed
boolean source IDs and duplicated bake inputs before fixing them.

Synthetic seed1326 probe: **500/500 cyclic-preservation cases and12/12 invalid
coordinate refusals** (v202); prior source-cell600case independent intersection
probe remains tested. A real fresh-process timing attack changes only an
agent-owned reference COPY after tile1001: CLI exits2, emits no successful report,
and retains6partial PNGs explicitly as **not a model** (v200/v201). Original
reference bytes remain unchanged. Original architectural source hashes remain10/10.

Affected tests and exact-head counts are in the final PR/handoff. Full suite:
**deferred to merge batch (rule68)**. CI: not run (billing lock).

## Status separation and remaining boundary

This is the authorized two-tile **pilot artifact + reusable scripts**, ready for
independent code/evidence review, not a final4BK package. Artem's two material
visual stages are answered[D310,D317]; do not ask them again or replicate.
The raw source-stair xView baseline[D296] and absent final delivery/SINTEZ package
checks prohibit a global `passed=true`. Mip4/arbitrary engine filters and final
publication are not certified. Reviewer approval is still required; no merge or
publication was performed by the worker.
