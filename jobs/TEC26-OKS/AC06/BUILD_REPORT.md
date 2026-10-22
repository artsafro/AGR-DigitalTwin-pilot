# AC06 build-v006 — built for review, NOT a passed AGR delivery

## Current result and authority

The prior fascia question is answered. Latest card comments (Artem, 2026-10-22
16:37–16:39): slide39/40 govern; vertical upper fascia is blue5015 sandwich,
walls are light-grey7047 sandwich with the SAME vertical-rib profile, sloping
roof remains7004. The explicit roof answer is retained even where slide39's
projected top strip is blue. The comparisons show that difference; it is not
retouched or called an exact visual match. Full geometry is the approved source.

`bash jobs/TEC26-OKS/AC06/run_build.sh C:/x/tec26-oks/AC06/build-v006`
completed with exit0, Blender5.1.2 headless, fresh processes for ZIP FBX readback.
Source model3dsMax2026.3 copy in metres; no source scene saved or edited.
`materials.json.production_build` supersedes historical Gate-1 solid-grey text;
the original Gate-1 approval/scope is not reinterpreted as build acceptance.

## Measured files and coverage

- Main: all3118 source vertices,2954 source polygons retained in the master;
  both exported profiles5596 triangles; source IDs retained in master `srcid`.
- Glass: all24 vertices/6 polygons,12 exported triangles, map-free, alpha0.5.
  Delivery's normalized main material is one slot; source Multi/Sub IDs are
  **not claimed to survive as FBX slot numbers**. IDs are recorded in the master.
- VPM has21 UCX (516 triangles), NPM has main+glass and no UCX. Cap tessellation
  uses only original corners; no hull rebuild, weld, vertex move, or ring cut.
- Current regions: 300 grey sandwich polygons,262 blue sandwich polygons
  (85 ID1 +177 ID2, including all39 faces of three canopy components).
  Below-zero drop remains plain7047 on the same ID10, minimum−2.025103807m.
- VPM full Diffuse/ERM/Normal4096 for both sandwich colours; plain finishes256.
  NPM one2048 RGB diffuse atlas plus2048 RGB `_o_`, embedded; no delivered normal.
- **924/924** exported patterned triangles measured **999.9583–1000.0841px/m**
  (target1000, strict measurement band±1%); zero UV overflow in all7 finish tiles.
- **5596/5596** main triangles map to the correct presentation region in BOTH
  VPM and NPM, with0 wrong finishes; every source polygon's directed boundary
  and positive projected triangle area are covered exactly. Glass and all21 UCX
  receive the same complete original-corner/boundary coverage check.
- `audit_build.py .../build-v006 tmp/ac06-slide/audit-v006-final.json`:
  **104/104 measured checks pass**. This is a building-specific build audit,
  **not** the public full-delivery validator or SINTEZ.
- Public `dt qa xview` on master, exported VPM, exported NPM: **0 contact/area
  face pairs,0 overlapping vertices,0 bowties**, each exit0. CLI default local
  profile is NPM; the retained AC08 per-profile mesh_report checks also run.

## Pictures and count boundary

Drive `G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v006/`:
`contact-sheet.png` has12 swatches, labels outside. Four `compare/facade-*.png`
plates are slide|VPM|NPM at42.6px/m; `compare-cavity/` additionally shows actual
geometry edges using Workbench cavity shading (not painted texture borders).
Uncropped `renders/` includes the full below-zero drop and iso views.
The comparison viewport is z≥−0.23m; this crop does not delete model geometry.

Nominal grid0.20m from slide spacing (~8.53px per rib,465px/10.9m and575px/13.5m):
**55 /55 /68 /68 full facade bays** for A–D/D–A/1–3/3–1. These are reconstructed
full grid bays including occluded positions; **a pixel-perfect count of all
visible strokes is NOT certified**. Windows, doors and pipes occlude lines.
Independent `export-grid-probe.json` reads both actual exported UV sets:
888/888 vertical sandwich triangles per profile preserve the0.20m grid;
maximum phase residual1.39µm. Full rib centres within measured wall spans are
55/55/68/68 in BOTH exports. This proves grid count/phase, not hidden pixel strokes.
Supplement: `G:/Мой диск/AGR-evidence/tec26-oks/AC06/build-v006-grid-probe-v001/`
(2/2 files SHA256 verified; original143-file build manifest is unchanged).
No image is submitted as Artem-approved or as a certified exact visual match.

## Remaining public validation failures — not waived

Both `tools/qa/validate_package.py ... --json --scene` runs exit1; raw reports
are retained. VPM machine stages3 pass /3 fail /1 review /5 not_run; NPM4 pass /
2 fail /0 review /2 not_run. Pending manual reviews are listed in those reports.

- VPM V001: missing GeoJSON; actual address/coordinates are not supplied.
- NPM V001: one-building ZIP has1 FBX, no mandatory whole-site Ground FBX.
  This card builds AC06, not the complete site's final combined delivery.
- V004 in both: public validator reports6992 duplicates/self-intersections;
  its broader topology metric is NOT the xView contact-pair count above. It also
  retains a clearance review (8937 projected pairs, including widely separated
  faces). No threshold/checker/source geometry was changed to hide those results.
- VPM V010:4 existing UCX piece intersections (2.2/3.8mm); all source corners
  and source polygon coverage are unchanged. Fixing the source UCX is outside
  the explicit colour-only authorization; no silent geometric repair was made.
- Temporary `Prg_1`/`0000` names, user visual acceptance and final SINTEZ remain
  open. No `passed=true`, publication-ready status, or final checker pass claimed.

Unchanged shared AC08 `qa_packages.py` has72/98 passing checks,26 failures:
no-glass name assumptions, polygon-count equality despite requested UCX
triangulation, old one-finish-per-ID mappings and density contract assumptions.
The raw report is retained, NOT rewritten green. The AC06 audit names each
replaced inapplicable check and supplies a complete stricter source-bound probe;
all other raw checks (including UCX convexity/xView/PNG/budgets) remain active.
Its strict raw schema requires all98 check keys, literal boolean statuses and
an exactly matching failed-summary list; malformed/partial evidence is refused.

## Regression and repair evidence

- `7258f8f` RED:3 failures for missing presentation region function; then GREEN.
- Additional observed RED: ID2 fascia1 failure; canopy top1 failure; supporting
  cap fan1 failure; map module6 failures; audit coverage1 failure; raw-schema3
  failures. Final focused run: **34 passed**, including historical Gate-1 tests.
- v003 exposed untextured ID2 faces over the fascia; all broad vertical faces
  and complete canopy components now share the correct sandwich finish.
- UCX004 BEAUTY cap residual14.59µm exceeded the1e-5m supporting-plane bound.
  Source-corner fan selection passes the SAME bound; no vertex moved. Real-source
  negative/control regression keeps concave geometry fail-closed.
- Hostile fresh-process probes **5/5**: declared raw failure remains failure;
  truthy `fail` and empty checks refused; report hardlink/input alias preserves
  source bytes; existing report and `.partial` sentinel not clobbered. Snapshot
  regression rejects duplicate inputs and input rewrites; non-finite/exact-bound
  and missing/duplicate/reversed triangle probes reject without a pass.
- Non-final suite attempts were stopped for audit self-review and the final
  author-receipt/docstring freeze; no success is claimed for those snapshots.
  Owned native pytest/uv children were checked absent before each restart.
  The one completed final full-suite receipt belongs in the PR.
- Regression evals: tmp/evals/report.json;0 passed /0 failed /10 not measured
  (no Claude transcript); exact receipt validation exit0. Missing telemetry is
  not substituted with pytest counts or fabricated transcripts.

## Storage, resume and status

Only small text, hashes, source geometry dump and code are in git. Older verbose
v002 diagnostic JSON receipts are now kept only in their already verified Drive
folder (82/82 hashes); the retained historical manifest still identifies them.
New evidence is versioned separately and verified after Drive copy. See
`BUILD_MANIFEST.json` and `DRIVE-SHA256SUMS.txt` for paths and exact artifact hashes.

Next: independent review of the material/UV implementation and comparison plates;
Artem's explicit visual acceptance before final SINTEZ; preserve the public
validator failures and resolve final whole-site packaging/metadata separately.

---

## Historical blocked attempt (superseded by the answered question above)


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
