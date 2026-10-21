# Skolkovo L4 — resume v011: approved plan executed, live reference access needed

**Incomplete production. `passed=false`. No final master/export/review/PR.**

## Immediate question (not another Gate1 or tolerance request)

May the worker perform a **read-only live Revit reference audit**, and can Artem
open the copied September `СК_ИЦ_ЦОД02_П_АР.rvt` with the Revit MCP bridge enabled?
Path: `C:/x/l4-skolkovo/01_source/02_pravki_2026-09-15/rvt/`.
If the roof families belong to the sibling `_АР_Ф.rvt`, use that copy instead.

Need native family/solid and face/ring decomposition of the five primary masts
and108 KNS instances after initial execution plus three distinct primary repairs
failed. Five FBX label IDs:6631253/6640426/6640949/6641475/6677027; they are NOT yet
verified Revit IDs. This is reference-only, not FBX geometry replacement, not
permission to save/export/edit, and not a guarantee that it fixes the mesher.

`revit_exec.py --ping` exit2/WinError10061 at documented127.0.0.1:7891; independent
TCP10061, no Revit.exe rows,0 offline IFC inputs. Wrapper/version/live-only policy
checked; no config/token/addin/app/document changes. The card explicitly requires
asking before a needed live Revit run; no headless or guessed-port fallback.
First identify actual application/document/units/version and match the source
families/placements. Stop on an RVT/FBX discrepancy; source/revision FBX placement,
heights and geometry remain authoritative. No user scene has been touched.

## Settled permissions — never reopen them

Artem16:58 accepted canonical PartsList SHA256
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`.
49parts/147000 allocation/291 conditional joints and embedded recipe are unchanged.
Approval-only execution copy SHA256:
`78c0331b2d8ff994f5f7d155c56ef977a0e53acb004e951be19c07111e4d8931`.
`GATE1-APPROVAL-v011.md` records the actual comment;5/5 approval checks and9/9
negative design/actor/hash mutations. The immutable canonical draft is untouched.
Primary bidirectional <=2mm and KNS silhouette<=2cm/target10k remain granted;
opaque glazing/exterior-only and VPM appearance-only decisions also remain granted.

## Actual results, not accepted geometry

- Five source-weld candidates:55230 ->55183tri, exact Z extrema unchanged; both
  whole-surface bounds <=0.002m on every mast, plus separate65536-sample/seed35310
  area-weighted p95 in each direction. All original faces conservatively exterior.
- BODY-J after:1234/1233/1233/1222/1225 vs100. Every candidate is rejected.
- Isolated row3628 `run_operation(contour_rebuild)` rolls back:250 visible borders,
  5448 overlaps, quad383/texel10338 failures. All six before/after counts retained;
  original before receipt reused only after matching source buffer SHA. Not a
  whole49-part kernel receipt.
- Three primary repairs: exact self-union275878tri>55230; broad planar domains
  BODY-J2632/changed Z plus guarded native stall; cap-only domains fail conformance
  on2 unresolved24-vertex circuits. Failed outputs are never used as a master.
- KNS edge-collapse15/108 eligible; true-plane support50/108 eligible. Best measured
  shortlist62/108 remains65524 candidate-or-unchanged triangles vs10000 allocation.
  All108 objects accounted for; shortlist is not applied/accepted output.
- Full report: `REPORT-v011.md`; small summaries/raw-check hashes in `evidence-v011/`.
  There is no proof that further FBX repair is impossible, only these route failures.

## Verified

776 affected tests passed in207.32s; initial bad pytest path (exit4/no tests) is
retained and corrected in a new log/basetemp. Private synthetic tests-first tracers:
profile final6/6, plane/cap domains4/4 each, KNS reducer4/4, conforming quads4/4,
true-plane support4/4, certificate8/8. Generated exact plane controls150/150 and
invalid requests8/8 reject, including exactly-at-limit/NaN/inf/empty/budget controls.
104/104 inventory inputs and113/113 mast buffers unchanged after diagnostics.
Native timeout/owned termination, output-collision refusal, localized taskkill
stdout decoding error and representative regression are preserved, not hidden.

Machine walk exits1 with zero validation errors: inputs/parts pass;
operations/budgets fail; report review; export/readback/visual/checker missing.
A model pass is not inferred from green tests or surface proximity.
Full suite remains for the first complete review head via suite_slot.py;
CI not run (billing lock). No new library/shared module/Git LFS.

## Restore and next steps

Drive supplement: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v011/`.
`evidence-v011/index.json` pins the archive, approval-only JSON and restore guide;
CRC, full member hashes and independent Drive readback are required. Restore
older v008/v009/v010 packages first where needed, then v011 over its new tmp paths.
Use current Git job files rather than historical archived checklist snapshots.
This supplement contains raw failed candidates and113 source mast buffers, not
all6955 building buffers or original FBXs. See earlier restore guides for those.

After permission/access: read-only live native-family reference through
`revit_exec.py` with its session lock; do not start/open/close the user's Revit.
Recover source-bound closed side/cap domains and remeasure topology/profile and
all six invariants; no blanket threshold or unknown-face exemption. Complete
KNS10k, then actual49parts/contacts, measured master, versioned exports + clean
FBX readback, source/album/delivered comparison, board-user visual approval,
complete final SINTEZ, suite_slot/author receipts/one PR/dt-reviewer. A changed
approved design needs new approval, but reference inspection alone is not a
reason to request the same Gate1 again.

GitHub issue353 was manually closed08:18:27Z (no closing commit), before the
later explicit user approvals/continue. This is not L4 acceptance. No issue
state was changed and no PR exists on the branch.

Transcript: Hermes session local-1ec1333a6816497d539322d2dc648c1e2065addd680f0b90aec42b4187903595, task t_b205c8e1, run1150.
