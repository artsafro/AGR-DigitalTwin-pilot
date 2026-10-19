# Flora library audit: catalogue and triangle budgets (#189)

## Question and scope

Audit the supplied Max library and FLORIO set without inventing species identity: enumerate every label, compare XY nearest pairing against bounded display-row pairing, export every plant variant, and read the outputs back.
This is a source audit, not a passed AGR delivery. No new species/textures, original-scene edits, standards changes or production checker changes.

## Setup and commands

- Headless 3ds Max 2026.3 (28.3.0.30732), embedded Python 3.11.12, via `dcc_batch.py max` only, one locked batch at a time. No live bridge/safe-mode changes.
- Both originals were hashed before copying to `C:/x/t_366e8d9d/`; Max loads only those copies. Both scenes report meters, SystemScale 1 and one scene unit per metre.
- Native entry points: `tools/max_flora_inventory.py`, `tools/max_flora_archive.py`. Pure analysis and reproduction commands: [README](../../experiments/flora-library-audit/README.md).
- Actual FBX outputs: `C:/x/t_366e8d9d/out/assets-v003/`; corrected SVG previews and coordinate-verified receipts: `out/verified-v004/`. FBX 2014 / 7.4 binary. No binaries in Git.
- Machine [catalogue](../../experiments/flora-library-audit/catalogue.json); schema/fields in README; complete [findings](flora-library-audit-findings.md).
- Source method context (source attribution, not a decision): [Max scripting research](../research/3dsmax-scripting.md), `tools/max_profile_roundtrip.py`, [Artem's Flora grilling notes (2026-10-15)](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/187).
- Startup warning: `polyunwrapper_autoload.mse` CLR error returns native -130; the wrapper classifies it as a warning. Current job markers/receipts and independent hash/readback checks determine completion, not native exit alone. Legacy mental-ray attributes are unavailable.

## Counts and interpretation

| Source | All nodes | Text / TextPlus | All meshes / plant | Paired labels | Ambiguous | Orphan incl headings | Normalized captions | NPM / VPM candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| FLORA_Union_v1.max | 506 | 320 / 6 | 179 / 90 | 319 | 4 | 3 | 53 | 71 / 66 |
| FLORIO_2BT_2022.max | 69 | 23 / 0 | 46 / 46 | 0 | 23 | 0 | 35 | 23 / 23 |

The 80 display slots are not 90 proven unique species. Normalized caption counts include cultivar-only strings and project multiline alternatives; see the complete names in findings. LP -> HP entries overlap both descriptive profiles. NPM/VPM candidates are not conformity assertions.
Library nonplants: 80 Box envelopes, five planters, four size cylinders, one helper; all retained under `excluded_nodes`. Every Box has 20 triangles, Multi_Ground and a bbox top at/below placement Z within 1mm; its display-plinth role remains unverified.
Library species/profile labels contain no height/crown dimensions. Project Hnnn tokens assume cm explicitly (unverified); all alternatives and >10% mismatches are retained. Hidden TextPlus uses the static GetPlaintextString by-reference adapter. No raw caption is repaired.

## Baseline versus prototype

Same extracted nodes and exclusions; median of three pairing runs, excluding Max startup, I/O and scene loading. Concordance means agreement with a literal triangle-count label, not independently established botanical correctness.

| Source | Method | Median s | Unique / ambiguous | Triangle-label concordance |
|---|---|---:|---|---|
| FLORA_Union_v1 | xy | 0.0223406 | 116 / 210 | 26 / 81 |
| FLORA_Union_v1 | xz | 0.0215681 | 321 / 5 | 78 / 81 |
| FLORA_Union_v1 | bounded_row | 0.0166942 | 319 / 4 | 78 / 81 |
| FLORIO_2BT_2022 | xy | 0.0008413 | 23 / 0 | 0 / 0 |
| FLORIO_2BT_2022 | y | 0.0006270 | 0 / 23 | 0 / 0 |
| FLORIO_2BT_2022 | bounded_row | 0.0001710 | 0 / 23 | 0 / 0 |

Pairing function size: XY baseline `pair` 9 lines; bounded row prototype `row_pair` 25 lines. It adds row/right selection, bounded nearest fallback and <=20% distance ties. In this library labels sit below mesh pivots in XZ, so fallback is intentional; FLORIO is a left-hand XY schedule with two high/low columns, retained together by Y row. Conflicting same-role captions are ambiguous; identical Text/TextPlus duplicates corroborate rather than compete.
All ambiguous pairs, headings, orphan notes and unlabelled plant names are enumerated in the generated findings; no silent nearest-first resolution. Three ordinary source count discrepancies remain: SM_klen_tatarsky001 (1901 label / 1091 measured), Object002 (10 / 8), co-located SM_boyaryshnyck_obyknovennyi001 (488 / 574).

## Triangle statistics and proposed budgets

| Type | Profile | n | Min | Median | p90 nearest-rank | Max | Review above |
|---|---|---:|---:|---:|---:|---:|---:|
| tree | NPM | 28 | 8 | 531.0 | 1266 | 3830 | 3900 |
| tree | VPM | 26 | 264 | 830.0 | 4894 | 6267 | 6300 |
| bush | NPM | 43 | 18 | 80 | 120 | 1254 | 1300 |
| bush | VPM | 40 | 32 | 84.0 | 160 | 1254 | 1300 |
| hedge | NPM | 0 | None | None | None | None | None |
| hedge | VPM | 0 | None | None | None | None | None |

Review thresholds round the observed maximum up to 100, rather than failing the upper 10% of the current library. p90 is descriptive. No hedge samples means no hedge budget. Bush includes ornamental perennials. These are not regulation limits or a checker change: NPM Ground+GroundEl+Flora still share 180k triangles; VPM Ground limits depend on area and unresolved regulation conflicts.

### Project comparison statistics (not new budgets)

| Type | Profile | n | Min | Median | p90 | Max |
|---|---|---:|---:|---:|---:|---:|
| tree | NPM | 5 | 125 | 166 | 238 | 238 |
| tree | VPM | 5 | 350 | 1007 | 1914 | 1914 |
| bush | NPM | 17 | 10 | 10 | 10 | 979 |
| bush | VPM | 17 | 20 | 20 | 20 | 5074 |
| hedge | NPM | 0 | None | None | None | None |
| hedge | VPM | 0 | None | None | None | None |
| climber | NPM | 1 | 10 | 10 | 10 | 10 |
| climber | VPM | 1 | 20 | 20 | 20 | 20 |

## Library versus FLORIO

Exact normalized captions: 13 shared, 40 library-only, 22 project-only. Project variants with name candidates: 26/46; with exact-triangle and bbox-within-20% candidates: 2/46. Exact mesh-name matches: 0.
Full name lists and per-entry candidates are in findings/JSON. No synonym, typo or cultivar normalization beyond case/yo-e is invented. Candidates are not approved replacements.

## Native archive and independent verification

**Acceptance complete: True.** Exports/previews: 136/136; native readbacks: 136/136; exact-with-tolerance readback checks equal: 136; failed IDs: [].

| Native variant | Observed result |
|---|---|
| MAX v001 baseline | 9 saves, median 47.043s between saves; cancelled, no readback; retained outside Git |
| FBX v002 early attempt | 1 file + SVG before cancellation, no readback; retained unverified |
| FBX v003 | 136 exports + 136 initial readbacks; six apparent mismatches exposed a double-transform bug in the measurement, not promoted as a pass |
| Final selected versions (see artifact_basis in JSON) | Median selected export+preview 3.1371977999951923s; corrected signature+preview 0.677986750000855s; native readback 2.577982550006709s; maximum matched-corner deviation 0.007921813834112239mm |

Corrected native source snapshot bboxes agree with independent nodeGetBoundingBox (maximum 0.0mm); maximum matched UV deviation 0.0. `tools/max_flora_verify.py` first checks a translated/rotated SYNTHETIC mesh, then every real source and imported object. `snapshotAsMesh` vertices are already world coordinates here: multiplying node.transform again created placement-dependent errors. The correction removes that multiplication, preserves the FBX bytes, regenerates previews to a new version and repeats every readback without relaxing the matcher tolerance.
Selected artifact routes: {'native_direct_fbx': 131, 'derived_world_state_Editable_Mesh_snapshot': 1, 'identity_transform_world_TriMesh_value': 4}. The v004 coordinate correction alone left five genuine polygon-corner/winding or affine-transform conversion failures. Tree_LP changed from 2075/3065 matching triangles to 3065/3065 after an isolated Editable Mesh snapshot (v006, 0mm max). Full-scene snapshot export v005 stalled without an output and was cancelled; its exact blocked API phase was not instrumented. Four flowers retain shear in snapshot NODE transforms; their FBX bboxes change even though source/snapshot match. The separate v007 variant creates `mesh(mesh=world_TriMesh_value)` at identity, checks equality before export and reads each file back. No old file is overwritten; any failed/pending rows keep acceptance_complete=false. Maximum deviation above covers equal rows only when the audit is incomplete.
Autodesk reference for snapshot/node versus TriMesh-value construction: https://help.autodesk.com/cloudhelp/2017/ENU/MAXScript-Help/files/GUID-0532C071-4401-4846-8450-3DA5510A3883.htm (native behavior tested in Max 2026). World geometry, not original pivot/matrix identity, is preserved in derived exports.
Readback is native Max FBX import into a reset headless scene, one geometry object per file, binary header/version independently checked. The bijective matcher checks every triangle/cyclic corner (preserving winding), world positions, per-corner UV and finish material names, plus bitmap-reference equality and metre units. It does not certify shading/smoothing, topology quality of the originals, texture pixels or botanical appearance.
All stored bitmap references were unresolved in the source inventory. Atlas use is reference sharing only; no atlas pixel/UV-island validation is claimed. Previews are actual untextured native-mesh XZ wireframes, not rendered/opacity appearance approval. Materials are not repathed and no textures are generated.
Native wrapper wall times including startup/shutdown: original v003 archive+first readbacks 1721.5s; v004 source-probe/signature/corrected-readback job 956.4s. Per-asset medians above are a heterogeneous workload distribution, not a controlled cold/warm or MAX/FBX speedup claim.
The v003 first two exports measured 156.85s and 97.56s; later calls were materially faster. The initial abort-based extrapolation from a cold first file was not representative. Per-row checkpoints preserve progress and source/artifact hashes; repeating the same command skips only verified receipts. Cause of the cold delays is not proven.

Independent receipt: [verification.json](../../experiments/flora-library-audit/verification.json). Both original hashes were re-read after the archive audit; copied scenes are equal too.

| Source | Bytes | SHA-256 before | SHA-256 after |
|---|---:|---|---|
| FLORA_Union_v1.max | 19519734 | `30d7fc32fc534e7165ac1f47385cdcf2a91adb967228a087e3a9404a6e397416` | `30d7fc32fc534e7165ac1f47385cdcf2a91adb967228a087e3a9404a6e397416` |
| FLORIO_2BT_2022.max | 6041600 | `787dce8aeb7aa826c4f35c583a869e4cd89f34e035f92c4d83bd0fd696faaca8` | `787dce8aeb7aa826c4f35c583a869e4cd89f34e035f92c4d83bd0fd696faaca8` |

## Invariants

- Original untouched: two original/copy hash equalities; generated synthetic hash probe mutates a copy 30 times and proves the reference unchanged; hostile-path probe rejects 100 traversals.
- Every Text accounted: library 326 = 319 paired + 4 ambiguous + 3 explicit orphan/non-asset records; project 23 = 0 + 23 + 0. Synthetic competing-caption/accounting probe covers 21 translated layouts; every candidate resolves to a plant handle.
- No binaries committed: actual diff/untracked-path scan rejects native/image extensions and NUL bytes, plus generated probes for seven binary/image suffixes and disguised NUL text. Final Git diff check is also recorded in the PR.
- Resume safety: synthetic checkpoint probe rejects changed source hashes and 30 modified outputs; real archive verifies each receipt before skipping. Existing unreceipted files are never overwritten.
- RED on prior catalogue implementation (20420b4 plus new acceptance tests): 3 assertion failures / 1 pass for missing structured parser, row matcher and p90. GREEN: 20 standalone audit tests, including the additional double-transform regression (RED: actual X=20 vs expected X=10; GREEN after removing extra node transform). The earlier collection ImportError is not valid RED evidence.
- Full unchanged project suite final rerun: 3279 passed, 9 skipped, 13 deselected, 359.69s (concurrent native verification). Earlier run this attempt: same counts, 327.76s; prior baseline 326.45s. No claimed suite speed improvement. Profiles: 3 OK; schemas: 11 OK; `git diff --check` clean.
- Regression evals: `tmp/evals/flora-library-audit-resume/report.json`, exit 2, 0 passed / 0 failed / 10 NOT MEASURED (Hermes has no expected Claude-format transcript/PR evidence); not an eval pass.
- Pattern / new case: module docstrings mark #189 as a standalone source-audit case, not production modelling or a reusable general-layout rule.
- CI: not run (billing lock). No fabricated subagent or trace claims.

## Author receipts

- Pattern / new-case: new case #189 in catalogue/checkpoint/native-entry module docstrings; explicit non-delivery scope and empirical layout rule.
- Regression evals: local `tmp/evals/flora-library-audit-resume/report.json`, 10 not measured, exit 2; missing Claude-format transcript is recorded, not treated as green.
- Probe: generated source-integrity, label-accounting, binary-diff and resume-tampering probes plus every-file native readback receipt; see Invariants above.

## Verdicts and follow-up

**ADOPT, limited to this display layout:** bounded row/display-plane association with raw labels, ambiguity and orphan lists. It improves the triangle-label proxy without inventing species identity. Proposed follow-up: **Flora catalogue intake: explicit layout schema and reviewed species/profile IDs**; scope: review co-located/unlabelled/cultivar-only entries, reject unknown layouts and add hedge fixtures before checker thresholds.
**ADOPT, bounded to these intake cases:** evaluated Mesh exports with source-corner guards; use identity-transform world TriMesh VALUES where source nodes carry shear. Tree_LP snapshot fixed its polygon conversion; four sheared flower variants required identity baking, not snapshot nodes alone. Proposed follow-up: **Flora FBX intake: world-state Mesh values and affine guards**; scope: generalize behind a flag with translated/rotated/sheared fixtures, immutable UV/finish/winding readback, source hashes and per-file resume receipts. Do not normalize original masters or claim appearance approval.
**MAYBE:** observed type/profile ceilings as review-only budgets; no regulation or checker update without planting-quantity/site context. **REJECT:** automatic authoritative species substitution, appearance approval or a delivery pass from this audit.

## Out of scope / seen, not mine

- Missing maps, curated species deduplication and stable Flora material IDs belong to [#216](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/216); texture generation belongs to #190. No new species or texture is added here.
- Shared runner stale-lock ownership risk: [#223](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/223), filed after two duplicate searches. The waiter timeout can expire a healthy longer holder; no external wrapper was edited or lock manually removed, and this card never submitted overlapping native calls.
- No PROJECT_STATE edit on this task branch; merge/acceptance/publication remain separate gates.
