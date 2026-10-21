# Skolkovo L4 — resume v009: Gate1 granted, component candidates rejected

**Incomplete production. `passed=false`. No accepted master, export or PR.**

## New blocking question

Read [PRIMARY-PROFILE-TOLERANCE-QUESTION-v009.md](PRIMARY-PROFILE-TOLERANCE-QUESTION-v009.md).
The earlier permissions are settled. The new choice is whether a new retopology
recipe for the **five primary assemblies** may approximate their exterior
surfaces within <=0.002 m, while locking original FBX placement/heights and
principal outlines, or must preserve the exact supplied exterior facets.
This bound is proposed, not granted or achieved. No failed candidate is offered
for acceptance. A changed contour recipe requires a fresh exact-hash Gate1.
No PDF rescale, generic replacement mast or invariant/BODY-J waiver is requested.

Do not reopen interior/opaque glazing, source-vs-PDF heights, VPM appearance-only,
Drive storage, the108-KNS <=0.02 m /10k permission or source-bound topology cleanup.

## Actual Gate1 is now recorded

Artem's Telegram "yes", task comment2026-10-21 13:34, approves canonical
`f1867120b2c7072405d32440a27382a0be8bb2bf9edc56c9fbc2876eb3ff2302`.
Original canonical bytes remain unchanged. The confirmed execution copy changes
only approval metadata; full remaining semantic payload equality is tested.
Confirmed copy SHA256:
`0a002ad56221c1cddeaa6a9a14d97f3b8c29c120f4ff0a8f3c21b5ebc25fe3f2`.
See [approval](GATE1-APPROVAL-v009.md). Approval is not revoked by operation failure.

## What actually ran

Blender5.1.2/ec6e62d40fa9, new headless factory scenes, metric1 m. No Max/Revit/live
scene changes, new library, kernel/checker/tolerance edit or VPM geometry copy.
Initial native Boolean plus three distinct repairs are documented in the
question report, with their source hashes and preserved failed outputs.

- Raw Boolean55,230 ->296,642 triangles: rejected. Exact-filter repair122,610:
  rejected (row3628 defects19,291, zero-length62).
- Source-surface arrangement47,234 triangles on five copies fits55,230 design
  allocation, but every mesh fails BODY-J (2,264–2,564 defects; zero edges23–59).
  Independent kernel on isolated row3628 rolls back:5,705 exposed edges,
  4 lost pixels,29 back-face samples. These are not whole-building contexts.
  Projection loss exceeds a2 cm buffer in YZ/XZ. Never use these as a master.
- Source seam repair262/312/312/286/206 boundary edges ->0, existing source
  vertices only, max3.802 micrometres precision deviation, no new caps. Useful
  source diagnosis, not acceptance: subsequent Boolean still19,295 defects.
- Conservative planar retessellation of arrangement row3628:9,362 ->9,262
  triangles, still2,278 defects/48 zero edges and failed quad/texel checks.
- KNS varying-source-section candidates:103/108 pass cardinal silhouette
  certificates,96 pass quad,15 pass raw topology,5 pass texel checks (independent
  counts, not their intersection). No candidate has whole-scene acceptance.
  Five concave base frames explicitly refused. Candidate-or-unchanged60,826
  exceeds10,000; target is not achieved or proved impossible. Next engineering
  route: componentwise source profiles/face adjacency, not a new user question.

`run_operation` returned `applied=false` /original object for measured candidates.
The49-part master operations and291 actual-contact joint decisions are unfinished.
The immutable plan has not been rewritten to hide a failing count or status.

## Checks, errors and honest gate state

- Focused tests: **773 passed in213.16s**. Selection/command/log hash in
  `evidence-v009/timings-and-tests-v009.json`.
- Approval regression: old draft exits1 ->confirmed copy5/5 checks exits0.
  Nine negative approval/provenance/output-alias/clobber probes reject9/9.
- Synthetic native controls: overlapping cubes volume12/area32; duplicate-face
  regression volume17.333... RED ->12 GREEN; source seam/nonmissing-cap
  controls6/6; planar fan retessellation5/5; variable step-profile regression
  passes. Synthetic data are labelled synthetic, never real project acceptance.
- Diagnostic self-repairs: texel API needs profile `VPM-OKS`, not `VPM`, and a
  distinct `inv_texel.PolyMesh`, not the same-named quad contract. Initial errors
  and expensive failed-run logs remain; a successful source/output-hash-bound
  kernel checkpoint was reused for corrected cheap diagnostics.
- Native limited-dissolve at1e-5 left the planar-fan control unchanged, including
  after normal update. Explicit coplanar-edge/collinear-vertex selection passed
  the original control; it did not fix the real source defects. No false claim
  about the native implementation's internal cause is made.
- **104/104** original copied inputs and **113/113** mast buffers rehashed;
  all104 checked again after Drive publication, unchanged.
- Machine walk actual exit1, zero errors: inputs/parts pass+ready;
  operations/budgets fail; report review; export/readback, visual/checker missing.
  `evidence-v009/procedure-walk-v009.json` is the current walk, not v008.
- Full suite deferred until a complete first review head (rule49), then only
  through the card's `suite_slot.py` command. CI: not run (billing lock).

## Restore, hashes and review path

Drive: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v009/`.
Archive `source-cleanup-v009.zip`: **11,139,823 bytes**, SHA256
`eb3f394c2c214810bafd8b0c5e8c8fe4afe2ffbc31e8d05c1d35e222037f7183`.
Local+Drive CRC and **573/573 member hashes** checked; **5/5** published files
independently rehashed. No readback error. `SHA256SUMS.txt` SHA256
`dca96ef08e609c79abc350c3d45a9f24fcceb0397e96c2938262fd4546c3c9f5`.
Index: `evidence-v009/index.json`.

Archive preserves repository-relative paths, raw113 mast buffers, canonical and
confirmed PartsList, failed candidates, before/after probes and raw logs, all
job-only drivers and their frozen historical snapshots. Original adapter01 was
recovered byte-for-byte and matches its actual recorded native-run SHA.
`RESTORE-v009.md` explains restoring v008 first for the rest of6955 source buffers.
Restore `tmp/` diagnostic data over a checkout; retain the current Git `jobs/`
files. Archived job documents are the frozen measurement snapshot (the current
checklist removes one EOF-only blank line); semantic refs/design are unchanged.
`toolchain-v009.json` pins actual Python/packages/kernel source bytes/revision.

Question image `primary-profile-question-v009.png` was visually checked and
rehashed on Drive. It is clearly a **rejected-candidate diagnostic**, not a final
review sheet, completed board-tool review or user visual acceptance. No final
building review page exists yet. After valid geometry: derive NPM/VPM ->versioned
export/readback/comparison ->board-tool user review ->complete final SINTEZ.

Small v009 receipts and approval/question text use job-local `-text` attributes
to preserve hash-pinned bytes. Actual fresh-Git-blob CLI witness on commit
`eec3ee2ce91922a00efb9baa6994d989d2a01b71`: all evidence verified, zero errors,
exit1/`passed=false` as expected for the failed/open production gates. Record:
`evidence-v009/checkout-portability-v009.json`; raw walk, original record and
driver independently rehashed3/3 on Drive `evidence-v009-portability/`, index
`evidence-v009/portability-index.json`. Final receipt-only commits do not change
the tested checklist or any evidence it references. No Git LFS objects or large
binaries are added to git.

## Partial L5 timings, not whole-building throughput

| Actual failed/component stage | Seconds | Hours |
|---|---:|---:|
| Initial native Boolean, five | 169.123 | 0.046979 |
| Exact-filter/native repair, five | 160.339 | 0.044539 |
| Source arrangement, five | 2110.359 | 0.586211 |
| Conforming-source Boolean, one | 54.397 | 0.015110 |
| Raw source before-invariants, one | 442.493 | 0.122915 |
| Candidate03 invariants/diagnostics, one | 441.918 | 0.122755 |
| KNS varying-section candidates | 82.659 | 0.022961 |
| Focused tests | 213.160 | 0.059211 |

Stages overlapped; do not sum them into a fictional elapsed model-production
baseline. Earlier failed diagnostic API runs, manual interpretation and whole
build/export/visual/checker throughput are not quantified as successful stages.
Full precision and unmeasured stages are in the timing JSON.
