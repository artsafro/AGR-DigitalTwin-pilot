# #1315 — VPM tree source isolation / metadata diagnosis, v027

**passed=false. No PR, review or delivery claim.** Cells `ground-npm` / `ground-vpm`.
Continuation of our own `9c98c2f1`; all current model files remain byte-unchanged.

## Current pair (ONLY)

- NPM: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v026/site-flora-r3/NPM/SM_SIL13_Ground.fbx`.
- VPM: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v025/site-ucx-wide-r1/VPM/SM_SIL13_Ground.fbx`.
-176094NPM /300120VPM raw=native;37physicalMAF +38census /4582plants.
- NPM Flora already clean; no repeated geometry repair. D339 UCX gap bands are
  OBSERVE/report-only, not a hard-failure repair queue. Libraries remain read-only.

## Metadata: isolated cause, NOT a repaired current version

The v025→v026 metadata difference is exactly SIX absolute Flora image locators.
Units, other settings, embedded bytes, relative locators and connections are unchanged.
An isolated copy restores the original six strings using Blender's own binary
parser/encoder. The entire decoded tree equals v026 except these six strings;
independent native import gives all three object vertex/face arrays EXACT,176094
triangles and both original2048PNG hashes. The old absolute `.fbm` locators
actually DO NOT exist on disk; native import resolves the embedded PNGs. This
is an additional publication limitation, not an available external-map claim.

Actual regression: v025→v026 comparison1RED, v025→restored-copy1GREEN; public
archive_diff exit0 with ONLY Flora geometry/UV declared. **However**, comparison
from the immediate v026 predecessor to the restored copy is still metadataFAIL.
Do not skip that predecessor or relabel the older-baseline pass as the complete
version gate. The copy is **NOT ADOPTED**; archive-metadata remains OPEN. No
shared checker change or waiver. Codec import/type failures and a corrupt
unadopted r2 output are preserved; r3 native success is independently checked.
The public native validator on the r3 copy still exits1:1pass/3fail/1review/3not_run.

## VPM root, independent from NPM and earlier hedge decisions

Complete29615pair census: **29240** are within the six original VPM maples
`33F02A9/33F02AB/33F02AC/33F02AD/33F02AE/33F02AF` (4869–4875each).
First tree:1070triangles /109vertex-connected parts:3trunk/large-branch parts
and106eight-triangle foliage fans. Real first-tree regulatory regression fails
at4869, not the historical NPM515. The other375VPMcrossings remain OPEN too.

Three DISTINCT isolated routes, all **REJECTED / NOT ADOPTED**:

| Route | Actual public faces | Vertices | Other evidence |
|---|---:|---:|---|
| Source-fan6.2mm shell + manifold union |2|5832|72418triangles; closedness is NOT a QA pass |
| Error-controlled optimizer |222|30|54628triangles;1.5mm estimate is NOT a surface bound |
| Cumulative1.995mm original-assignment link contraction |574|111|62026triangles;5196steps; max1.994613mm; not global collision-safe |

The first priority-queue prototype refused a disappearing-component mapping;
retained rejection and added duplicate-face/tetrahedron-collapse refusal before
r3b. Even r3b still fails public QA; no promotion, UV claim or new render verdict.
No current scene, library plant, source point/rotation/species or accepted NPM
geometry changed. Shared dependency files untouched (`uv run --with` experiments).

## New model-owner choice, not a technical-waiver question

Request a NEW VPM-only maple construction choice before substituting a less
 detailed crown for the detailed library VPM crown: retain real VPM trunk/large
branches, pilot a shell from the paired library NPM crown at existing accepted
VPM sizes; export/QA/show that pilot separately before any of six site replacements.
The source NPM first-tree bboxXY6.609×5.784m differs from VPM3.946×4.628m;
it must not simply be copied unchanged or called the same construction.
Alternatively Artem can identify another detailed library VPM maple source.
See `question-receipt-v027.json` for the exact issue comment and readback hash.
No candidate pilot is represented as built or visually accepted. D314's generic
copy experiment authority and D291/D315's accepted shrub/hedge pilots are not
acceptance of a less detailed six-maple VPM crown. D340 and all OLD gates stay CLOSED.

## Verification and outstanding work

- Affected tests: exact argv/env/log hashes in `source-wide-summary-v027.json`;
 227passed (53.66s), including actual metadata regression, native-array equivalence,
 rejected-route isolation and complete pair accounting. First tree remains1RED.
- Full suite: deferred to merge batch (rule68).
- Ground skirt/master/UV/maps, VPM mixed/non-maple contacts, archive metadata and
 final visual/material/SINTEZ gates remain OPEN. No hiding them behind the new
 model choice; independent connected-step checker triage remains`t_66104c70`.
- This continuation is not another cold-agent readiness gain. New code is only
 hashed job-local experimental drivers in Drive; no new shared module or library edit.
