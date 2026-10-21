# SKOLKOVO-L4 — real building intake (issue #353)

Object: Engineering Centre of Sberbank, TsOD02, `0809_BolshoyBulvar_64`.
Input copies: `C:/x/l4-skolkovo/`; originals are read-only and were not opened for writing.
Profiles: both NPM and VPM from one <=150,000-triangle master (D010).
Base: pilot `48e2a55`; #348 and #351 are closed. No building output is approved.

## Current status — v007

**108-component cleanup permission recorded; primary-mast topology decision needed.**
`passed=false`, `buildable=false`, no Gate 1/build/export/PR. Current report:
[RESUME-v007.md](RESUME-v007.md); exact question:
[PRIMARY-MAST-TOPOLOGY-QUESTION-v007.md](PRIMARY-MAST-TOPOLOGY-QUESTION-v007.md).

The 46-part diagnostic now separates five primary `keep` meshes (55,230 source
triangles) and 108 permitted `contour_rebuild` components (10,000 allocated).
Schema-valid allocation 146,750 is NOT measured geometry or final PartsList:
face/legend/joint reconciliation remains open. Policy regression old v006
6/10 pass -> v007 10/10; 311 focused topology/reader tests passed in 15.62s.

Read-only source QA exposes BODY-J/V004 conflicts in the five unchanged primary
meshes: combined defects 1,302/1,307/1,307/1,296/1,292 vs limit100 per mesh.
Six original strict crossing witnesses plus six clean controls rule out merely
counting coincident triangles. Repairing the five is not authorized by the answer
about 108 additional components. No topology threshold was weakened or waived.

Two analytical projected-profile preflights give counts88,708 / 85,212 for the
108 components, not achieved output or proof that all source-profile methods fail.
No new 3D model was built. Drive evidence-v007b has source-only sheet, 135-member
verified ZIP and 4/4 independently rehashed artifacts; original104/104 and source
mast buffers113/113 unchanged. All diagnostic processes ended; no DCC launched.

Transcript: Hermes task t_b205c8e1, resume after task comment2026-10-21 12:00.

## Historical v006 status — superseded by v007

**Material authority answered; full mast-system membership/cleanup decision needed.**
`passed=false`, `buildable=false`; no Gate 1, kernel/export or PR.
Current report: [RESUME-v006.md](RESUME-v006.md).
Exact new question: [MAST-MEMBERSHIP-QUESTION-v006.md](MAST-MEMBERSHIP-QUESTION-v006.md).

The old mast budget counted only five parent-like meshes (55,230 triangles).
Audit found 108 separately exported КНС_* components, adding 90,168 triangles:
113 meshes / 145,398 triangles for conservative full keep. The corrected source
proposal allocates 226,918 and is rejected by PartsList's 150,000 limit. Exact
duplicate counting and strict planar-retessellation feasibility do not validate
that plan. No extra components are silently dropped or rescaled.

Recommendation needing approval: keep the five parent-like meshes unchanged;
allow bounded simplification of the 108 extra components (source placement,
silhouette <=0.02 m, proposed 10,000-triangle allocation). Only proven coincident
surfaces may be deduplicated; shifted base receptor heads are not automatically
mistakes. This is NOT Gate 1 or a measured output budget.

VPM appearance-only authority is recorded, with explicit SHA-pinned swatch
proposals and original finish names retained, no geometry copying or defaults.
Baseline roof decks/caps/access omitted by the facade-only revision are now
inventoried; native baseline selected geometry bbox checks passed 11,834/11,834.
The 32,961-row scope table and 45 homogeneous candidate parts remain unapproved;
face/legend/joint reconciliation is not a completed gate.

Evidence on Drive `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v006/`, index
`evidence-v006/index.json`: source-only question sheet, 30,799,389-byte archive,
11,991 verified archive members and 11/11 Drive rehashes. Original inputs 104/104
unchanged. Focused tests 133 passed; membership regression v005 3/8 fail -> v006
8/8 pass; over-budget PartsList correctly rejected. No full suite before the
first complete review head. All three serial headless Max runs completed;
the user's live Max 2024 scene was not changed.

## Historical v005 status — superseded by v006

**Partial intake; needs explicit material authority for unmapped exterior finishes.**
`passed=false`, `buildable=false`; no Gate 1, kernel/export or PR.
Current report: [RESUME-v005.md](RESUME-v005.md).
Exact user question: [SOURCE-MATERIAL-QUESTION-v005.md](SOURCE-MATERIAL-QUESTION-v005.md).

Interior/opaque glazing and preserve-FBX masts are answered, NOT reopened.
Mast draft operation is now `keep`, reserving the actual 55,230 source triangles;
the incomplete 20-group subset allocates 134,166 triangles, not measured output.
1,695 facade rows, source supersession, material legend and joints remain open.
The source-material witness identifies twelve exposed rooftop-substrate walls,
not an arbitrary request to pick colours. The current subset is NOT for Gate 1.

Drive: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/`; binaries and 11,631-member
source-diagnostics ZIP are hash-verified there. Only small text/index files are
added to git. LFS quota is no longer the blocker; no history rewrite in this run.
Checks: old mast-policy draft 4/8 fail -> v005 8/8 pass; 133 focused tests pass;
104/104 original input hashes unchanged; 12/12 Drive artifacts rehashed.
No DCC subprocess was started by this run. Full suite waits for first review head.

## Historical v004 status — superseded by v005

**Interior policy answered; new roof-mast source-choice question before production.**
`passed=false`. See [current diagnostics](RESUME-v004.md) and
[the exact source question/sheet](SOURCE-QUESTION-v004.md).

Artem's job decision: **exterior shell ONLY; drop the whole interior with a
per-object drop-list; glazing OPAQUE**. Full authority and boundaries are in
[DECISION-2026-10-21.md](DECISION-2026-10-21.md). The historical question in
`RESUME-v002.md` must not be asked again.

Runs 981/988 prepared 32,961 source-row proposals and an explicitly incomplete
20-group PartsList subset (81,496 allocated triangles, not measured output).
1,695 facade rows, v1 supersession, legend and joint reconciliation remain open.
Corrected source-only Max dump: 11,510/11,510 bbox checks pass; the rejected
second-transform dump fails 11,510/11,510. Duplicate-name draft references were
replaced by hash-pinned census-row locators: 5,267/5,267 unique. 133 focused reader
tests pass (5.02 s), 104/104 original inventory hashes unchanged.

The revision PDF labels M4 h=8 m / M5 h=12 m; two similarly positioned FBX families
are named 10.4 m. Actual vertex extents and provisional registration are recorded,
not equated with pole heights or silently rescaled. A source-authority decision
is needed; no final PartsList is ready for Gate 1 yet. No kernel/build, final
export, post-build visual publication or SINTEZ ran. Full suite is reserved for
the first complete review head; no PR is open. Raw diagnostic buffers/drivers
remain local; hashed data and question PNG are committed locally under evidence-v004/.
Push is externally blocked: repository LFS budget exceeded, 0/6 PNG objects uploaded.
See RESUME-v004.md publication blocker. Do not claim the new commits are remote.

### Previous attempt (historical; superseded where the resume report says so)

Attempt 965 stopped after two Blender startup crashes; build had not started.

The v1 structure read completed (exit 0): 17,710 mesh objects, 6,644,287
triangles, 73,110 bbox contacts, 709 shared components; every mesh has zero
material slots. Elapsed: 1,388.938925799972 s = 0.38581636827777 h.
`source-summary.json` is committed; the full 26,008,630-byte facts file stays
in the local evidence directory. This is not an exterior-only master or a
budget-compliant decomposition. Name-only classes must not be accepted blindly
(e.g. `Railing АР_Витражный отлив_500мм` is labelled glazing by the name reader).

The initial bulk driver also attempted the revised site-fence file: Blender
rejects its ASCII FBX (exit 1). The fence is outside this building run; do not
convert it or expand scope merely to make the bulk driver green.

After v1 succeeded with the environment repair, the **in-scope lightning-rod
FBX** launch crashed again, exit 11, `EXCEPTION_ACCESS_VIOLATION`, at the same
address `0x00007FF6FCE42509` in `blender.exe`. See the two preserved crash logs.
No third Blender attempt was made. The pure-Python PartsList CLI was cancelled
and produced no output; all subprocesses started by this run were stopped.
Remaining revision, delivered-reference and operation stages are incomplete.

Resume after the environment blocker clears: reuse the hashed v1 facts, rerun
`python -m dt_ai.parts.readers.fbx` with `--fbx` verification, finish in-scope
revision/delivered readers, reconcile the materialless v1 and drawing legend,
then prepare the actual per-part operation/budget proposal for user Gate 1.
The default all-keep reader draft must not be approved as a 150k master.
The stage timings are partial intake baseline measurements, not L5 completion.
No user Gate 1 decision exists for this building. The orchestrator's selection of the
building is not approval of a PartsList (D125; `docs/procedure/TASK_TO_MODEL.md`).

## Evidence and reproducibility

Local run directory (this worktree): `tmp/skolkovo-l4-v001/`.
Drivers: `tmp/l4_intake.py` (hash inventory and isolated Blender structure readers),
`tmp/l4_album.py` (C5 page readings plus text and rendered page images).
These are read-only extraction runs, not kernel operation or delivery receipts.

- Full copied-package inventory: 104 files; all 16 entries in the supplied
  `SHA256SUMS.txt` match their computed SHA-256 values. `inventory.json` records
  every copied file, including files outside the supplied checksum manifest.
- Inventory role labels are **path-based**, not semantic classification: source 7,
  album 1, delivered NPM 3, delivered VPM OKS 54, Ground excluded 37,
  package metadata 2. In particular the revised site-fence FBX is inventoried
  but is not authority to include site fencing in the building.
- C5: all 26 album pages and all 4 revision-PDF pages return extraction status
  `ok`. This is NOT an acceptance pass: all 30 have unknown scale, no extracted
  axes and no extracted dimensions. Revision pages 3/4 have 3/2 level marks;
  no metric check can be claimed with unknown scale. Individual JSON readings,
  page text, PNGs and `album-summary.json` are saved locally.
- C5 per-page read/serialize/render elapsed time: 50.954157300060615 seconds
  for all 30 pages (not human interpretation time). `timings.json` records
  separate measured inventory/structure stage times; unexecuted stages are not zero.
- Existing focused tests: 133 passed in 6.83 s:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py --basetemp=C:/x/t_b205c8e1`.
  No code fix is claimed; there is no RED/GREEN regression claim.
  Full suite is reserved for the first complete PR/review head per rule 49.

## Source facts and risks

A read-only binary-header traversal of the v1 FBX found version 7400,
17,714 `Model` nodes and 6,822 `Geometry` nodes, with **no `Material` nodes**.
These are FBX node counts, not a PartsList or a mesh/triangle census.
Blender's importer reports invalid material indices reset to the first material
(641 warning lines observed). This is an importer fallback, not a valid material
mapping or authorization to use the first slot. Do not use it as a material pass.

The initial Blender launch crashed with `EXCEPTION_ACCESS_VIOLATION`, exit 11.
A second run uses a worktree-local TEMP/TMP/TMPDIR and `--threads 1
--disable-autoexec`; a separate factory-startup preflight passed with Blender
5.1.2, empty `Scene`, unit scale 1.0. Both attempts' logs are kept locally.
The running structure reader uses a new isolated headless process, not a live scene.

## Drawing observations — provisional, not approved part decisions

Rendered images inspected: album page 18, revision pages 1 and 3. Page 18 is the
first-floor plan at 0.000, with functional-room colours; its colour boxes must
not be treated as facade material IDs. The plan shows overall axes 1–7 =
46,000 mm and A–E = 36,000 mm; these require a source-geometry comparison.

Revision page 1 marks a plinth-material change and an added mullion/stemalite
infill on facade 7–1. Revision page 3 explicitly adds roof lightning rods
(M1/M3/M5 h=12 m, M2 h=10 m, M4 h=8 m); protection-zone circles/lines are
annotations, not building geometry. Inspect exact locations at full resolution.
Album page 15 text lists facade legend Ф.1–Ф.10; the revision text describes
curtain-wall profile RAL7015 where the original album lists RAL7004. Follow the
specified September revision round, retaining the discrepancy in the report;
do not silently treat the May album and September source as identical versions.

## Gates still open

1. Finish structure extraction, produce/validate the source draft PartsList and
   reconcile source coverage, exterior/internal scope, repeated components,
   operation/budget per part and material legend/joints.
2. Obtain **user Gate 1 confirmation of that exact version/hash** before build.
3. Run kernel operations and mandatory before/after invariants; record real
   measurements, not declared success.
4. Versioned export and clean-process readback; compare to delivered NPM/VPM.
5. Publish actual comparison review through the review tool; user visual decision.
6. Final SINTEZ after visual approval, complete report and L5 timings per stage.

No new kernel ops, data mappings, approval receipts or external review publication
have been invented. No source, delivered reference, live DCC document or shared
review queue was modified.

Transcript: Hermes session local-334de4f92d4c06367dea20c1a18d8e87059b355379b917979a59a8a1f655a249 (task t_b205c8e1, run 965).
