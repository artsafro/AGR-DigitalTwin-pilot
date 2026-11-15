# #1315 — accepted Bench025 replication and NEW Table016 representation choice v014

**`passed=false`; cells `ground-npm` / `ground-vpm`.** [D316] records Artem's
[6893485374 answer](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6893485374):
Bench025 v013/r2 is accepted, including the 6.2mm frame walls, genuine holes and
repaired joint. Replicate the same constructive approach to the other MAF copies;
libraries remain untouched. The [D305] pilot-picture gate is CLOSED. No renewed
Bench/MAF repair-scope, hedge, composition, zero or TIN question is asked.

Evidence root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v014/`.
Current sheet: **`review-sheet-v014-Table016-r4-FLAT-D316-NOT-ADOPTED.png`**, 1600x3050.
Earlier missing-seat r1 and smooth-shaded views are superseded, NOT current.
Colors distinguish geometry only; final materials/wood texture are not shown.

## Accepted construction actually replicated

The exact accepted 116-triangle Bench025 is placed in its **two existing copies**
(handles 33FB3BE /33FB3BF), both profiles. Source-plan points, rotations, ground
height and 100mm sinking retained. No new source or library geometry substituted.

| Actual export | NPM | VPM |
|---|---:|---:|
| Raw render triangles | 162011 | 334274 |
| Fresh native render triangles | 161972 | 334226 |
| Other MAF malformed-face loss, explicitly unresolved | 39 | 48 |
| Changed Bench025 copies / retained all MAF | 2 /38 | 2 /38 |
| Other MAF copies exact against actual v012/r1 arrays | 36 | 36 |
| Retained plant census | 4582 | 4582 |
| UCX pieces | 0 | 600 |

Four independent fresh raw/native full-site readbacks were exercised. Each placed
bench has116 raw/native triangles, exact face arrays and coordinates within10um
of the accepted source-derived placement. Ground, Flora and every UCX actual
vertex/face array are exact against v012/r1. Therefore previous Flora support
minima78.225/78.655% and the census remain applicable to **unchanged arrays**;
no new individual merged-plant bbox claim or new crown measurement is invented.
No other experimental MAF candidate was promoted to the site.

Whole-site public xView still **FAIL**: NPM3122faces/1026vertices/669bowties,
VPM44977faces/44vertices/298bowties. Public native `validate_package.py --scene`
ran on both new FBXs: NPM **2pass/3fail/1review/2not_run**, VPM **3/3/1/5**.
Neither is technical acceptance. Geometry-only bench UV remains provisional.

## Three distinct repair routes retained, not relabelled as passes

Fresh Blender5.1.2 reads all seven unchanged source FBXs before copy experiments.
The source set itself yields9083 overlapping faces,2236vertices and106bowties.

1. **r1 source-triangle shell6.2mm + union:**43729faces/41718vertices, rejected.
   Per-triangle normal skins create severe slivers; no site replication.
2. **r2 structural profiles / source-boundary repair:** the five-type partial
   output gives803faces/832vertices; original canopy lattice is unsupported by
   generic boundary filling (empty output), rejected. An API-doc mismatch for
   MeshFix `fill_holes` was corrected locally; the failed log is retained, not
   represented as geometry acceptance.
3. **r3 source structural masks:** original canopy component1 is a **beam lattice,
   not a roof skin**. Native component views reveal15nodes/30actual beam segments.
   Component78 is a stepped platform, not a single convex box. Source-beam hulls
   and measured horizontal platform levels replace the erroneous mask; no filled
   courtyard/roof proxy is promoted. Seven-type r3 masks still fail3103faces.
   QEM alone, chain-cluster contractions and bounded-net+LOD are recorded with
   their own witnesses: the best retained complete net candidate still has
   **300faces/14vertices/5bowties**. Source-face drops and collapse histories are
   external, not silently called retained geometry. A final boundary cleanup
   refuses empty output. These are failed technical attempts, not user waivers.

The originally required complete-set repair regression remains **RED**:
`test_repaired_set` observes43729 !=0 on retained r1. It was deliberately not
included among the226 green checkpoint controls; acceptance is incomplete.
No rule/checker threshold was changed. No new shared Python module was added.

## Newly observed model choice: real wood planks, not fasteners

Table016 source has **28 tabletop +48 seat wood-plank components =76**, plus four
metal supports, a small central cap and curved backing frames. Those76 large
components are **NOT fasteners** and were never authorized to disappear under a
fastener exclusion. Replacing their real radial slots by texture is a different
representation from squaring tiny Bench025 edges or repairing a joint.

A separately exported, **UNADOPTED** r4 option demonstrates the new choice:

- Continuous tabletop and **four real solid seat sectors**, not empty backing
  rails. Four source access gaps and four metal supports remain. Source-derived
  support C-profile walls measured4.15-4.36mm are thickened by expanding in-plane
  boundaries1.2mm per side; the earlier slab-axis correction did not address them
  and is retained as failed r3. Overall bbox max delta **1.222mm**.
- Source6180 -> option **2108triangles each**. Both actual FBXs independently read
  as raw bytes and fresh native Blender:2108/2108faces exact, raw/native coordinate
  delta<0.119um. Both raw and native NPM/VPM public xView are **0faces /0vertices
  /0bowties /0area** at unchanged2mm/5mm thresholds. Closed positive-volume mesh,
  every edge incidence2; no final package/material pass is inferred.
- Twenty seeded actual-native mesh occupancy probes: **1000/1000 seat points
  inside**, **1000/1000 points in four access gaps outside**.
- Sampled source->option:28052points,max **19.126mm**; option->source:9488points,
  max **39.624mm**. These measurements include removed slot/internal surfaces;
  **NOT exact Hausdorff bounds** and not covered by the prior Bench pilot6.072mm.
  Physical plank-slot depth/underside construction is deliberately changed.
- The plain geometry sheet has **no restored plank texture**. Any later plank
  appearance by texture is proposed work, not an existing measured result.
- Only a projection: replacing12 current Table016 copies with this2108triangle
  option would give172487NPM /285410VPM render triangles before other repairs.
  **Those are NOT built-site counts.** Current12Table copies remain byte/array
  unchanged in the new site exports. All38MAF and4582plant records remain.

**One new question:** accept this shown continuous tabletop/four-seat construction
for the12Table016 copies, with physical plank divisions represented later by
texture, or require retaining those physical wood slots? Recommend the continuous
copy route only with this explicit representation approval. This is not another
[D316] repair authorization and not acceptance of whole-site technical FAILs.
The new option is NOT applied before Artem's answer.

## Per-area result / value, limit, owner

| Area | This run | Remaining value / limit / owner |
|---|---|---|
| Ground | Actual arrays unchanged; both exports/readbacks/validators rerun | Whole-perimeter0.006m vs>=1m despite835taggedcontrols>=1.0009999m; curbs/details/materials/UV/UDIM:worker |
| UCX |600 VPM-only pieces exact, no NPM/MAF/Flora collider added | Continuous coverage<=100mm,2-10mm pair gaps/contacts:worker |
| MAF | Exact accepted Bench2/2;36othercopies unchanged; seven real sources inspected; three failed repair routes retained | NEW Table physical-plank representation choice:user. Remaining6types/36copy repair,39/48native face loss/materials:worker, not waived |
| Flora |4582census; entire actual geometry exact, no renewed hedge question | VPM shrub/mixed contacts, maps/grey/interim species:worker/source |
| Delivery | Both current full-site native validators ran FAIL | Final technical QA, visual and complete SINTEZ:worker/user/checker owner after repairs |

Existing Abies1/RedSunset4/22MAFrows/133m2flowerbed-rate gaps stay listed, never
invented. Historical #906/#969/#1178 comparison remains the report-only table in
[v009](CONTINUATION-v009.md#historical-comparison-report-only-after-this-build).
No historical same-site build scripts/geometry were consumed; no earlier site's
exception or readiness gain is transferred. Library originals/4sources/9libraries/
3original maps/original bench and both old v012site files rehash unchanged.

## Registry aliases, not new model decisions

A new pre-push scan found foreign main #1412 using earlier pushed pilot IDs and
PR1422 using the new reservation. Only this branch's current canonical rows and
TASK/REPORT/area citations were mechanically changed: D298->D313,
D300->D314,D301->D315,D311->D316. Meaning, answer URLs and geometry unchanged.
`decision_ids.py next` returnedD313; all origin/improve heads highestD312;
active-board D313-D319 reservations0; `gh pr list --state open --search
'D313 OR D314 OR D315 OR D316'` returned[]. Current guard:OK(main+4openPRheads).
Own D311 reservation11:23:36Z preceded PR1422's plan11:24:01Z by25seconds; this
branch still yielded the display ID rather than touching another branch.
Historical v001-v013 documents and generated/sealed receipts retain execution-time
IDs and hashes; resolve them only with [decision-aliases-v014.json](decision-aliases-v014.json).
They are not authority for unrelated newly merged main decisions. D305 unchanged.
The new sheet uses the canonical D316; old D311-labelled layouts are superseded.

## Tool/code accounting and checks

This run's12 direct headless Blender invocations include7-source intake in one
process,2full-site exports in one process,4full-site reader processes, source-part
views, option exports/readbacks and corrected views. One view-only invocation
failed because an empty factory scene had no World; its FBX/native output was
retained and a separate render-only stage repaired it. Two additional public
validator reader invocations completed. Ground/UCX/Flora got **zero new builders**;
exports/readbacks/validators are shared across areas, not counted four times.
Four Max bridge calls were read-only (ping, version/document/units/count and
source MAX object-name query); the user's K3 scene was not loaded/saved/changed.
Total agent tool-call count is not measured. Actual commands/logs and job-local
Python driver sizes/hashes are indexed externally; copied/generated adapters are
included in literal line counts, not claimed as independently authored engines.

Affected tests: `env PYTEST_ADDOPTS= uv run pytest -q tests/test_decisions.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tmp/cold-v011/test_hedge_contract.py tmp/cold-v012/test_witness_indices.py tmp/cold-v012/test_export_controls.py tmp/cold-v013/test_maf_pilot.py tmp/cold-v013/test_pilot_structure.py tmp/cold-v014/test_checkpoint_controls.py tmp/cold-v014/test_replication.py -k 'not test_repaired_set' -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v014-preseal`

**226passed,1deselected (17.17s)**. The deselected **unresolved complete-set repair**
is explicitly rerun separately: `env PYTEST_ADDOPTS= uv run pytest -q tmp/cold-v014/test_replication.py -k test_repaired_set -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v014-open-red` -> **1failed,1deselected**,43729vs0.
D316 authority RED1missing->GREEN; new option contact regression RED4failed
(12faces on retained r2) -> actual exported r4 GREEN4/4. No complete-task green
claim. Public whole-site validators and the unresolved regression stay FAIL.

Full suite: deferred to merge batch (rule68).
PR=null; no review requested, acceptance incomplete. Resume from
`site-bench-r1`, not failed set r1/r2/r3 or missing-seat optionr1. Obtain the ONE
new Table representation answer, then continue worker-owned technical repairs,
actual exports/readbacks and final visual/SINTEZ gates without reopening D316.
