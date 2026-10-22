# AC06 diagnostic build — blocked, NOT a delivery

## Scope and pinned inputs

Issue #563 BUILD fan-out, branch `job/tec26-oks-ac06-build`.
Starting main: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Merged designated inputs: `origin/job/tec26-oks-pilot-ac08` (`5febf7c`) and
AC06 Gate-1 branch `origin/improve/issue-563-tec26-06-1-materials-per-multisub-id-fro`.
Historical `materials.json.build_allowed=false` is retained as the Gate-1 packet's
scope marker; the BUILD authorization is this card's orchestrator note, not an
edit to the historical approval. No new user approval is claimed.

Staged Max copy and drawing hashes: `materials.json.inputs`.
Read source layer `006` once using the card-authorized locked headless Max route,
not the reachable user's live Max scene. Native version 2026.3; metres x1.
`max-dump-006.json` has 23 uniquely handled nodes: main 170, glass 378, 21
collision candidates. Max wrapper status `ok`, native exit `4294967166` with
polyunwrapper startup warning; `DUMP-OK` and the actual complete JSON establish
extraction, not the wrapper status alone. Source file was not saved.

## Blocking question: conflicting visible upper fascia

The approved mapping assigns ID1 (roof **and upper fascia**) entirely RAL7004,
ID2 (canopies/trims) blue metal, and ID3 walls solid RAL7047. The Gate-1 packet's
last section explicitly leaves blue-wall ID identity unresolved. The building's
own supplemental DWG colour rendering
`C:/x/tec26-oks/AC06/evidence-v001/dwg-facades-recovered.png` visibly has a blue,
vertically ribbed **upper facade band** on all four facades. Isolated ID1 evidence
`evidence-v004/isolated-1-shaded.png` includes the roof and vertical upper fascia.
The diagnostic build follows the approved table, so this upper fascia is grey.
It is NOT an acceptance render and is not being sent to Artem as one.

**Question for Artem:** should the vertical upper-fascia faces within ID1 be
RAL5015 with vertical ribs, while sloping roof faces stay RAL7004, preserving
source ID1 and geometry? The alternative is to retain approved ID1 wholly grey,
which differs from the colour sheet. Please confirm which authority applies.
After this answer, measure this building's rib count separately on all four
native DWG colour views; do not import AC08's 30/12 counts or 0.20 m step.
The recovered DXF image is supplemental, not a native authoritative count source.

## Executed result (diagnostic only)

`bash jobs/TEC26-OKS/AC06/run_build.sh C:/x/tec26-oks/AC06/build-v002`
completed with exit 0. AC08's shared builder first refused the two Multi/Sub
meshes (main + separate glass). The job-local adapter explicitly partitions by
handles, builds the main/collisions using the existing recipe, and retains the
separate map-free glass object. No node is dropped. All five opaque finishes
are currently solid placeholders (density-exempt, not a measured 1000 px/m
panel texture); exact KPP 5015/7004/9016/Interior colours, approved 7047 RGB.
Source geometry/IDs preserved in the working master; UCX triangulated for export.
No ring cuts. Mixed ID10 below zero uses wall 7047, above uses plinth 7004.

- Main: 3118 source vertices, 2954 source polygons, 5596 exported triangles.
- Glass: 24 source vertices, 6 source polygons, 12 exported triangles.
- VPM: 21 UCX objects, all triangulated. NPM: main + glass, no UCX.
- VPM: 5 sequential placeholder UDIM triplets, 256 square RGB.
- NPM: one 2048 RGB diffuse atlas and separate opacity atlas, embedded FBX.
- Separate clean-process readback of both exported ZIP FBXs completed.
- Public `uv run dt qa xview .../readback/vpm/SM_Prg_1.fbx --out .../xview-vpm.json`:
  zero overlapping faces/vertices, exit 0 (CLI printed default NPM local profile;
  do not misstate this as a VPM-threshold certification).
- `qa_packages.py`: **71/98 checks pass; 27 fail**. This is NOT green QA.
  Failures: hardcoded no-glass name expectations; UCX comparison expects original
  polygon counts rather than required triangulation; UCX004 convexity false at
  readback; 8 unmatched main triangles / 4 uncovered source polygons in finish
  coverage, though wrong-finish=0; texel-contract check rejects no patterned faces.
  None is waived. Investigate source-geometry/triangulation comparisons test-first
  after the material decision. Never fix source geometry to silence findings.
- VPM preview helper replaces glass material with main UDIM material; its preview
  is diagnostic, not authoritative glass appearance. Correct before acceptance.
- No native DWG/rib-count comparison sheets, final SINTEZ, user visual acceptance,
  final full suite, or publication is claimed. Address/GeoJSON remain unavailable;
  `Prg_1` / `0000` are explicit temporary naming tokens.

## Tests and repair log

RED commit `70966b7`: 5/5 new build mapping witnesses failed (missing build spec).
After the spec: 5/5 passed. Final focused run: **16 passed in 0.31 s**:
`uv run pytest -q tests/jobs/test_tec26_ac06_build.py tests/test_tec26_ac06_materials.py tests/test_tec26_ac06_isolated_ids.py -p no:cacheprovider --basetemp=C:/x/t_6af403e8-focused`.
Includes all 11 opaque IDs, separate glass handle, all 23 nodes, duplicate/empty/
partial node partition refusal and four unmapped-ID failures. These are not
architecture/export acceptance tests.

Repair 1: native Blender adapter run failed with `KeyError: finish` in glass
`pack_uv`; added the required BMesh finish layer and reran in a fresh build-r1
folder successfully, then ran the complete build-v002 pipeline successfully.
No retry or repair of the model-authority conflict was attempted.

## Durable evidence and resume

All 82 diagnostic build files copied to
`G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v002-diagnostic/`.
All **82/82 SHA256 hashes** verified after copy; `SHA256SUMS.txt` there,
copy in `build-v002/DRIVE-SHA256SUMS.txt`. Binaries are not in git/LFS.
Only small JSON QA/adapter/readback receipts and hashes are committed.
Local raw logs: ignored `tmp/ac06-build/`.

Resume: answer upper-fascia question; update build mapping only with that answer;
obtain native DWG facade images and measure rib count per facade if applicable;
repair/extend job-local export coverage probes and glass preview without shared
script refactoring; rebuild to a new version; run complete acceptance comparisons,
full suite through suite_slot, eval receipts, push and open one PR based on the
AC08 parent branch. Do not request review of this diagnostic snapshot.
