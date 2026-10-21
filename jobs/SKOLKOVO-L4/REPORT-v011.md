# Skolkovo L4 v011 — approved profile executed; no accepted master

**`passed=false`. No final FBX, model review page, user visual decision, SINTEZ or PR.**

## Actual permission and scope

Artem confirmed revised Gate1 at2026-10-21 16:58 on canonical PartsList SHA256
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`.
The49parts/147000 allocation/291 conditional joints and embedded recipe are unchanged.
The approval-only execution copy SHA256 is
`78c0331b2d8ff994f5f7d155c56ef977a0e53acb004e951be19c07111e4d8931`.
See `GATE1-APPROVAL-v011.md`. The <=2mm permission and Gate1 are settled; neither is
being requested again. Source/revision FBX geometry remains the authority, VPM appearance-only.

## Five primary source-profile measurements

All original faces are conservatively treated as exterior. None is silently classified
internal. The bound is a **whole triangle-surface certificate**, not the sampled max:
each accepted cell has a common opposite triangle containing three convex-combination
witness points within the bound; convexity bounds the complete cell. Otherwise adaptive
longest-edge subdivision continues; uncovered/uncertain cells reject. Float64 convex-point
bounds include recorded arithmetic slack. The BVH selects candidate triangles only.
P95/max-sample are separately labelled diagnostics:65536 area-weighted samples per direction,
seed35310. Synthetic exact plane controls include exactly-at-limit rejection.

| Source row | Triangles before -> candidate | BODY-J before -> candidate (limit100) | Source->output upper / p95 / sampled max, mm | Output->source upper / p95 / sampled max, mm |
|---|---:|---:|---:|---:|
| 3628 | 11098 -> 11086 | 1302 -> 1234 | 1.996374 / 0.000509 / 0.704052 | 1.994075 / 0.000508 / 0.713760 |
| 3651 | 11940 -> 11926 | 1307 -> 1233 | 1.995962 / 0.000506 / 0.735987 | 1.993790 / 0.000508 / 0.691731 |
| 3674 | 11940 -> 11936 | 1307 -> 1233 | 1.993528 / 0.000509 / 0.735988 | 1.987827 / 0.000505 / 0.658737 |
| 3697 | 10114 -> 10099 | 1296 -> 1222 | 1.997315 / 0.000506 / 0.508087 | 1.992704 / 0.000506 / 0.513666 |
| 3719 | 10138 -> 10136 | 1292 -> 1225 | 1.997320 / 0.000509 / 0.511833 | 1.985960 / 0.000508 / 0.486808 |

All five preserve exact FBX Z extrema. Candidate total55183 fits allocation55230,
**but all five fail BODY-J. No candidate is accepted.** Source/candidate hashes,
certified cell counts/coverage and timing are in `evidence-v011/primary-profile-summary-v011.json`.

## Actual isolated kernel rollback — not a whole-building receipt

Only row3628 was put through the kernel in isolation. Original before diagnostics
are reused from v009 only after exact source-buffer SHA match; the new after state
was genuinely measured. No historical failed mesh is reused as output.

| Invariant | Before raw source count/status | After candidate count/status |
|---|---|---|
| open_borders_hidden | 262 / fail | 250 / fail |
| no_see_through_hole | 0 / pass | 0 / pass |
| no_visible_back_faces | 0 / pass | 0 / pass |
| no_close_overlap | 5331 / fail | 5448 / fail |
| quad_dominance | 187 / fail | 383 / fail |
| texel_ready | 10389 / fail | 10338 / fail |

`run_operation(contour_rebuild)` returns `applied=false`; original scene and source
object identities are restored. BODY-J also fails independently. All six invariants
remain required in the selected whole-building context, which has NOT been executed.

## Initial attempt and three distinct primary repairs

| Route | Observed refusal |
|---|---|
| Initial source-profile weld/retessellation | Surface certificates pass but BODY-J1222-1234 >100; isolated kernel rollback |
| Repair1: weld + native exact self-union |275878 triangles >55230 allocation; exit-zero native modifier is not acceptance |
| Repair2: union all coplanar source domains, then conform/union |10841-triangle pilot has2632 BODY-J defects and changed Z extrema; native representative guard refused first run; corrected retry stalled before conform (first180s timeout, owned retry terminated), no accepted output |
| Repair3: union horizontal source-cap domains only, preserve sidewalls, conform before union |10881-triangle pilot; seam preflight refuses2 unresolved24-vertex circuits, exit1; native union never starts |

No source caps were invented to hide the last failure. Raw source/source-cap mapping,
all errors and candidate files remain in the Drive archive. The three repairs do not
prove that the FBX is impossible to repair, only that these bounded routes failed.
The later protected-representative regression (0.0033165m outside bound) was repaired
test-first by retaining an already-valid extremal target; final synthetic6/6 passes.
It does not retroactively turn any recorded failed candidate into an accepted output.

##108 separately exported KNS components

| Route | Component-eligible | Candidate-or-unchanged triangle total |
|---|---:|---:|
| Historical v009 varying support loft |103 silhouette-eligible only; not full component pass |60826 |
| v011 source-edge collapse + conforming quad subdivision |15/108 |85236 |
| v011 all-axis true-plane support profiles (no epsilon rings) |50/108 |69988 |
| Best measured v011 shortlist, identity matched |62/108 |65524 |

Allocation10000 is **not achieved**. Every object is selected as a measured candidate
or remains explicitly unchanged; there is no silent object drop. Eligible here means
two-way <=0.0199m buffered cardinal silhouette coverage, BODY-J<=100 with zero
isolated/zero-edge findings, quad and texel checks. It does NOT mean whole-building
kernel/contact/material/export acceptance. The mixed shortlist has not been applied.

## Access needed for the next route

Read-only live Revit reference is requested, as allowed conditionally by the card,
to inspect native family/solid and ring/face decomposition rather than infer it from
the failing FBX triangle soup. This is not permission to replace FBX placement/heights
or waive the 2mm/2cm bounds. It is not a guarantee that RVT reference will solve the mesher.

`revit_exec.py --ping`: exit2, WinError10061 at documented127.0.0.1:7891.
Independent TCP connect_ex=10061; CIM returned no Revit.exe rows; the pinned inventory
contains0 offline IFC files. The wrapper endpoint/version and live-only policy were
checked. No Revit was started, document opened, token/addin/config changed or headless
fallback attempted. The external access boundary cannot be repaired within this worktree.

Question: may the worker perform a **read-only live Revit reference audit**, and can
Artem open the copied September `СК_ИЦ_ЦОД02_П_АР.rvt` with its MCP bridge enabled?
If the roof families are in the sibling `_АР_Ф.rvt`, use that copy instead. Five FBX
label IDs:6631253/6640426/6640949/6641475/6677027 (not yet verified Revit IDs), plus
their108 KNS instances. No save/export/edit is requested. First identify app/document/
units/version and match families/placements; stop on any source discrepancy.

## Verification and retained errors

- Affected tests: **776 passed in207.32s**, exit0; command/log SHA in `tests-and-probes-v011.json`.
- Approval probe:5/5 positive checks,9/9 design/actor/hash negatives rejected; draft was RED.
- Native/synthetic tracers: final profile6/6; plane domains4/4; cap domains4/4;
  KNS reduction4/4; conforming quads4/4; true-plane support4/4; certificate8/8.
- Independent exact parallel-plane controls:150/150; invalid proof requests8/8 rejected.
-104/104 input inventory hashes and113/113 original mast buffers unchanged after diagnostics.
- Errors are retained: historical census output collision (no overwrite), first wrong
  pytest directory (exit4/no tests -> corrected new log/basetemp), native timeout/owned
  termination, localized taskkill stdout decoding error with independent process readback.
- Full suite not run on incomplete production; run once on the complete first-review head
  via suite_slot.py. CI: not run (billing lock). No new library/shared module or Git LFS.

## L5 baseline — measured intermediate/failed stages only

| Stage | Seconds | Hours |
|---|---:|---:|
| primary source profile native candidate generation | 0.614866 | 0.000170796 |
| primary native union rejected | 40.126779 | 0.011146328 |
| primary topology polygon+export-triangle diagnostics | 200.816819 | 0.055782450 |
| primary bidirectional certificates + p95 | 133.340496 | 0.037039027 |
| isolated row3628 actual kernel rollback + quad/texel | 128.258734 | 0.035627426 |
| 108 KNS edge-collapse native generation | 8.501305 | 0.002361474 |
| 108 KNS edge-collapse independent audits | 691.481802 | 0.192078278 |
| 108 KNS true-plane profiles+independent audits | 80.658224 | 0.022405062 |
| affected pytest | 207.320000 | 0.057588889 |

These overlapping stages are NOT summed into an end-to-end throughput. Native process
startup and interrupted stalls are not fabricated completed-stage timings. Historical
intake/album/source-plan timings remain in earlier versioned job records. Accepted
whole49-part build, final master, export/readback, delivered/album output comparison,
board-user review and final SINTEZ are **not measured / not completed**.

## Publication and source issue state

Only small text, hashes and storage paths are committed. `evidence-v011/index.json`
identifies the CRC/member-verified Drive archive and approval-only execution JSON.
Restore previous v008/v009/v010 evidence as needed, then this supplement; current Git
job files take precedence over archived checklist snapshots. All candidates remain rejected.

GitHub issue353 is manually CLOSED at2026-10-21T08:18:27Z with no closing commit.
Later user decisions (including16:58 local /14:58Z) explicitly say continue. This
closed flag is not evidence of L4 acceptance; the card is not marked complete. No PR
exists on this branch and no issue/repository state was changed by this run.
