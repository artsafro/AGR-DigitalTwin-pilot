# #1315 — visible VPM interface pilot, v030

**passed=false; NOT ADOPTED; no PR/review/delivery or final visual acceptance.**
Cells `ground-vpm` / unchanged `ground-npm`; continuation of10c6149d, not a new cold run.

## Applied answer, not repeated

Artem6959387195 («Принимаю рекомендации», option a) closes question6958474507.
[D342] records the exact hidden-only VPM delivery cut, retaining the10cm-buried
source master and census. Registered `skeleton.json` placement-after hook
`hooks/visible_interface.py` fills only this job's surface-subset operation;
no parallel builder, shared checker or library edit. New module: `new-case`.

## Actual isolated copy, not site replication

Bench013 /33FB3BD, actual source5064triangles -> **4373** in both raw and fresh
native Blender5.1.2 FBX readbacks,2200vertices.744fullyhidden source faces,
95partiallycut,4225unchanged; full per-face barycentric maps and UV interpolation
sealed externally. Vertical walls are partitioned in source barycentric space,
not their singular XY plane. Every actual upward Ground triangle participates;
stacked surfaces subtract the hidden part under every layer, not the first hit.
Coverage residuals <=2.356e-16 barycentric area are numerical roundoff, not an
exact symbolic proof. Numerical line triangles <=0.1nm altitude are logged with
barycentric coordinates, not silently treated as visible detail simplification.
The retained source vertices are not deliberately moved; actual FBX float
roundtrip max coordinate delta3.547um raw/3.335um native is disclosed.

Same official BVH/regulatory route against local actual Ground: **183 ->0**,
pre/raw/native; real pre-fix regression1FAILED183, actual post-fix1PASSED0.
Public xView in BOTH actual readbacks still **0faces/65nearvertices/49pairs/
0bowties**: FAIL. A separately isolated source wall249640 has regulatory0 and
public0, but certifies neither Bench nor site. Source/code numeric tests pass;
that is not approval of the failing physical candidate.

Standalone diagnostic FBXs `export-r1/{before,after}/SM_SIL13_Ground.fbx` have
archive_diff exit0, explicit `--expect-changed SM_SIL13_Ground`, geometry/UV only,
no metadata or duplicate-name waiver. This isolated comparison does NOT close
the whole-site immediate-predecessor metadata FAIL. One source material12
retained, no new texture or appearance approval. Actual native/clay failure
renders only; no acceptance scene or finished model was opened.

## Three distinct bounded repair trials, all REJECTED

1. Exact source-triangle cut: regulatory0 but65nearvertices. Initial numeric
   line triangle left1regulatory pair (3Darea3.28e-16m2); barycentric zero/line
   detection removes only that numerical artifact. Raw/native fail remains.
2. Planar-patch retessellation: regulatory0 but83faces/211vertices/14bowties;
   near-coplanar reconstruction is NOT adopted.
3. Native BMesh planar/collinear dissolve1e-6rad: regulatory0 but65nearvertices;
   no deliberate source offset and no improvement, NOT adopted.

Supplementary separate Urn probe is NOT adopted:110triangles,21regulatory and
4nearvertices. A failed first Urn run refuses a numerically collapsed triangle;
0.1nm line classification is retained explicitly. No checker exception or
increased tolerance, visible deletion, vertex slide, source/census loss or
whole-site adoption is inferred from any trial.

## NEW bounded model question, not hidden-cut permission

https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6960708487
(readback equal; `question-receipt-v030.json`). Actual source corner531 lies
0.708/0.522mm from exact-contact vertices530/532; max incident-normal angle51.58deg.
It is a real visible kink, not a collinear redundant point. Strict exact visible
shape and the2mm vertex-clearance rule collide here. [D342] removes hidden parts
only; it does not authorize changing this above-Ground corner. Do not implement
the proposed <=2mm local visible repair, limited to<=5mm above Ground, before
Artem's answer. If authorized, ONE new measured pilot and separate picture
approval before site-wide replication; never expand the bounds silently.

Full-resolution1800x900 failure image:
`G:/Мой диск/AGR-evidence/1315-cold-silikatny/v030/failure-comparison-NOT-ADOPTED.png`
SHA256`edff0a69ff911a3334321f3a8528d52340d1608409240dd4c2b7f6fb25e452cd`.
Right image is an actual7mm native-readback view, red markers on measured
vertices only. First black/occluded camera render retained rejected, not shown.

## Current full-site pair and unwaived remainder

UNCHANGED: NPMv026/site-flora-r3,176094triangles; VPMv029/site-maples-r3,
298218triangles;37physicalMAF/38census/4582plants/545UCX. Neither diagnostic
Bench nor Urn nor single-wall subset replaces any site geometry. The full-site
source master keeps10cm burial.22original/source/library hashes and both
current FBXs are rehashed in `source-wide-summary-v030.json`.
Whole VPM stays79869regulatory pairs (62572Ground-Flora/16653Ground-MAF/
613Flora/31Flora-MAF), public9faces/49pairs and validatorFAIL. Skirt/master/
maps/UV/legacy archive/final visual/SINTEZ stay OPEN. D339UCX bands OBSERVE,
not a wide-gap repair queue. Independent skirt-checker triage t_66104c70 unchanged.

## Verification

Affected tests: `CUT_MODE=native PYTEST_ADDOPTS='' uv run pytest -q tests/test_sil13_visible_interface_1315.py tests/qa/test_topology.py tests/ops/test_xview_gate.py tests/qa/test_archive_diff.py tests/test_scenario_router.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tests/test_maf_requirement_sheet.py tmp/cold-v030/test_actual.py -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0/v030-affected` -> **448passed0failed66.62s**.

New retained tests:25passed, including real source frame face1->0, six generated
slope/scale/winding probes, missing/partial/nonfinite/degenerate inputs, layered
upper envelope, duplicate layer order and exactly-at-surface retention. Initial
8RED/no hook, then8GREEN; real actual-source whole-Bench regression183RED->0GREEN.
Final affected command uses `--basetemp=C:/x/t_d9ae7dc0/v030-final` and adds
source empty/partial/nonfinite/exact-degenerate-threshold and immutable-input
probes: **455passed0failed118.13s**; earlier scope448passed66.62s retained.
Current hook reproduces the actual precursor's seven arrays EXACT (v/f/UV/mi/
smoothing/source-face/barycentric); no stale report is transferred to new geometry.
Full suite: deferred to merge batch (rule68).

Initial source-shape float roundtrip is measured explicitly; source/census retention
is not a claim of bit-identical cross-reader coordinates.

First repo_guards RED: D342 absent from a tracked non-job domain anchor;
self-fixed by adding the specific Ground practice row, no guard relaxation.
Final guard result and postdocs tests are sealed in summary/manifest.
Environment self-fixes: unsupported `decision_ids.py next --all-branches` ->
read-only manual origin/improve + active-board reservation scan (D341 reserved,
D342 reserved on card8753); `agr` not onPATH -> `uv run agr`; `python` lacks
project yaml/trimesh -> `uv run` / temporary `uv run --with trimesh`, no dependency
or machine-wide setting edits. Headless render needed an explicit own World;
failed render retained, corrected camera checked visually. No live Max touched.
