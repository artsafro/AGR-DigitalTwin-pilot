# Vatutino Ground v014 — explicit upper-gap exception (#295 / PR #308)

Status: **not passed / ready for code review**. Ground and shared UCX rebuilt/read back; manual geometry/visual acceptance and SINTEZ/site assembly remain separate, not claimed. No source/main/standards writes. One narrow shared-validator candidate-filter correction is listed below.

## Decision and implementation

[D150] Artem, 2026-10-20, option a (card comment): "the 12 vertices where a ~81 deg face meets a flatter one (normal gap up to 36.9 mm, face centres up to 26.6 mm) are ACCEPTED as an exception, listed by vertex/face id with their gap in the report and the PR; the 20 mm gate stays for every other vertex/face (the exception list is explicit, not a raised threshold)."

`ground-gap-exceptions.json` freezes all 24 over-band measurements: 18 near-corner samples at exactly those 12 vertices, plus 6 face-centre samples. IDs are **zero-based clean projected surface IDs BEFORE skirt/details/final cleanup**, not FBX polygon IDs. This stage is pinned by `surface_sha256`; no ID reuse on changed geometry. Corner samples retain the existing 0.1% pull toward the upper face centre and lower-face normal, as in v012.

- Input SHA-256: `3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502`.
- Surface (exact float64 XYZ and int64 triangle order) SHA-256: `26a646d304692389df584db16398119bed02943d889a82a1fec1828686e65f41`.
- Require an exact sample-identity set and counts, finite measured/frozen gaps, and no increase beyond frozen maxima (numeric comparison epsilon 0.000001 mm). A missing/new sample, source/geometry change or malformed evidence fails the 20 mm gate. No CLI threshold was raised.
- Lower 5 mm, co-directional, containment, relief, UV, density and alias checks remain independent. Manifest input/output aliases are also rejected before writes.
- `normal_gap_over_band_samples` always reports the original measurements; acceptance adds a separate `accepted_samples`/decision field, never hides counters or changes the validator verdict.

## Explicit exception list

| Sample | Upper face | Lower face | Vertex | Gap mm |
|---|---:|---:|---:|---:|
| centroid | 22992 | 22991 | — | 22.671415127 |
| centroid | 25840 | 25839 | — | 22.941478413 |
| centroid | 25852 | 25851 | — | 26.614998379 |
| centroid | 26265 | 26264 | — | 22.347862647 |
| centroid | 26280 | 26279 | — | 24.900964737 |
| centroid | 32790 | 32789 | — | 26.622788769 |
| corner | 22992 | 22991 | 16178 | 31.248536986 |
| corner | 22992 | 22991 | 16179 | 31.248536985 |
| corner | 22994 | 22993 | 16178 | 31.239951279 |
| corner | 23004 | 23003 | 16184 | 36.914151803 |
| corner | 25840 | 25839 | 17840 | 31.629732932 |
| corner | 25840 | 25839 | 17841 | 31.629732932 |
| corner | 25842 | 25841 | 17840 | 31.349857033 |
| corner | 25852 | 25851 | 17844 | 36.911983458 |
| corner | 25852 | 25851 | 17852 | 36.913581175 |
| corner | 26265 | 26264 | 18031 | 30.763370037 |
| corner | 26265 | 26264 | 18032 | 30.763370037 |
| corner | 26267 | 26266 | 18031 | 30.754946106 |
| corner | 26278 | 26277 | 18036 | 36.108089818 |
| corner | 26280 | 26279 | 18036 | 36.095745557 |
| corner | 26280 | 26279 | 18037 | 32.592822838 |
| corner | 32774 | 25851 | 17852 | 36.903273883 |
| corner | 32790 | 32789 | 637 | 36.924463790 |
| corner | 32790 | 32789 | 16184 | 36.924463790 |

## Reproduction / actual execution

1. `uv sync` -> exit 0.
2. `uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v4.json --snap 0.003 --out C:/x/t_d94665f2/ground_v014_diagnostic` -> **exit 1**, only report, failed gate `normal_gap_max_20mm`. This proves the default remains fail-closed.
3. Same command with `--gap-exceptions jobs/VATUTINO-SITE/ground-gap-exceptions.json --out C:/x/t_d94665f2/ground_v014` -> **exit 0, 11/11 geometry gates**, both master JSON written. Both masters are **byte-identical to v012** (no geometry/UV/material changes).
4. Blender 5.1.2 (`ec6e62d40fa9`), headless/factory startup, `--python-exit-code 1 --python tools/blender/ground_json_to_fbx.py -- build <master> <fbx> Vatutino`; then separate clean `readback <fbx> <master> <report> <px> <lo> <hi>` and `render <fbx> <dir> <report>` for each profile -> all exit 0. Earlier shell-path formatting probe failed to open input; repaired native forward-slash paths and added Python exit-code propagation, no source change.
5. `uv run python tools/qa/validate_package.py <fbx> --profile <npm|vpm> --scene --json` -> NPM **2**, pre-integration VPM **1** (UCX absent), neither passed. Raw pre-integration reports `tmp/validate-v014-{npm,vpm}.json`; final VPM after UCX integration and the V008 fix is **exit 2**, no failed stages (`tmp/validate-v014-vpm-final.json`).

## Export/readback

| Check | NPM | VPM |
|---|---:|---:|
| Triangles | 46,343 | 46,343 |
| Surface triangles (master, excluding details/skirt) | 32,821 | 32,821 |
| Raw material mismatches by polygon order | 0 | 0 |
| Surface normals down / mirrored UV | 0 / 0 | 0 / 0 |
| UnitScaleFactor / scene scale | 100 cm / 1 | 100 cm / 1 |
| Object scale / location / rotation | 1 / 0 / 0 | 1 / 0 / 0 |
| Density px/m (all non-Skirt faces, including details) | 11.5555–30.2137 | 589.6264–1442.0618 |
| Out-of-band density | 0 | 0 |
| UDIM straddling / tiles | n/a (NPM world UV) | 0 / [1001] |
| Open edges (accepted class) | 8,307 | 8,307 |
| Face Orientation back pixels top/45/135/225/315 | 0/2/4/3/1 | 0/2/4/3/1 |

Open-border acceptance remains "method-C plate borders, user-accepted 2026-10-19"; it does not waive defects. V004 topology reports no isolated/zero-length elements, max 10 self-intersections (unchanged, human review). V004 clearance: 0 below 5 mm, 24,928 in band, 17,494 distant pairs >20 mm (unchanged diagnostic class), **review**, not pass. Relief max 9.963 mm, all contours inside tolerance, no projection misses/cracks. Locally raised: 435 vertices/1,436 touching faces; max raise 30.94 mm; near-corner minimum 5.049 mm; unaccepted above-band measurements 0. Both profile geometry derived from the single unchanged master. Skirt 1 m; budget/GND-06 areas and all per-entity dispositions remain in the build report and [v011](ground-build-v011.md)/[elements](ground-elements-v011.md).

FBX paths and SHA-256:
- NPM `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx`: `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef`.
- VPM `C:/x/t_d94665f2/ground_v014/vpm/SM_Vatutino_Ground.fbx`: `a41266757fe39958cae7a40a765b628aa7cbfeb74de48d3c82efc297b9cf75f1`.

Readback JSON: `C:/x/t_d94665f2/ground_v014/readback_{npm,vpm}.json`. Renders: `C:/x/vatutino-ground/v014/{npm,vpm}/face_orientation_{top,oblique45,oblique135,oblique225,oblique315}.png` (not committed).

Validator stages (not_run never counted as pass):
- NPM pass V002/V003/V006; review V004/V012; not_run V001/V005/V014/V015/V017.
- Final VPM with UCX: pass V002/V008/V012; review V003/V004/V010; **no failed stages**; not_run V001/V005/V007/V009/V011/V013/V015/V016/V017. V010 shape/coverage remains not_run in the general validator; independent UCX audit below supplies measured evidence, not a rewritten validator verdict.
- No raw validator result changed to pass for the exception or accepted open borders.

Both original DWG hashes re-read unchanged: main `64e22677454affce7071a823123b13742c8d68cd39c1ec0ee761c4cfa3b546e4`, paving `d24df23219fe1357830b3628ca31fa9acacedb158a9d3c8b9f9bc8a16cc3ece2`. This run reads the already-typed adapter v4 JSON, no re-export or second DXF parser.

## Tests / author receipts

- Tests-first commit `d13a7c2` on pre-fix `1f5be1c`: **13 failed** (`tmp/gap-red2.log`). Initial default-temp PermissionError repaired with dedicated basetemp, not counted as RED.
- `uv run pytest -q tests/test_ground_gap_exceptions.py tests/test_ground_review_r2.py tests/test_ground_cake.py -p no:cacheprovider --basetemp=C:/x/t_d94665f2/pytest-gap-green2` -> **49 passed** (19 new, 30 prior). New cases include exact-set/source/geometry binding, dropped/new/duplicate/moved samples, NaN and increased maxima, lower bound, five earlier gates and policy-input/output alias.
- Full non-DCC suite: **6649 passed, 15 skipped, 139 warnings**, exit 0; `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL python C:/Users/artsafro/hermes_kanban/scripts/suite_slot.py --card t_d94665f2 -- uv run pytest -q -n 8 -m "not dcc and not blender" -p no:cacheprovider --basetemp=C:/x/t_d94665f2/pytest-v014-integrated` (236.17 s execution after 1665 s queued; `tmp/suite-v014-integrated.log`).
- Pattern: n/a (existing implementation modules only); test module is marked new-case.
- [D150] was reserved against main/open-PR bodies and comments before appending the registry row (PR #252 owns D136-D149); anchored in the Ground requirement sheet. Focused decision/domain checks: 21 passed. `docs/decisions.md` is a declared hotspot; preserve all pending reservations.
- Regression evals: `tmp/evals-v014/report.json`; **0 passed / 0 failed / 10 not measured**, exit 2 (no Claude transcript / PR evidence in expected primary-repo path). Not a pass.



## Shared UCX integration after PR #334 merged

During this run remote state changed to MERGED (`mergedAt 2026-10-20T02:56:38Z`, reviewed parent head `c2468c1528d65a491956887cafe6bf27e2d85e1e`). `git fetch origin`; proved the parent head is an ancestor of origin/main; `git merge --no-edit origin/main` -> merge commit `433e4eb`. Base remains main, never merged into main or rewrote history. The old suite-slot waiter was still queued; killed its exact orphan native process tree and verified no old pytest-v014 processes before starting the integrated suite.

- Headless shared `tools/blender/ucx_build.py -- C:/x/t_d94665f2/ground_v014/vpm/SM_Vatutino_Ground.fbx C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx Ground` -> **exit 0** with defaults. Report `<out>.ucx_build.json`: 715 hulls, 8,788 triangles / 15,000 cap, 4 mm gap, adaptive 16 m initial cell, exact construction max vertical deviation 0.079852425 m, uncovered strip 0.045956608 m, reverse footprint overhang 0; `within_tol=true` is builder self-measurement, NOT delivery acceptance.
- Final VPM artifact is **`C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx`**, SHA-256 **`a5f7d3963ffbe3003f4dd7d706395a84f30a3548c5281f3402b1c1694cfa3b6c`**. The no-UCX VPM above is retained only as an intermediate source.
- Separate clean `ground_json_to_fbx.py -- readback` on final VPM -> exit 0; render mesh remains 46,343 triangles, raw material mismatch 0, density 589.6264–1442.0618 px/m, tile straddling/mirrored/down normals 0. Coordinate sidecar from the unchanged source preserved the existing MSK-77 origin, not a new transform. NPM remains collision-free.
- Separate clean `tools/blender/ucx_audit.py -- <final.fbx> C:/x/t_d94665f2/ground_v014/ucx_audit.json 100000` -> **exit 0, readback_ok**. **715/715 closed and convex**, 0 material slots/UV, names 001..715; 0 overlaps/touch/below-band pairs; 1,863 in-band adjacent pairs, minimum 3.99 mm after FBX float32; 632 wider candidate pairs.
- Independent wide-candidate classification (101 points between nearest planar edges each, adapted parent round-3 probe, `uv run python tmp/v014-ucx-classify.py`): 423 have another piece between, 172 are seam candidates whose sampled corridor stays within 5 mm of a piece, 37 contain source void; **0 covered corridors**. Grid 0.11 m: **0 / 2,224,138 void samples filled** (3,607,868 total grid points). This is sampled evidence, not a continuous void proof.
- Area-weighted model->UCX audit (seed 165, 100,000 points including source skirt/details): max 0.077 m (<0.1 m), p95 0.024 m. Reverse exposed collision distance max 2.269 m remains diagnostic per D134, not a failure. All checked mutual intersections pass. Final validator V010 remains review for 632 wide candidate pairs and not_run shape/coverage; audit findings are not substituted into raw validator results.

### Out-of-scope fix required for integration

The final FBX initially failed V008 solely because all 715 materialless collision meshes correctly had UV=0, yet the checker required UV=1 for collision too. No open owner issue was found (search `UCX UV`). One-line `src/twinqa/scene.py` change scopes the UV-channel candidate list to non-UCX render meshes; no fabricated UV, no relaxed render rule. Tests-first `6c3478a`: **1 failed, 2 controls passed**; correction `41cbf38`: **512 scene tests passed / 18 deselected**. Render UV=0/2 still fails, render UV=1 + UCX UV=0 passes; UCX presence/budget still pass independently. Final validator exit 2 (review/not_run), no failed stages.

Additional receipts: `uv run python tmp/probe-gap-v014.py` **78/78** actual-evidence probes (all 24 samples independently dropped/increased/moved, 5 malformed scalar controls, accepted control); `uv run dt profiles check` 3 profiles; `uv run dt schemas --check` 12 schemas.

## Remaining acceptance

- Shared UCX is now generated after the authorized parent merge (below); no hand-made UCX or relaxed budgets. Shape/void/deviation proofs remain limited to construction evidence and sampled audits; final human/site acceptance is not inferred.
- Human geometry/visual acceptance, including back-face pixels and 10 Mulch/Stairs intersections, remains outstanding; C36/C37 review, placeholders rather than final texture acceptance. Every source curb/stair disposition remains in v011 evidence; no missing element invented.
- Site assembly / SINTEZ / package acceptance #298 is not executed by this card.
