# #1315 — NPM-only Table adoption; VPM physical-slot scope v015

**`passed=false`; cells `ground-npm` / `ground-vpm`.** [D319] records Artem's
[6896446736 answer](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6896446736):
accept Table016 r4 **for the twelve NPM copies only**, solid tabletop and four
seats, plank divisions to be restored later by texture. VPM keeps physical slats
and geometric slots until a different answer. No NPM representation permission
is transferred to VPM. [D316] Bench and previous hedge/composition gates stay closed.

Evidence root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v015/`.
Current 1600x2300 sheet: `review-sheet-v015-NPM-APPLIED-VPM-SCOPE-NOT-DELIVERED.png`,
SHA256 `484b71636e1fc5f7b0ff68363b8630afe229b1abf8963d1fad093921e8e46097`.
It shows actual library-source geometry and accepted NPM geometry, NOT a rendered
new VPM proposal. Colours are geometry-only; wood texture restoration is unfinished.

## Actual adoption / independent exported readback

| Measurement | NPM | VPM |
|---|---:|---:|
| Raw render triangles | 172487 | 334274 |
| Fresh native render triangles | 172472 | 334226 |
| Remaining other-MAF native face loss | 15 | 48 |
| Newly changed Table016 instances | 12 | 0 |
| Other MAF instances exact against v014 | 26 | 38 |
| All MAF / plant census retained | 38 /4582 | 38 /4582 |
| UCX pieces | 0 | 600 |

Actual exports are `site-table-r1/<NPM|VPM>/SM_SIL13_Ground.fbx`. Four fresh Blender5.1.2
readbacks (two raw-byte and two native) were exercised. All twelve adopted NPM
Tables have **2108 faces** with exact raw/native face arrays and coordinate
difference below10um. Placement points/rotations/ground heights and100mm sinking
are independently recomputed from source controls. Public xView on **each actual
placed table**, not just the old isolated pilot, is clean: **24/24 raw/native
instance checks, 0faces/0vertices/0bowties/0area**. This is not the whole-file verdict.

NPM Ground/Flora and all26 other MAF actual vertex/face arrays are exact against
v014. **Every VPM mesh array**, including all38MAF, Ground, Flora and600UCX, is
exact against v014. The twelve original VPM Table constructions were NOT replaced.
All original/source/library/map/old-site hashes in the previous audit rehash equal.
No source, accepted version, library or checker threshold was edited.

The NPM total172487 stays below180000, with7513 triangles remaining. VPM uses the
same measured9568.799640m2 operand/band2625000 as before. Neither triangle budget
nor successful import certifies the whole delivery. Native15/48 missing MAF
triangles remain an explicit failure, not an import-success loophole.

## Three VPM source-slot repair routes — NOT adopted

The proposed new VPM parameterized construction is **not built**. The following
are rejected copy experiments within the earlier source-profile/joint route:

1. **r1 — source solids/profiles, all76physical wood components retained.**
   3568triangles; public xView202faces/15vertices/0bowties. Source curved backing
   profiles produce near parallel end/rim faces; no site adoption.
2. **r2 — planar source plank profiles, shared wood/backing top levels.**
   3614triangles;297faces/26vertices/0bowties. Coplanar/top alignment does not
   solve real rim/end gaps and introduces Boolean strips; rejected.
3. **r3 — real radial6.2mm plank-to-ring embeds, not blanket slot filling.**
   4818triangles;97faces/647vertices. Its bounded joint finishing keeps separate
   slats, changes side widths by1.8mm and simplifies Boolean strips, but still
   fails64faces/549vertices on4690triangles. Source/profile construction therefore
   is NOT certified. A bounded3.1mm witness cleanup maps every old face to output
   or an explicit drop, moves retained vertices at most1.603mm and removes near
   vertices, but regresses to **70faces/0vertices/0bowties**,4088triangles. This
   final cleanup is rejected too, not silently preferred because it is latest.

One xView adapter call refused NPZ `vertex_map`/`face_map` keys (exit2/no verdict).
A separate diagnostic array file retained those maps externally and passed only
the schema; its actual xView result is the rejected70face result above.
No face/vertex threshold or selected-part exception was introduced.

The original diagnostic occupancy test counted26 full-mesh occupants in sampled
wood-layer gaps. Some can be original metal backing/cap: the probe mixes wood
and frame occupancy, so **26 is NOT a proven count of closed physical slots**.
It is not used as an acceptance claim; wood-slot preservation for a new pilot
must be measured independently against the source, not inferred from this probe.

### Exact source counterexample, correctly classified

Unchanged source wood components16/20 have projected closest gap **4.945264925mm**.
Public VPM xView on their unchanged joined triangles gives **0overlapping faces,
0vertices,3area-only pairs,0bowties,passed=false**, not an intersecting-contact
count. Actual 3D face separations include4.96575-4.96810mm at the unchanged5mm
face threshold. Thus the source has near-clearance diagnostics even before
placement, but it is wrong to call these3pairs self-intersecting faces. No waiver
for other70/44979contacts follows from that observation.

## ONE new model-scope question, not approval of a failed repair

**May a separate source-bound parameterized VPM Table016 pilot rebuild all76
individual physical wood slats and the backing/frame with real inset joints,
keeping geometric slots but widening them to>=6.2mm and realigning ring/slat
interfaces, preserving all12existing instance IDs/points/rotations and D094
overall dimensions? Or must the exact original slot widths/profile shapes be
retained (then name the intended representation/clearance treatment)?**

Recommendation: allow that VPM-only pilot, then require a new measured before/after
picture before replication. It is broader than source-profile thin-wall/joint
cleanup: local plank widths and frame profiles would deliberately be rebuilt,
not merely repaired in place. The NPM solid construction remains forbidden in
VPM. The recommendation is NOT to approve any failed r1/r2/r3 mesh or any whole-site
technical FAIL. Closed NPM/Bench/hedge/composition gates are not asked again.

## Whole-site validators / per-area continuation

| Area | This run | Remaining value / limit / owner |
|---|---|---|
| Ground | Actual arrays exact; NPM native xView0faces/0vertices/0bowties; both full-site validators rerun | Prior perimeter0.006m vs>=1m despite835taggedcontrols>=1.0009999m; details/materials/UV/UDIM:worker |
| UCX | All600VPM pieces actual arrays exact; no NPM/MAF/Flora UCX | Continuous coverage<=100mm,2-10mm pair gaps/contacts:worker |
| MAF | Accepted NPM Table12/12; exact accepted Bench2/2 retained; other26NPM/38VPM arrays exact;24actual-table xView checks clean | NEW VPM76slat/frame reconstruction scope:user. Remaining types/copies/native15/48face loss/UV/materials:worker |
| Flora |4582census retained; actual arrays exact; fresh NPM native xView0faces/0vertices/0bowties | Prior support78.225/78.655percent remains applicable only to exact unchanged arrays, not a new measurement; VPM mixed contacts/maps:worker/source |
| Delivery | Fresh native xViewNPM2819faces/114vertices/213bowties,VPM44979/44/298; validatorsNPM2pass/3fail/1review/2not_run,VPM3/3/1/5 | Technical FAILs:worker; final visual then complete SINTEZ:user/checker owner after repairs |

Known22MAFrows/Abies1/RedSunset4/133m2flowerbed-rate gaps remain explicit; no type or
species is invented. Historical #906/#969/#1178 comparison stays report-only in
[v009](CONTINUATION-v009.md#historical-comparison-report-only-after-this-build).
The original cold-intake boundary is documented in the earlier report; this
resumed worker explicitly uses its own v014 checkpoint, not a new independent
cold reproduction. No readiness increase or delivery acceptance is claimed.

## Checks, ownership and accounting

Tests-first initial checkpoint regression: **4failed** (missing D319 and outputs),
then profile/adoption/export controls pass. The new VPM-clean regression remains
separately RED on70overlapping faces. The older full-set regression remains RED
on43729faces. Neither is concealed by the passing checkpoint selection.

Affected tests: `env PYTEST_ADDOPTS= uv run pytest -q tests/test_decisions.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tmp/cold-v011/test_hedge_contract.py tmp/cold-v012/test_witness_indices.py tmp/cold-v012/test_export_controls.py tmp/cold-v013/test_maf_pilot.py tmp/cold-v013/test_pilot_structure.py tmp/cold-v014/test_checkpoint_controls.py tmp/cold-v014/test_replication.py tmp/cold-v015/test_profile_scope.py -k 'not test_repaired_set and not test_vpm_candidate_clean' -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v015-preseal-green`

**254passed/2deselected (12.61s)**. Both unresolved regressions rerun explicitly:
`env PYTEST_ADDOPTS= uv run pytest -q tmp/cold-v014/test_replication.py::test_repaired_set tmp/cold-v015/test_profile_scope.py::test_vpm_candidate_clean -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v015-open-red`
-> **2failed (7.79s)**,43729/70faces. Detached pre-fix4a3f5df2 authority
regression actually gives1failed(missingD319), then passes on this branch. No
.venv copied; temporary worktree removed. A row-order self-error253pass/1fail
was fixed by moving D319 afterD318, without changing any decision content.
Full suite: deferred to merge batch (rule68).

Direct headless Blender invocations:6 (one two-profile export, four independent
readers, one render-only process). Two more public-validator native-reader
invocations completed. Max2026 ping was read-only; no live user scene was loaded,
saved or mutated. New shared modules:0. Literal job-local driver/adapter lines and
hashes are indexed in the external summary; copied adapters count as code, not
claimed new engines. Total agent tool-call count is not measured.

Resume from **site-table-r1** (NPM D319 adopted / VPM exact v014), never from the
rejected VPM copy experiments. Acceptance remains incomplete; no PR or review.
