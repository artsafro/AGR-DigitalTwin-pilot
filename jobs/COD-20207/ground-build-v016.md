# COD 20207 — second-site Ground test, v016 (#420)

## Verdict and acceptance boundary

The second-site experiment and review publication are complete; **delivery not passed**.
This is a measured pipeline trial, not a declaration that the route is general or
that COD is a final SINTEZ package. Human visual acceptance, original-etalon normals,
parking markings, normal-map transfer and six UCX corridor candidates remain review
items. No checker, budget or tolerance was relaxed. No D150 exception is used.
The parked Vatutino quad v015/#371 route was NOT used: COD version numbers are
local attempts of the same triangular method-C route.

Gate 1 and source hashes: [gate-1-intake.md](gate-1-intake.md), confirmed
[parts.json](parts.json), `adapters/cad/configs/cod_20207.yaml`. Historical failure
receipts remain in build-attempt-v001.md, overlay-repair-v002.md,
ground-build-v008.md and native-xview-review-v001.md; their questions are now closed.

## Last source decision and reusable changes

Artem, card comment 2026-10-21 01:59: Tile remains continuous at +6 mm; remove
only the Geogrid hidden by Tile, no extra +12 mm Tile strips. Future analogous
fully hidden overlaps use visible-layer continuity, with the choice recorded.
The generic `covering_priority: [["Tile", "Geogrid"]]` setting implements this
by semantic slot, including the reinforced source types. It is not a site-name
conditional. Invalid/unknown/repeated/conflicting pairs are rejected. Legacy
calls omit it and keep their original route/order.

Measured clipped hidden area: geogrid 0.029179137779575 m2;
geogrid_reinforced 0.000001981298671 m2. The pre-clip comparison's
0.029182716615471 m2 differs at the 1 um normalization grid; this is not a
new source-boundary decision. Each hidden covering gets a named disposition.
Method C still retains the full Asphalt base, a 6 mm upper-covering step,
1 m skirt and approved 150/50 mm curb sections; drive/garden 6 mm joints remain.

All changes required by this second site:
1. Explicit flat datum, semantic slots and uncovered-covering settings in the
   existing `jobs/VATUTINO-SITE/build_ground.py`; no invented survey observations.
2. Opt-in polygon-only make_valid/1 um clipping normalization, including empty,
   non-polygonal, below-area and precision-collapse dispositions, in ground_cake.
3. Approved taller-continuous curb joints in ground_details, configurable and
   off by default for legacy Vatutino.
4. Approved visible-covering priority before overlay, with hidden-area receipts.
5. Optional explicit CRS label in the existing Blender exporter. COD passes
   `DWG WCS metres; CRS unspecified by user, no transform`; no hand-edited final
   sidecar. Historical `origin_msk77_xyz` key remains for readback compatibility;
   its numbers are source WCS, not an assertion of MSK-77 authority.
6. Texture/source coverage findings: copied-etalon diffuse atlas crops rather
   than Vatutino maps; normal atlas and separate painted parking markings are
   not reproduced. Crop enlargement adds no detail. These are recorded limits,
   not material-equivalence acceptance.

## Execution receipts

- `uv sync --extra cad` completed in the preceding attempt (exit 0).
- Priority tests-first 391dc18: 1 failed (unsupported setting); CRS tests-first
  e9aa705: 1 failed / 1 legacy control passed. Fix b38dd9f: 40 passed in 5.21 s
  (site settings, curb joints, real Blender CRS export); exit 0.
- Initial focused retry encountered the documented inaccessible default pytest
  temp (WinError 5). Private `--basetemp=C:/x/t_3e9518e5-green-final` repaired it;
  no production workaround or global environment change.
- Build: `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/ground-cod-22/intake-v001/cod_ground_inputs.json --site-settings jobs/COD-20207/build-settings.json --snap 0.003 --out C:/x/ground-cod-22/ground-v016`
  exit 0; 11/11 gates. Log `tmp/cod-build-v016.log`.
- Blender 5.1.2, factory startup, one thread, python-exit-code 1: build each
  master with `tools/blender/ground_json_to_fbx.py -- build <master> <raw.fbx> COD20207 <CRS>`;
  VPM `tools/blender/ucx_build.py -- <raw.fbx> <collision.fbx> Ground`;
  both `tools/materials/bind_ground_textures_blender.py -- bind <geometry-or-collision.fbx> <binding-plan.json> <final.fbx>`;
  both existing exporter readbacks. All 7 subprocesses exit 0; exact argument
  arrays/log hashes in `ground-v016/execution-export-v001.json`.
- Fingerprints before/after binding equal, including raw FBX material arrays,
  ordered geometry/UV and UCX inventory: 2/2. Image readback: 7/7 exact source
  image hashes per profile, 2/2 profiles; Cycles top/oblique renders saved.
- `tools/blender/ucx_audit.py` final VPM, 100000 samples, seed 165: exit 0.
  Orientation render and both fingerprint readbacks: exit 0. Both
  `tools/qa/validate_package.py <final> --profile <npm|vpm> --scene --json` exit 2;
  review/not_run stages are NOT passes. Exact commands: execution-qa-v001.json.
- Native Max 2026.3 batch, copied final NPM and VPM, metres, Editable Poly:
  OverlappingVertices 2 mm / OverlappingFaces 5 mm, **0 vertex IDs / 0 face IDs
  on each profile**, 3169 verts / 5659 polygons. Prior v008 4/5 is fixed.
  Wrapper exit 0, native process **4294967166** (existing PolyUnwrapper startup
  error). Measurement markers and reports completed; not a clean process exit.
  `tmp/cod-native-final-v016-run.json` retains the full native-status distinction.
- Vatutino real v014 prior rerun: both complete ordered master JSON files byte
  identical, 2/2 (hashes in native-xview-review-v001.md). Final legacy synthetic
  plan + complete ordered mesh parity 1/1, SHA-256
  `6c33802ea4f60cf9f9634720b73325a6849b26a01c266fe5c1ed7994769ab399`.

## Vatutino v014 versus COD v016

| Same check | Vatutino v014 | COD v016 |
|---|---:|---:|
| Plot / footprint m2 | 25854.04 / 9110.08 | 5101.59 / 1670.09 |
| NPM / VPM render triangles each | 46343 | 5659 |
| Surface triangles / 50000 | 32821 | 2321 |
| Whole master / 150000 | 46343 | 5659 |
| VPM area-dependent cap | 4500000 | 1650000 |
| Geometry gates | 11/11, pinned D150 | 11/11, no exception |
| Relief | max error 9.963 mm | flat by user decision |
| Flat corners / centres, max error m | n/a | 6963 / 2321; 0 / 8.674e-19 |
| Skirt depth m | 1 | 1 |
| Exported NPM non-skirt density px/m | 11.5555–30.2137 | 29.8916–30.0491 |
| Exported VPM non-skirt density px/m | 589.6264–1442.0618 | 1001.4123–1049.7519 |
| Out-of-band / mirrored / down surface faces | 0/0/0 | 0/0/0 |
| VPM UDIM straddles / tiles | 0 / [1001] | 0 / [1001] |
| Raw material-order mismatches | 0 | 0 |
| Open edges (not automatically defects) | 8307 | 613, off-outline surface edges 0 |
| Face Orientation back pixels top/45/135/225/315 | 0/2/4/3/1 | 0/0/0/0/0 |
| Python xView, current checker | 0 vertex / 222 face pairs | 0/0 |
| Native Max xView | not rerun | NPM 0/0, VPM 0/0, startup status above |
| UCX hulls / triangles / cap | 715 / 8788 / 15000 | 501 / 5928 / 15000 |
| Closed and convex | 715/715 | 501/501 |
| UCX overlap / touch / below band | 0/0/0 | 0/0/0 |
| In-band / wide pair candidates (3D audit) | 1863 / 632 | 1451 / 1144 |
| 100k sampled forward max distance m | 0.077 | 0.046 |
| Reverse distance, diagnostic only m | 2.269 | 1.000 |

Vatutino's 222 current Python face pairs are from the byte-identical rerun,
not a stored/native v014 metric or a newly introduced geometry change.
NPM UV straddles are allowed world-continuous repeats, not VPM UDIM errors.

## Ours versus the hand-made etalon

| Same measurement | Native LP etalon | Native hp etalon | Automatic NPM/VPM |
|---|---:|---:|---:|
| Named Ground render triangles | 2817 | 48765 | 5659 / 5659 |
| Up-facing triangles (proxy, includes curbs) | 2033 | 13879 | 2991 / 2991 |
| All render triangle area m2 | 6158.163 | 10617.647 | 5233.954 |
| Up-facing XY union m2 | 5112.052 | 5112.978 | 3431.498 |
| Sum up-facing XY areas m2 | 5137.123 | 5982.762 | 4500.070 |
| UCX count / triangles | 0 / 0 | 23 / 296 | NPM 0/0; VPM 501/5928 |
| Height range | 158.727219..161.326645 LP frame | -2.675156..5.503055 hp frame | flat datum; skirt -1, curb tops .068/.168 |
| Surface/detail-only budget split | unavailable | unavailable | 2321 surface / 3338 other |
| Texture/material set | legacy Ground_1 d_1/n_1 atlas | native identity retained | 7 diffuse-only semantic materials |

Etalon full plane extends under the building; approved 1670.085519 m2 hole
explains most projected-area difference. Etalon heights are NOT scored against
our flat model. Curbs: all 9 SPOZU entities modeled, drive 150 mm/garden 50 mm
exposed; approved 6 mm mixed-section joints. Geometry readback within 2.057675 um
both ways, unit scale 1, object scale/location/rotation 1/0/0, one UV channel.
Original FBX crashed even without custom normals; authorized copied-Max clean
FBX fallback succeeded. Native snapshots, not clean-import face counts, supply
etalon budgets. Original normals/native-etalon xView remain not measured.
See native-xview-review-v001.md for exact atlas crops and all crash receipts.

## UCX candidate classification and remaining limits

Independent planar nearest-edge/101-point corridor probe on final exported hulls:
1145 planar-wide candidates: 891 have another piece between; 193 stay within
5.1 mm of a piece; 55 cross source void; **6 covered corridors remain review**.
Planar set differs from the audit's 1144 3D candidates (different predicate).
Residual IDs: 122/125, 292/308, 296/301, 296/302, 296/305, 322/343.
Their max sampled distance to any hull is 5.169–6.279 mm; pair gaps 11.169–66.898 mm.
This does NOT prove compliant direct-neighbour spacing. Do not call UCX passed;
review junction adjacency/continuous gap geometry before final delivery. Full
rows in `ground-v016/ucx-corridor-classification.json`. 100k forward surface
samples all within 0.046 m support the separate <=0.1 m shape check only.

Preview observation: a central building hole, broad dark roadway and narrow
curbed green perimeter bands are visible; no obvious additional large hole in
the viewed oblique render. Fine seams, curb source fidelity, texture equivalence
and parking-marking completeness are NOT established by that observation.
The etalon uses separate painted parking polygons, absent here; no new content
or normal map was invented. This trial exposes those pipeline findings.

## Review publication (not user acceptance)

`C:/x/review/2026-10-21/420-cod20207-ground-v016/420-cod20207-ground-v016.max`

Existing publisher command `uv run python tools/review/publish.py --task 420
--slug cod20207-ground-v016 --fbx <final VPM> --png <vpm/textured-oblique.png>
--what <explicit pending-acceptance and pipeline-limit note>` exited 0.
First attempt returned busy shared Max lock; retried unchanged after release.
`C:/x/review/pending.json` read back: #420 row points at the exact scene above;
previous publications remain. Independent FINAL-path Max reload: 502 geometry
nodes, 2 camera-related nodes, metre units, all 7 bitmap paths exist. Source
FBX/live user document untouched; review camera is not exported into delivery.

## Additional UCX parameter probes (diagnostic, NOT selected)

The six planar corridors were not silently accepted. A zero-covered-corridor
assertion on v016 returned exit 1 (`tmp/ucx-corridor-red.log`). The existing
shared builder was then exercised WITHOUT code or tolerance changes:

- v017 `gap=0.0025`: rejected with `UcxBuildError: gap 0.0025 m outside the
  build band 3-6 mm (inside [D098] 2 mm - 1 cm)`. Initial error-report write also
  found its missing collision parent; creating that new output directory exposed
  the original error. Both logs retained. No collision FBX was exported.
- v018 `gap=0.003`: build/export/readback/audit exit 0; 542 hulls / 6304 tris,
  no overlap/touch/below-band pairs, 1611 in-band / 1244 wide candidates,
  sampled forward max still 0.046 m. The independent planar probe found 993
  another-piece / 194 within-5.1-mm / 56 source-void / **1 covered corridor**
  (350/371, pair distance 54.672795 mm, max-to-any-hull 5.221607 mm).

This reduces but does not establish the adjacency contract. It is NOT a fix or
reason to relax the classifier. v018 is an unselected diagnostic under its own
new path; final review remains v016 using Vatutino's default gap=0.004. No UCX
algorithm/threshold/source changed. A direct-neighbour review, not another guessed
parameter, is needed to establish whether these planar junction witnesses are
actual 3D spacing defects. Testing exposes this limitation; no generality claim.

## Hashes

| Exact path | SHA-256 |
|---|---|
| `C:/x/ground-cod-22/spozu.dwg` | `9b409b023a5dd494c91f6807e7aee392b6a684da48fac371209764770d5f764b` |
| `C:/x/ground-cod-22/gp.dwg` | `5f1155b8c317350515dcf0995c5dbcfb643f40c0d1dd28e2af1bd852e7f32300` |
| `jobs/COD-20207/build-settings.json` | `6d2ce7a2551bad1628830be3a032c6fc60a4fbb54abd23624e8ab893e5821c2c` |
| `C:/x/ground-cod-22/ground-v016/ground_master_npm.json` | `9fed1a51944de12fa9fde9fa9d4260114fc9bc12a52096b46041c040a980df7c` |
| `C:/x/ground-cod-22/ground-v016/ground_master_vpm.json` | `c4d86add44d57aaa528c95ef57fea8f8d4981914f7dc80e2b5ba68afde372081` |
| `C:/x/ground-cod-22/ground-v016/ground_report.json` | `c3f3a7167d2fedba84295e2caab6c04bbda977b76743bcc77bc27da9b0c3cea8` |
| `C:/x/ground-cod-22/ground-v016/npm/SM_COD20207_Ground.fbx` | `58f11cf7ef93cba46809373ff777f9b0420c4c5e3dd76bd6a7872c7d1b063fe0` |
| `C:/x/ground-cod-22/ground-v016/vpm/SM_COD20207_Ground.fbx` | `1dad8cff229e6f037f4b0271240346e58ec531de3b231e70d0a3773bcc129c20` |
| `C:/x/review/2026-10-21/420-cod20207-ground-v016/420-cod20207-ground-v016.max` | `7c824bb72ec06a5c086552fe5fcab29e0d77d4a4d53b78aa74157fbc74f23417` |
| `C:/x/ground-cod-22/ground-v016/native-xview-npm.json` | `9756bc63f7c3d90dd1fcd37b114fa6fad5770c0a145367700334feb8c24ba170` |
| `C:/x/ground-cod-22/ground-v016/native-xview-vpm.json` | `9756bc63f7c3d90dd1fcd37b114fa6fad5770c0a145367700334feb8c24ba170` |
| `C:/x/ground-cod-22/ground-v016/published-readback.json` | `ab38427ca1e63b45dacca106cd19e0cc40e3b02bacdece11b762fd943d89b36e` |
