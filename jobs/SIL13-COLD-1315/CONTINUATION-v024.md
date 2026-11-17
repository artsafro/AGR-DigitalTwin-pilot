# #1315 — buried Bike bases and NEW canopy identity question, v024

**`passed=false`; cells `ground-npm` / `ground-vpm`.** Continuation of our own
`7b2982eb`/v023, not a new cold-agent/readiness gain. No PR/review request:
acceptance incomplete. **New model/data question, not a technical-QA waiver:**
[#1315 comment6943077043](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6943077043).

## Current resume artifacts, NOT deliveries

Both profiles: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v024/site-bases-r1/<NPM|VPM>/SM_SIL13_Ground.fbx`.
Actual **179576 NPM / 305706 VPM raw=native** render triangles, no native face loss.
All38MAF and4582plant census entries/points/rotations retained. **Canopy006 has NOT
been removed/replaced**; changing the physical count to37 is only a question.
Exact export hashes, commands and report paths: `source-wide-summary-v024.json`.

## Adopted: D095 removal of completely buried horizontal Bike bases

The108public xView Bike–Canopy pairs in v023 lie on horizontal base faces of
`33FB3B4/33FB3B5/33FB3B6`. Remove ONLY50fully buried horizontal faces per rack,
150per profile, not an instance, vertex, visible structural element or library file.
Every removed actual raw/native triangle is completely partitioned against actual
upward Ground triangles; affine height extrema prove minimum burial **80.662710mm
NPM /83.156370mm VPM**, including all material layers. No five-ray shortcut.

Actual raw/native comparison against matching predecessor readbacks proves:
- ALL vertices EXACT, ALL retained triangles EXACT; complete removed-face lists.
- Ground/Flora/564UCX arrays unchanged; all38MAF/4582plants remain.
- Fresh raw-FBX UV channels, material inventory and retained per-face UV/material
  assignments EXACT, including all565VPMobjects. No new appearance invented.
- Three placed racks per profile, raw AND native: **12actual placed checks clean**.
- NPM original part scope: **0faces/0vertices/0bowties/0pairs**, but additional
  diagnostic joined scope still **26faces/26pairsFAIL** (Flora–Canopy).
- VPM original and diagnostic-join scopes: **38faces/81pairsFAIL**,0vertices/0bowties.
  All81pairs mapped:3Ground–Flora,46Flora–Flora,32Flora–Canopy; no Bike xView pairs.

**This is NOT complete MAF or whole-scene QA.** The regulatory checker measures
transverse crossings that parallel/contact xView does not establish.

## New model/data boundary: source bicycle shelter versus seating pergola

PZU row19, handle`33FB581`: stroller/bicycle shelter “Wood”, **Relief PM-158**, plan
7.5×1.8m. The previously picture-accepted direction used dimension-only candidate
`MAF_0472_M_Cannopy_006`, catalogue3.071×6.127×2.964m, with built-in benches/platform.
D287 did not certify its article identity. Three row18racks at their original
PZU points and27.31degree rotation intersect that built-in furniture.

Fresh independent per-instance regulatory audits: ALL38MAFs have ALL defect
counters0. Whole-MAF regulatory witness audit: **667v023 →670v024** pairs,
all Bike–Canopy. This counter worsened by3; do not call it a whole-QA improvement.
Strict opposite edge/plane signs and interior barycentric intersections, independent
of the2mm proximity band, prove **447transverse pairs ABOVE actual Ground**, maximum
witness elevation **351.844258mm above Ground**. These are not buried bottom faces.
No automatic deletion of visible benches/platform or movement of accepted points.

Question: allow row19 as an explicit missing-library-type gap, keeping row19/handle
in the38entrycensus but37physicalMAFs, all4582plants and remaining points unchanged;
**or name the correct existing library shelter**. Missing-type reporting is allowed
by the source issue, but departing from the accepted38physical candidates requires
Artem's answer. No change applied pending that answer; no new D-row allocated.
All13existing canopy previews inspected; no PM-158 article match established.

Actual-export full/section views:
`v024/mixed-review-r1/source-bound-mixed-MODEL-QUESTION-NOT-DELIVERED.png`.
SHA256`916d5cea3d84c26afeb63773b402a929a35b66d10c2fa515e7c10763170e5458`.
Blue=currentCanopy006, red=three racks. The right view omits Canopy faces aboveZ1m
ONLY for display; no exported/site geometry was cut. This is not a model proposal,
final material sheet or acceptance. Question body read back normalized-equal.

## Other measured FAILs, still worker-owned

- Current Flora unchanged:515regulatory crossings. New six-maple common-axis pilot
  refuses10.789mm plane nonconcurrence against its10micrometre guard;6RED retained,
  **NOT adopted**, no silhouette/axis moved to manufacture a pass. Planar-knife
  patch analysis finds only90potential triangle savings with protected seams/UV;
  no new Flora surface or failed prior221.552m2-loss variant adopted.
- Fresh public native validators BOTHexit1: NPM2pass/3fail/1review/4not_run;
  VPM3pass/4fail/1review/7not_run. VPMV009 now measures and FAILs0..7782.75px/m,
  not the earlier not_run; exact UV lineage is independently proved. Do not hide it.
- NPM skirt diagnosis:14upward boundary rings,1848outer edges below1m required
  drop; existing1670skirt faces individually span>=1.0009999m but do NOT establish
  full perimeter coverage. No Ground edits or skirt waiver.
- Prior complete Ground4.975942mm/border/domain/normal proof,4620pivot coverage,
 2Urn shelf burial and UCX89.935645mm coverage remain geometry-applicable through
  EXACT target/UCX arrays.175UCXwide-neighbour gaps outside2–10mm remainOPEN.
- Ground/MAF maps, UV/smoothing/normals, remaining mixed contacts and final whole-site
  visual/material/SINTEZ stay incomplete. No library/liveMax/shared checker changes.

## Verification

Affected tests: `uv run python tmp/cold-v024/run_affected.py` → **547passed /
5historical controls deselected (79.49s)**. Exact argv/env/log hash in the summary.
Real mixed-base regression RED108pairs → pre and actual raw/native GREEN0Bikepairs.
Separate Maple6RED and whole technicalFAIL remain explicitly outside the green
checkpoint claim. Whole-join regulatory diagnostic180s timeout retained, not PASS;
38per-instance audits and complete whole-MAF witnesses subsequently measured.
**Full suite: deferred to merge batch (rule 68).**

|Area|Reproduced this run|Remaining value/limit/owner|
|---|---|---|
|Ground|Exact26378NPM /58896VPM arrays; earlier full proof applicable|Skirt1848edges/maps/UV:worker|
|MAF|150buriedfaces removed/profile;12placedchecks;38isolatedregulatory0|NEW row19model choice:user; whole670crossings not waived|
|Flora|4582census/geometry/UV retained; failed axis route refused|515regulatory<=100, mixed contacts/maps/source gaps:worker/source|
|UCX|564pieces/6564tris EXACT; earlier complete89.936mm proof applicable|175widegaps outside2–10mm:worker|
|Delivery|Actual paired native/raw/UV readback and two fresh validators|All technical repairs, then final visual/material and completeSINTEZ|

Historical#906/#969/#1178 comparison remains in v009. D335/D321/Table/Bench/hedge
and source Gates stay CLOSED; only the new row19candidate choice waits on user.
