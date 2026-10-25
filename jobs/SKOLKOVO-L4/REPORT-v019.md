# Skolkovo L4 — v019: measured cassette UVs, source-projection repair, revision ownership

**Incomplete; `passed=false`. No final FBX, user visual acceptance, SINTEZ or PR.**
The exact approved proposal remains unchanged at
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`.
No source reference was newly dropped and no budget was raised.

## Decisions retained and delegated aspect decision

- Keep all earlier mast/KNS authorities, repairs and tolerances. Do not open Revit.
- Keep the answered 92-object external-frame exclusion and `from_face` variant B;
  its 15,692-triangle allocation remains mandatory. No closed-box acceptance shortcut.
- Orchestrator, 2026-10-25 22:43, delegated technical decision **pending Artem review**:
  for long thin rectangular cassette profiles, report aspect >8 diagnostically ONLY
  when actual tile fit, texel density and padding are each measured. All other
  texel rules and budgets are unchanged. This is not recorded as an Artem decision.

The shared `inv_texel.py` remains strict and unmodified. The job-specific
[`cassette_uv.py`](cassette_uv.py) recomputes rectangle geometry, all six pair distances
per quad, 1024 px/m isometry, 4K tile fit, 32 px exterior margin and 64 px chart separation.
Missing/duplicated/nonfinite UVs, other part IDs, stale changed geometry, shear, folds,
size failures and insufficient padding refuse. Aspect alone is diagnostic only after
this proof. It does not approve a whole model, material count or final texture inventory.

## New source-ownership question — not the earlier aspect/budget question

The approved retained list contains both baseline and revision objects sharing an
Element ID, not just baseline details absent from the revision:

- **33 one-to-one shared IDs**. **22** also have registered bbox coordinate differences
  <=25 mm and intersection >=90% of the smaller bbox volume. Finite bidirectional
  surface samples corroborate these candidates; they are not continuous identity proofs.
- The other **11** one-to-one pairs differ more, including changed height/type.
- One additional shared ID (`5111482`) is many-to-many and deliberately NOT paired
  or silently deduplicated by ID. Cross-document IDs are not universal instance keys.
- Exact refs, names/types, part membership, bounds and classifications:
  [`revision-overlap.json`](evidence-v019/revision-overlap.json), SHA256
  `55aceaa811773a4750df1b714c72775f67317e49a275df8c46d6055e359d5b8e`.
  [Surface witnesses](evidence-v019/revision-surface-witnesses.json) are labelled sampled.

Examples:

| ID | Retained baseline | Retained revision | Measured discrepancy |
|---|---|---|---|
| 1711687 | insulation 150 | insulation 160 | max bbox coordinate delta 0.0097062073 m |
| 3372758 | floor type 15 | floor type 4 | max bbox coordinate delta 0.0002921143 m |
| 5387772 | glass unit 25 mm | Stemalit RAL 7035 assembly | max bbox coordinate delta 0.0233023682 m |
| 2276473 | insulation 150, source row 54 | insulation 160, revision row 3901 | height 13.40 ->15.75 m; **not** one of the 22 near-coincident pairs |

The progress comment's wall example 2276473 belongs to the 11 changed pairs, not the
22 near-coincident subset. Both are part of the 33 one-to-one retained-ID collisions.
Some pairs change semantic material/part class as well as thickness or height.
Keeping or removing them affects the opaque enclosure, visible material ownership,
receiving context and the source-coverage/drop list; neither choice is just a UV fix.

**Exact question:** For the 33 one-to-one retained baseline/revision pairs in this
hash-pinned census, is the revision the replacement authority (remove each corresponding
baseline ref with a named superseded-by-revision disposition), or are some separate
physical components that must remain? Please identify exceptions if any. After this
answer, prepare/consolidate the exact execution PartsList under Gate 1; do not modify
the already approved proposal bytes or auto-drop the many-to-many group.

This is not a request to raise 150k/15,692, treat opaque glazing as transparent, reopen
mast decisions, or undo the 92 authorized exclusions. September revision precedence
is already specified; the unresolved fact is identity/ownership of these simultaneously
retained cross-document objects in the approved list. No replacement is assumed here.

## Code and regression evidence

1. `silhouette.py` previously discarded edge-on triangles whenever any projected
   polygon existed. A 30 nm source tilt left a 1.49e-9 m2 strip and lost the remaining
   50x100 mm mullion perimeter: a false **82.5 mm** top-view refusal. The repair retains
   lines/points beside polygons, including when polygon grid samples also exist.
   The 70 mm limit and polygon sampling remain unchanged. A missing-fin witness now
   measures its actual 2.0/2.1 m reach rather than incorrectly reporting zero/0.0875 m.
2. `face_on_wall` now supports an explicit source-bound `outward_sign` and <=20 mm
   normal-offset `border_growth_m` for a real opening frame with no solid behind the
   panel centre. Border depth, silhouette and all four operation invariants still gate
   the result; **no opacity exception** is added. Growth refuses changed source
   piece/hole counts, unknown orientation, nonfinite/over-limit values and shallow embed.
   Wrong orientation or a missing opposite enclosure wall still rolls back. A synthetic
   closed-room fixture costs two triangles with opaque geometry and unchanged receivers.
3. Tests-first commits: `47ce565` (UV qualification), `e537ed1` (mixed projections),
   `15d8b31` (opening-panel support). Production commits: `d973707`, `50e913a`.
   Raw RED logs include 1 UV assertion failure, 9 mixed-projection assertion failures,
   a combined polygon/line assertion failure, the missing opening-panel API, and a
   real unwanted source-piece merge before the growth guard.

Final affected command:
`uv run pytest -q tests/ops tests/jobs/test_skolkovo_cassette_uv.py -p no:cacheprovider --basetemp=C:/x/t_b205c8e1-v019-ops-final`
— **598 passed / 113.06 s**. The focused face/opening selection passed **135 / 15.32 s**.
Generated controls: 50 slender rectangles; six room axis/sign orientations with 201
samples per border edge; exact padded tile boundary plus above-boundary refusal;
malformed/empty/partial/duplicate/NaN/inf, wrong-part, input-preservation and reset probes.
Existing band/receiver/embedding regressions remain in the same passing selection.

Full suite/evals/PR receipts remain deferred until a complete first-review head, through
`suite_slot.py` as required; this is not a green full-suite claim. CI: not run (billing lock).

## Real execution — candidates, not a final assembled model

| Stage | Actual result | Qualification |
|---|---|---|
| Exact historical cassette-box unwrap | 2,632/2,632 qualify; 15,792 quad charts; 9,712 aspect diagnostics; strict checker passes only 204 objects | 1024 px/m error <=2.274e-13 px; min exterior padding 32 px; zero global chart-separation failures |
| Packed chart inventory | 99 4K tiles | Actual candidate UV coordinates in `charts-01/charts.npz`; NOT final texture files/count approval; excessive layout remains to optimize |
| Cassette budget | 31,584 / 21,056 tris | Still fails; aspect diagnostics do not waive this |
| Cassette open-end band sample | 0/24 applied | Thin receiving profiles cannot provide required deep embedding, or close-overlap rollback; no threshold reduced |
| Coplanar grid/source-box unions | 31,192 (two failed pieces) / 30,316 tris | Feasibility only; over allocation |
| 3D bbox-union diagnostic, 0.1/5/10 mm grids | 26,238 /24,134 /23,292 tris | Over allocation and nonconforming edges; NOT a proved minimum or accepted geometry |
| 20 mm grid | Refused: collapses a source extent | Preserved failed log; no collapsed input accepted |
| Unchanged from-face context replay | 0/834 applied | Refusals/crowded contexts retained; not an accepted model |
| Source-contour precision repair | 6/23 kernel-applied | Pre-projection-fix diagnostic; not promoted to all-invariant acceptance |
| Repair after projection fix | **12/23 kernel-applied**, 7,296 tris | Six mullions independently pass BODY-J, quad and strict texel (6/6); six other contours still need D129 audit |
| Opaque-opening prototype | 0/2 selected | One ambiguous (both orientations applied), one both rolled back; candidate contexts are not final enclosure evidence |

The opening prototype predates the source-piece/hole growth guard. Its failures and
ambiguity are retained, not recast as current-head geometry passes. The overlap census
is not proof that these source collisions are the sole cause of that ambiguity.

[Arithmetic summary](evidence-v019/summary-v019.json): mixed staged coverage **6,852/6,863**,
**11 unbuilt refs**, **170,537/150,000** staged tris; from-face remains **38,023/15,692**.
These are counts across historical/local candidate contexts, NOT an assembled/exported
measurement. Newly represented geometry raises the arithmetic total; it does not fix
budgets. The old 92-object exclusion remains the only newly authorized drop list.
All **104/104** source/reference inventory hashes were rechecked unchanged.
No DCC/Revit was launched; no source was overwritten, and no final UV/material/UCX,
joined-scene/joint, visual, delivered comparison or SINTEZ receipt was manufactured.

## L5 timing and durable evidence

[Timing evidence](evidence-v019/timings.json) records approximate Windows new-log
birth-to-last-write intervals. Concurrent stages must NOT be summed as throughput:
charts 0.002 h; context replay 0.080 h; cassette band sample 0.004 h;
precision repair 0.033 h; post-projection repair 0.105 h; opening prototype 0.014 h.
Final focused tests have their actual pytest timing above. Final assembly/export/review
hours are still unmeasured, not zero.

The [publication index](evidence-v019/index.json) names the Drive ZIP, its SHA256 and
independently verified member/CRC count. Raw scripts, logs and NPZs are external;
only small text/code/hashes are committed. No Git LFS. The archive pins source code
and tests at `50e913afbb1f5917fb2c0c8196265c4bd0c91c0b` as well as job drivers.

## Resume after the source-ownership answer

1. Keep the already settled decisions. Record the new answer precisely and consolidate
   revision ownership, the 92 exclusions, variant B and the delegated scoped UV rule in
   an exact execution plan. Do not silently mutate the old approved proposal.
2. Rebuild the affected substrates/receiving contexts before selecting panel orientations;
   stale, duplicated or overfilled historical receivers are not final-model evidence.
3. Reuse the 12 hash-pinned candidates, but finish D129 for the six contour candidates,
   repair the 11 named unbuilt refs, replace remaining closed from-face fallbacks and
   solve both local/master budgets without a silent transfer or increase.
4. Assemble actual contacts/conditional joints; measure whole-scene topology and all
   applicable invariants, UV/materials and real texture inventory, UCX/derivations.
5. Versioned FBX, clean-process exported-file readback, delivered/album comparison,
   board-tool user geometry review, final complete SINTEZ, then the slot-controlled
   full suite/evals, one PR and `kanban_request_review(reviewer="dt-reviewer")`.
