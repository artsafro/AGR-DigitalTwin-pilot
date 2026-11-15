# #1315 — accepted continuous hedges replicated, v012/r1 (not delivered)

**`passed=false`; cells `ground-npm` / `ground-vpm`.** [D301] records Artem's
answer [6890885700](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6890885700):
v011/r2's 90-plant continuous-volume silhouette and common top envelope are
accepted without shape edits for replication. The [D300] construction-picture
gate is CLOSED, as are [D298]'s route/68% floor and the earlier composition,
shrub, zero/TIN and source gates. None is asked again.

Evidence: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v012/`.
Preferred full-site exports are **v012/r1**, not rejected v011/r3/r5 or the
isolated failed MAF Boolean experiment below. Libraries are unchanged.

## Real construction and readback

- Continue from the accepted v011/r2 hedge construction. The full site retains
  **4,582 plant census IDs/points/original heights**, including **4,535 hedge
  plants**, **47 unchanged nonhedge copies** and **38 MAF**. No substituted
  species, deleted plant or library-original edit.
- Find the actual cause of the failed v011 numerical edge repairs: public xView
  witness indices are **one-based**, but the job-local collapse scripts used
  them as zero-based. Of the real hedge witnesses, the wrong endpoints exceed
  the threshold in 292/298 NPM and 253/255 VPM cases. The decoder now validates
  index bounds and measured distance, and refuses stale/nonfinite witnesses.
- Contract only actual witnessed short edges in the accepted r2 hedge copies:
  292 NPM /253 VPM contractions, no non-edge contraction. Record every collapsed
  triangle (584/506) with its source run/index/reason. This is numerical cleanup,
  not a new silhouette/representation or permission to edit other MAF/Flora.
- Actual **162,159 NPM /334,422 VPM render triangles** after new FBX exports.
  Ground 58,896 each; MAF 34,121/168,140; Flora 69,142/107,386. Shared NPM
  <=180,000 and VPM <=2,625,000 using 9,568.799640 m2; no NPM UCX.
- Fresh raw FBX and native Blender 5.1.2 readbacks both executed for each profile.
  Native totals 162,120/334,374: inherited MAF still loses **39/48 faces**, so
  native import success is NOT exact whole-file preservation. NPM Flora face
  indices are exact and vertex delta <3.815 micrometres. VPM native geometry
  likewise differs by <3.815 micrometres but drops the 48 MAF faces.
- Independent **actual-export** connected-support audit verifies crown minima
  **78.2253% NPM /78.6551% VPM**, zero of 4,535 below68% in either profile.
  A plant intersection can have a tiny disconnected tip: measure the largest
  connected piece, not a bbox spanning separate pieces. Every point belongs to
  exactly one physical component. Original heights stay in the census; shared
  envelope top differences remain up to0.181347/0.222043m, not independent plant
  bboxes. Ground/MAF/600UCX arrays and 47 nonhedge copies remain exact.
- **Actual NPM Flora public xView is now 0 faces /0 vertices /0 bowties /0 area
  pairs**, versus r2's 576 near vertices. Hedge-only VPM has0/0/0 but2 `area`
  diagnostics. VPM nonhedge/mixed contacts and aggregate QA still fail.
- Whole-file public xView remains **3,197 faces /1,026 vertices /669 bowties NPM**
  and **45,052 /44 /298 VPM**. Public thresholds are recorded literally:
  vertex0.002m, face0.005m for BOTH profiles. A profile name is not a different
  threshold. Complete public package diagnostics execute FAIL (NPM2pass/3fail/
  1review/2not_run; VPM3pass/3fail/1review/5not_run). `review`/`not_run` are not pass.

## New model-owner boundary: MAF library construction

This is NOT another Flora gate or approval of existing technical failures.
Seven distinct real library MAF types underlie the38 accepted-by-picture copies.
Current isolated exported VPM xView face counts are Table0162570, Sand0021543,
Bench013170, Bench02540, Bicycle00718, Canopy0063437, Urn0100. Several have open
or nonmanifold components. NPM remains separately measured in the JSON index.

A **fresh native import of the ORIGINAL library Bench025 FBX**, without placement
or simplification, already gives **37 overlapping faces**,0near vertices and
0bowties. SHA256 `e6b6a2ba2ce042d957c80649dbf6285ecfa3d35e041f95142fe888691b2e723a`
is unchanged before/after. Exact one-based triangle witnesses retain29 contacts
with plane separation2.999941–4.999995mm,22 with opposing normals. Unmeasured
separations stay explicitly unmeasured; they are not filled with zero.

Test-first closed-component Boolean union on COPIES is a rejected experiment,
not an applied replacement: Bench025190→320triangles,40→70overlapping faces and
38new near vertices. Sand002VPM1543→1059faces but947near vertices; Bicycle007
18→59faces/88near vertices. Nonmanifold/open components are explicitly refused,
not filled or converted into invented proxy solids. The picture shows the real
bench before/rejected Boolean result; the apparently similar silhouette is not
checker success. No MAF Boolean result is in the full site.

The [MAF sheet](../../docs/domain/areas/groundel-maf.md) / [D165] requires constructive
inserts and silhouette fidelity; [C44](../../docs/domain/conflicts.md) leaves
constructive embed vs counted intersections unresolved outside its named job.
Library-only placement is not silent authorization to redesign thin details or
reinterpret that checker. Recommendation/question to Artem: **authorize a
job-local constructive repair on copies of these seven MAF types (union/repair
actual joints; where needed, thicken the measured3–5mm details to6.2mm), preserving
type, all38IDs/counts/points/plan rotations and overall dimensions within[D094],
then show a separate small before/after pilot before site-wide adoption; or name
the required representation/rule for those library joints?** No library-original
edit, MAF-from-PDF modelling, substitute, C44 waiver or acceptance of FAILs is
requested. This new model choice, not the completed hedge gate, is the wait.

## Per-area reproduction / ownership

| Area | Reproduced / actual route and calls | Remaining value / limit / owner |
|---|---|---|
| Ground | Same source-derived58,896triangles each; actual arrays unchanged; NPM xView0/0/0. Independent835tagged skirt vertical controls >=1.0009999m,1,670skirt triangles | Public whole-perimeter minimum0.006m vs>=1m is stillFAIL on another contour. Prior shorthand 'only6mm skirt' was incomplete, not a waiver. Curbs/details/materials/UV/UDIM:worker |
| UCX |600VPM-only pieces/6,876triangles exact, no new collider construction | Pair gaps2–10mm/continuous coverage/internal contacts and renewed<=100mm proof:worker |
| MAF |38accepted-by-picture copies unchanged;7source types isolated, source bench fresh native import and closed-component Boolean test | New copy-construction scope/C44:model owner. Native39/48face loss, topology/normals/maps/atlas:worker.22row gaps unchanged |
| Flora |4,535hedge census in accepted continuous volumes,4,582IDs and47nonhedges exact; corrected edge witness decoding,2exports/4readbacks, public actual arrays and independent support audit | NPMFlora0/0/0; VPM46Flora diagnostic face pairs (2hedge area, other shrub/mixed pairs), seating/UV/maps/materials:worker/source. No renewed construction approval |

DCC execution in this continuation: one two-profile export process, two raw reads,
two native reads, one original-library-bench native inspection/comparison render,
one render from the actual NPM native readback. All are headless Blender5.1.2 in
owned processes/new paths. Max2026 read-only ping succeeded; user live scene was
not changed. Driver code is job-local, sealed externally; no shared checker,
production Python module, threshold or library changed. The final JSON inventory
lists drivers, hashes and line counts; this is not an automated capability claim.

Abies1/RedSunset4/22MAFrows/133m2flowerbed-rate gaps remain listed, not invented.
Grey Physocarpus/Syringa and interim maps remain as disclosed. The actual native
site render shows the whole site/building cutout, patches and hedge runs, with
obvious grey/interim vegetation and provisional material appearance. It is not a
final textured visual approval. [D301] is construction-only. Final visual/SINTEZ
and complete materials are still due.

Historical comparison is unchanged and report-only: [v009 comparison](CONTINUATION-v009.md#historical-comparison-report-only-after-this-build).
#906 establishes accepted Ground-only xView/material discipline, not a transferable
texel exception; #969 is an OKS delivery/gate comparator, not a site-library etalon;
#1178's atlas/placement route is not acceptance of this dense site's changed hedge
construction. Historical geometry/runtime was not consumed or remeasured; no
speedup, equivalent delivery or readiness increase is claimed.

## Verification and retained failures

Affected command: `env PYTEST_ADDOPTS= uv run pytest -q tests/test_decisions.py tests/test_area_requirement_sheet.py tests/test_ground_surface_requirement_sheet.py tmp/cold-v011/test_hedge_contract.py tmp/cold-v012/test_witness_indices.py tmp/cold-v012/test_export_controls.py -p no:cacheprovider --basetemp=C:/x/t_d9ae7dc0-v012-final`:
**187passed/0failed (3.03s)**. Includes1,000generated index/distance controls plus
1,000stale-distance rejections, malformed indices, duplicate index, empty/partial
census, NaN/inf/negative/bool thresholds, and inclusive threshold/68% controls.
Original one-based regression RED1failed/2passed→GREEN; new threshold probes
RED3failed/12passed→GREEN; D301anchor RED1failed/114passed→GREEN.

Separate MAF model probe **remains RED**: original placed bench40faces; attempted
union70faces. Both real pytest logs retained, not included as a green repair or
hidden by xfail. The geometry fix is not claimed. The first independent support
audit refused a MultiPolygon intersection; a stricter largest-connected-piece
audit passed. The first diagnostic-witness serializer hit `None` separation;
corrected publication keeps those entries unmeasured. All failed logs retained.

Full suite: deferred to merge batch (rule68). Fresh-checkout procedure walk remains
`passed=false`, with the new model wait and technical gates incomplete, not a
finishedPR.4source/9library/3original maps plus original bench hash unchanged.
All binary evidence is on Drive with SHA256SUMS; git contains only small text.
