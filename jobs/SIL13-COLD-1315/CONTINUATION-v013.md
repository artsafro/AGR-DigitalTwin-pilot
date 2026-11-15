# #1315 — copy-only constructive MAF pilot v013/r2 (not accepted)

**`passed=false`; cells `ground-npm` / `ground-vpm`.** [D305] records Artem's
answer [6892163018](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6892163018):
constructive repair of COPIES of the seven library MAF types is authorized,
including real insets/joints and necessary3–5mm details to6.2mm, preserving all
38IDs/counts/points/rotations and overall dimensions under[D094]. Originals remain
untouched. A separate before/after pilot MUST be accepted before site replication.
The repair-scope question is CLOSED; no earlier hedge/composition/zero/TIN gate is
reopened. No C44 interpretation, checker exemption or technical FAIL is approved.

Evidence root: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v013/`.
Current full sheet: `review-v3/review-sheet-v013-r2-NOT-ACCEPTED.png` (1600×2500),
indexed in `review-sheet-v013-index.json`. Original2300px layout had overlapping
labels; review-v2 accidentally duplicated the original layout after a job-local
exec namespace collision. Both are superseded, not overwritten. The corrected
layout is read back from Drive and sealed separately; actual geometry unchanged.
Geometry-only comparison: source grey LEFT, actual changed-copy FBX orange RIGHT.
Side views show both genuine frame holes, not invented solid-box legs. Review
flat shading is explicitly separate from final smoothing/material acceptance.

## Real pilot / attempts

1. Actual source is `maf/union_v001/fbx/MAF_0435_M_Bench_025.fbx`, SHA256
   `e6b6a2ba2ce042d957c80649dbf6285ecfa3d35e041f95142fe888691b2e723a`.
   Prior fresh native source inspection gives101vertices/190triangles and
   **37overlapping faces**; the actual source regression fails37vs0. No earlier
   rejected Boolean geometry is promoted.
2. Source connectivity identifies two rectangular frame legs and one seat slab.
   Reconstruct their measured planar bounds on a copy, retaining both real
   through-holes and squaring source micro-bevels<=3mm. Leg frame walls become
   **6.2mm**. Exact joint union removes internal contact faces; this is disclosed
   changed construction, not a claim of exact original surface preservation.
3. First authorized route r1:116triangles, exact bbox, but public xView gives
   **14faces /8nearvertices**. Seat/frame intersections leave tiny Boolean ledges.
   This candidate is **REJECTED**, saved with its actual reports.
4. Distinct r2 joint route: embed the seat's back edge to the measured frame back
   plane (**+4.910mm**), lower its top onto the frame inner top plane
   (**−0.699mm**). Genuine frame holes remain; frame outer bounds are unchanged.
   Actual measured overall size is **2.000000×0.404827×0.450055m**, bbox deviation
   zero before export, native numerical delta<0.036micrometres. This is a
   before/after model option requiring picture acceptance, not silent adoption.
5. Actual NPM/VPM FBXs: **116triangles each**. Fresh Blender5.1.2 native import
   and independent raw FBX byte/axis/units readback: **116/116faces exact**, vertex
   max delta3.5392e-8m; no inherited face loss in this isolated pilot. Exported
   geometry arrays are identical across profiles; both retain metre units and
   unit scale. Materials are neutral geometry-only, not a final atlas.
6. Public xView on BOTH raw actual-export arrays and BOTH native actual-export
   arrays: **0faces /0vertices /0bowties /0area**, literal vertex2mm/face5mm
   thresholds unchanged. Closed, positive-volume, nondegenerate/unique-face and
   all-edge-incidence2 tests pass. Twenty seeded probes test **1,000hole points
   outside /1,000frame-wall points inside** the actual exported solid.
7. Independent sampled symmetric displacement against original triangles:
   source→pilot17,290samples, max**6.0714mm**; pilot→source10,556samples,
   max**6.0137mm**. The sheet rounds upward. This is NOT an exact Hausdorff bound.
   Source three-component vertex sets are fully accounted for; micro-bevels,
   thin-wall surfaces and internal seat/frame contacts are reconstructed,
   not attributed to missing source geometry or hidden drops.

Two export profiles in one owned headless Blender process; a distinct fresh
raw/native readback process and a native comparison-view process. All outputs
are new versioned paths. Max2026 read-only ping succeeded; no user live scene
was changed. Local drivers/tests and failed logs are sealed externally, not
registered as a reusable shared tool. A mistyped lowercase xView profile was
explicitly refused then corrected to literalVPM. First tiny preview conversion
rejected RGBA quantization; RGB conversion corrected it. No fabricated output.

## Honest public-validator result

Public `validate_package.py --scene --json` was run on BOTH isolated pilot FBXs.
NPM **1pass/3fail/1review/3not_run**, VPM **2pass/4fail/1review/5not_run**.
This geometry-only pilot is not named/packaged as a Ground delivery. NPM failures
are unmapped diffuse, no embedded texture, delivery naming. VPM failures are
provisional projected UV mirroring26faces, absent GroundUCX, delivery naming,
and local pilot pivot rather than final shared Ground centre. These remain
explicit, never pass or a requested waiver. MAF needs no own collision; the
isolated object is not a complete Ground FBX. Materials/UV/final smoothing/pivot
work remains worker-owned before delivery. No new pilot failure is relabelled
as a successful whole-file technical repair.

## Per-area continuation / value, limit, owner

The full-site **v012/r1 FBX bytes are unchanged** in both profiles. Actual
162,159NPM /334,422VPM triangles,4,582plant census IDs and38MAF are historical
measured site values, NOT a newly built v013 whole-site result. Source/library
checks rehash4sources/9libraries/3original maps plus the original bench; both
site FBXs also rehash equal. The pilot has not changed any placed ID, point,
rotation, size, Ground, Flora or UCX.

| Area | This continuation | Open value / limit / owner |
|---|---|---|
| Ground | No geometry edit; v012/r1 bytes exact | Known whole-perimeter0.006m vs>=1m, despite835taggedcontrols>=1.0009999m; curbs/details/materials/UV/UDIM:worker |
| UCX |600VPM-only pieces unchanged; no NPM collider | Continuous coverage<=100mm and2–10mm pair gaps/internal contacts:worker |
| MAF | One source-bound changed-copy Bench025 pilot,116triangles both, raw/native public xView0/0/0/0area | NEW pilot construction/silhouette picture:user. Remaining6type repairs and38copy replication/native39/48inherited site face loss/materials:worker after pilot acceptance.22source-row gaps remain |
| Flora | Accepted[D301] construction and4,582census unchanged; NPMFlora0/0/0 is prior actual site evidence | VPMshrub/mixed contacts,materials/grey/interim maps:worker/source. No renewed hedge gate |

Full-site public validators stillFAIL; no fresh full-site validator run was
needed for an unreplicated isolated pilot. Prior #906/#969/#1178 comparison
remains [report-only](CONTINUATION-v009.md#historical-comparison-report-only-after-this-build):
no earlier site's scripts or geometry were consumed, no transferred exception
or readiness gain. Abies1/RedSunset4/22MAFrows/133m2flowerbed-rate gaps remain
listed. Technical/final visual/SINTEZ acceptance stays incomplete.

## Verification / new required gate

Affected tests: `env PYTEST_ADDOPTS= uv run pytest -q tests/test_decisions.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tmp/cold-v011/test_hedge_contract.py tmp/cold-v012/test_witness_indices.py tmp/cold-v012/test_export_controls.py tmp/cold-v013/test_maf_pilot.py tmp/cold-v013/test_pilot_structure.py -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v013-final`

**214passed/0failed (3.53s)**. Source xView regression RED1failed (37vs0)→GREEN;
authorization-record regression RED1failed (missingD305)→GREEN. Initial missing
pilot receipt tests failed3; initial existing generic documentation checks were
115green, not a claimed failing D305 regression. Real failed r1 is retained.
Full suite: deferred to merge batch (rule68).

**New question:** accept the v013/r2 Bench025 copy's construction/silhouette,
including squared micro-bevels,6.2mm frame walls and measured seat/frame joint,
for replication, or specify shape/joint edits? This is the required[D305]
BEFORE/AFTER gate, not another authorization request or approval of failures.
No site replication until Artem answers. Acceptance applies only to this shown
construction, not unshown changes of the other six MAF types. PR=null;
implementation remains incomplete, so no review_requested or completion claim.
