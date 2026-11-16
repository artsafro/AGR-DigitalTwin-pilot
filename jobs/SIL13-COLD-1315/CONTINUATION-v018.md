# #1315 — paired Sand/Bike/Urn repair and actual UCX coverage, v018

**`passed=false`; cells `ground-npm` / `ground-vpm`.** Continuation of our own
`cdcd9aad`/v017, not a second independent cold run or a readiness gain. **No new
question to Artem.** D321/6903084291 form acceptance and the earlier composition,
hedge, Bench025 and NPM Table gates stay CLOSED. No decision ID was added.

## Adopted — 16 library-copy instances in each profile

Using the existing D305/D316 source-bound constructive-repair authority:

|Type|Instances per profile|NPM triangles each|VPM triangles each|Construction controls|
|---|---:|---:|---:|---|
|Sand002|6|1728|5332|38 actual source-circle post assignments; all lower/upper height probes pass; low post not raised|
|Bysicle007|8|870|870|Actual bent-frame profiles and foot rails;45/45 wheel-slot probes empty|
|Urn010|2|158|158|Internal cavity empty and actual100mm shelf present; measured357nm duplicate seam removed|

The Bike900triangle pre/raw candidate was **not** native-clean: native import
reported4faces at rail joints. Topology-preserving10um finishing yields870faces;
all actual isolated pre/raw/native checks then give0faces/0vertices/0bowties/0area.
The original failing FBX/report is preserved. Urn repair starts from the preferred
source-fixed shelf/cavity variant, never the earlier clean-but-filled candidate.
Sand NPM is a topology-preserving5mm LOD of the same repaired source copy, not a
substitution or a loss of posts/instances. Heavier1606/1216triangle alternatives
were measured but not adopted;1728 preserves more of the VPM construction.

**Actual paired site exports:** `v018/site-three-r1/{NPM,VPM}/SM_SIL13_Ground.fbx`
in `G:/Мой диск/AGR-evidence/1315-cold-silikatny/`.

- NPM **178571raw /178556native** render triangles; remaining15native face loss
  belongs to unchanged types, not the16repaired copies.
- VPM **301662raw /301662native**, no native face loss.
- **64 actual placed-instance checks** (16instances ×2profiles ×raw/native)
  are clean0faces/0vertices/0bowties/0area. IDs/points/rotations/heights retained;
  independent actual-export placement differences below10um.
- **22otherMAF in each profile are exact**, including all accepted Tables and
  Bench025. Ground/Flora and all600VPMUCX actual arrays are exact against the
  respective v015NPM/v017VPM inputs. All38MAF/4582plant census retained.
- UV/material on repaired copies is explicitly provisional; existing one candidate
  material retained, not a finished512atlas or VPMtexture result.

Seeded source-surface diagnostics use explicit `sample_surface(seed=1315/1316)`:
10000points in each direction, **NOT exact Hausdorff**. `np.random.seed` alone does
not control current trimesh sampling; earlier unseeded diagnostic files remain
historical and are superseded by `source-controls-seeded-r2.json`. Sand's roughly
104mm source-to-union maximum consists of buried interfaces inside genuine joins;
source EXTERIOR maxima are0.000000074m VPM/0.001196005m NPM. Candidate-to-source
maxima are about6.503/6.381mm. Bike measured maxima3.765/3.536mm; Urn outside-source
maximum1.144mm and candidate-to-source approximately10.001mm from restored walls.
All original sources, libraries, maps and prior resume exports rehash unchanged.

## UCX — complete actual model-to-collision bound, no geometry edit

Independent readback audit now covers **every one of57226actual Ground top
triangles**, including their perimeter. It does not reuse the builder's own
`max_vertical_dev` or substitute a point-sampling result for coverage.

-600actual closed consistently wound positive-volume pieces,1119actual upward
  UCXtriangles. No MAF/Flora/lighting collider and no NPMUCX introduced.
- Each Ground triangle is exhaustively partitioned by projections of actual UCX
  triangles. Lift polygon vertices onto that Ground triangle. Distance to ONE
  fixed actual target triangle is convex, so the vertex maximum conservatively
  bounds the entire polygon; assigning any such triangle bounds distance to union.
-450783partition vertices,0unassignedregions,0degenerate projected faces;
  all57226faces partitioned. Maximum per-face area reconciliation error
  **2.0650148258027912e-14m2**; aggregate layered surface area15872.911976507741m2
  (not the9568.79964m2plot footprint).
- Numerical conservative upper bound **0.08993564479232127m <0.1m [D134]**.
  This is not exact Hausdorff and not a wholeUCX/finalSINTEZ pass.

Failed diagnostics are retained: strict ideal-convex volume equality refused the
float32 input, so the final method uses ACTUAL triangles, not ideal hulls. The first
nearest-centroid ownership gives a valid but loose3.16m bound. An8mm gap partition
left3652tiny regions unassigned; a50mm partition plus residual assignment still
picked far overlapping facets. Adaptive complete polygon subdivision and actual3D
owner selection resolves those bounds without dropping an area or changing a
checker tolerance. Final90mm construction target leaves numerical margin below
the100mm rule.40seeded convex-distance oracles and5real-receipt controls pass.
**213wide-neighbour gap findings remain open**; no gap exemption is inferred from
this independent one-sided coverage result. Rerun coverage if Ground/UCX changes.

## Other types — isolated, not adopted

**Bench013:** the earlier projected slab loses rounded source structure; the
source-solid/MeshFix/3Dframe-joint route is raw/native xView-clean3600triangles but
silently loses a frame-bottom section: source-to-candidate148.463mm, REJECTED.
One-sided candidate-to-source distance below5mm did not establish fidelity.

The source-boundary route retains the full original frame using2mm surface voxels
and local closure, genuine3.2mm frame embeds, and conformal slat endplanes. Four
fastener components are explicitly accounted as D165drop reasons, not called wood
slats. Large side holes and source exterior checks pass. Six generated collinear
Boolean triangles are retriangulated by surface-preserving edge flips, never
passed through a relaxed zero-area guard. Bounded link/midpoint contraction retains
all original assignment bounds;33generated safety/invalid-input controls pass.
A degree3generated cone is capped without moving surviving vertices; volume change
−7.297287080154646e-11m3. Pre-export5064triangle topology is clean.

**Do not adopt it:** exact2mm voxel edges quantize below2mm on actual FBX export.
Direct20um guard fixes one edge but shortens its neighbour; coupled42pair guard
moves83generated vertices by at most31.605um and removes near vertices, but leaves
**1area-only pair** in actual raw AND native readbacks.0contactfaces/0vertices is
not a pass. Two-way10000point source probes and real side-hole controls pass;
pairedNPMbudget and placed native QA are still missing. Preferred isolated data:
`bench-boundary-export-r3`, not the clean-but-missing MeshFix route.

**Canopy006:** source-profile fine union still fails2070faces/532nearvertices.
Link helper correctly refuses zero-area Boolean needles; uncontracted diagnostic
was retained, not promoted. Original placed canopy remains unchanged. Continue
actual roof/tube/platform profile and thin-joint repair, not a blanket hull or
filled lattice/seat openings.

## Whole-site/per-area result — still FAIL

|Area|Actual result|Open value / limit / owner|
|---|---|---|
|Ground|Actual surface arrays unchanged; earlier correctly filtered footprint remains applicable by exact-array proof|Public skirt broken-face result, details/maps/UV/UDIM/density and footprint-hole reference:worker; old1.001m builder self-report is not a validator pass|
|MAF|16paired copies adopted;64placed checks clean;22otherMAF/profile exact|NPM native15face loss; Bench013final area-only1 and pairedLOD; Canopy profile failures:worker|
|Flora|4582census/arrays unchanged; prior accepted hedge support applies only to unchanged arrays|46Flora/Flora pairs plus mixed Ground/Canopy contacts, map/grey/interim restoration:worker/source|
|UCX|Complete actual Ground-to-UCX conservative bound0.089936m,600pieces retained|213wide neighbour-gap findings and remaining finalUCX checks:worker|
|Delivery|Fresh exported FBXs/public native validators actually exercised|NPM1pass4fail1review2not_run; VPM3pass3fail1review5not_run; final user visual/material and completeSINTEZ only AFTER technical fixes|

Whole actual public xView: NPM **728faces/114vertices/165bowties**, VPM
**4794faces/0vertices/162bowties** (formerly14191faces in VPM). Ownership report
preserves all mixed pairs: in particular10Ground/Urn,100Ground/Canopy contacts,
3Ground/Flora contacts,46Flora/Flora pairs and96Bike/Canopy contacts. Pair counts
are not unique-face counts and are not exceptions. Missing22MAFrows, Abies1,
RedSunset4 and133m2flowerbed rate remain explicit, never invented.
Historical#906/#969/#1178 comparison remains in v009; no new cold-context claim.

## Verification and resume

Affected checkpoint controls: **427passed/5historical controls deselected**;
exact command in `source-wide-summary-v018.json`. Separate CURRENT unresolved
controls: **2failed/6passed** (unchanged NPM15face loss, isolated Bench1area pair).
Separate HISTORICAL artifact controls: **7failed/32deselected**, including the5old
artifacts plus rejected slab and loose firstUCXbound. Failures are not hidden in
the green claim. Real nativeBike regression, missing-frame source regression and
actual float32 edge regressions/failures are retained.

**Full suite: deferred to merge batch (rule 68).** No shared module, checker,
registry or library edited;65new job-local drivers/adapters/tests,1273literal code
lines in the external seal, tool-call total unmeasured.347immutable evidence files,
148336598bytes;22original/resume hashes unchanged. Technical QA, acceptance and
publication remain distinct. No PR/review request while acceptance is incomplete.

**Resume BOTH profiles from v018/site-three-r1.** Earlier accepted Tables/Bench025/
hedges stay untouched. Do not adopt isolated Bench/Canopy on a partial clean counter.
The remaining repairs are worker-owned; no new human/model question is pending.
