# #1315 — bounded source continuation v005/r3

**Not complete, not delivered; `passed=false`.** Cells: `ground-npm` and
`ground-vpm`. This is a real exported-model checkpoint, not final Ground, UCX,
MAF or Flora acceptance. No PR/review is requested while construction acceptance
is incomplete.

## Authority and identifier reconciliation

[D281] records Artem's G1–G3 approval:
https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6872153353.
The fixed 7.597235 m2 polygons may use nearest-source-TIN linear continuation;
driveway wins over lawn; rubber follows actual AutoCAD redraw order; footprint
33FBD7A is the OKS cut-out; canopy/entry surfaces follow adjacent source surfaces
as disclosed assumptions. These answers are closed, not asked again.

Intervening main allocations reused the branch's former D279/D280 for unrelated
issues. The guard caught both before push. Only this branch's decisions were
renumbered: zero/5.6 m/pilot plan is now [D282]; first-fragment geometry and the
conditional lawn/#1316 instruction is now [D283]. Dates, answering URLs and scope
are unchanged. Historical external evidence is immutable and can still contain
the old local identifiers. D272/D275 remain unchanged. No main decision was edited.

## What was actually built and read back

- Fresh factory Blender **5.1.2**, metric scale 1; isolated headless processes only.
  `max_exec.py --ping` was unreachable; no live user scene was opened or saved.
- Source modelspace redraw order was read with `entities_in_redraw_order()`.
  The nested rubber block also has a redraw table: its hatch colour sequence is
  30, 252, 18, 18; reordering its two colour-18 children does not change the union.
  The original former pink wedge remains actual Rubber18, not a lawn assumption.
- Approved plot: **12958.738864 m2**; footprint: **3389.939224 m2**;
  final budget operand: **9568.799640 m2**. No fitting to the TEP table.
- Canopy source gaps assigned adjacent materials by longest shared boundary:
  **200.393329 m2**, individually recorded in the external buffers. This is the
  approved adjacent-surface assumption, not use of roof hatches as paving.
- Method-C base lawn beneath remaining unhatched slivers: **1.268965 m2**,
  explicitly a visual/material assumption, not source-certified lawn. Of that
  unhatched extent, **0.011239226 m2** is outside the original approved TIN-extension
  polygons. It was **excluded**, not extrapolated under the old permission.
- One global source/TIN/3 m-grid partition replaces independently clipped seams.
  Flat arrays precede Z-only projection; same master for both profiles. Final
  numerical noding grid is 3 mm; 24 snapped vertices are re-anchored to the existing
  authorized domain, never used to enlarge the extrapolation region.
- [D154] steep-layer correction is Z-only: 32 upper vertices / 174 faces raised,
  maximum additional raise **3.503748 mm**, maximum upper offset **9.503748 mm**;
  co-directional residual **0**, no over-20-mm vertices. This is not smoothing
  the source relief or deciding C37.
- Actual exports: Ground **59885 triangles** in each profile; six copied Acer
  **60 NPM / 6420 VPM triangles**. NPM total **59945**, VPM total **66305** for this
  incomplete composition only. No deletion or invented geometry to fit a budget.
- Fresh-process readback verifies counts, finite vertices, all-triangle exports,
  one UV channel, **UnitScaleFactor=100**, and 6/6 seating/height controls per
  profile. Max sinking error **5.337e-9 m**; height error **2.218e-7 m**.
  VPM vegetation is joined into the Ground mesh; the diagnostic vegetation-name
  failure is removed. No appearance/map acceptance is inferred.

The native top/oblique renders are in `v005/r3/`, not synthetic substitutes for
an unavailable run. The top render was visually read: footprint void and surface
layout are coherent, six grey maples are visible, remaining MAF/Flora are absent.
The complete site image is **not accepted**.

## Bounded repair attempts and actual failures

1. Shared adaptive partition: a 240 s timeout; instrumented replay localized the
   long loop to `_refine_relief/_insert_points` and was stopped. No result claimed.
2. Global partition at 1 mm exposed a numerical TIN singularity: near-collinear
   contour endpoint triples produced a roughly **2360330 m** height explosion.
   An actual-source regression failed before correction. The correction removes
   only **30 numerically singular TIN faces**, total projected area
   **4.998312e-8 m2**. All **1670/1670 original controls** remain covered with
   maximum Z residual **0**. No source point/mark or library mesh was removed.
   The same regression then passed. The 10 m sanity probe is explicitly a
   numerical-explosion witness, **not** a new relief-compliance limit.
   Stable 1 mm candidate: xView **795 faces / 1594 vertices**, not a pass.
3. Global 3 mm discretization: first refused 16 out-of-domain snapped samples;
   returning them to the authorized domain fixed the numerical miss, not the
   permission. Intermediate xView **296 faces / 0 vertices**. Completing the
   Method-C base only over the authorized domain and applying existing [D154]
   removed the source-sliver curtains and steep-stack contacts.

**Final public xView, on both exported FBX:** **0 overlapping faces / 0 overlapping
vertices / 9 bowtie vertices**; exit **1**, not a full xView pass. The overlap
postcondition is zero, but the nine bowties remain worker-owned. A hash-pinned
witness list names exported and master vertex identities separately, coordinates,
materials and nearby source hatches. Export-to-master matching initially refused
an assumed index mapping, then a 1-micron match; measured FBX transform differences
are at most 7.51 microns, so the already-used 0.1 mm readback matching bound was
applied. No topology threshold was relaxed. The nine 120-mm diagrams are projected
master diagnostics, not the native full-site render and not approval of a proposed
local shape change. No general proximity weld or silent C40 decision was used.

## Public delivery validators and UCX

| Profile | Machine stages | Actual remaining failed findings |
|---|---|---|
| NPM | 1 pass / 3 fail / 2 review / 2 not_run | skirt perimeter minimum reported 0.006 m; Flora topology counter 162; missing diagnostic diffuse/opacity maps |
| VPM | 4 pass / 3 fail / 0 review / 5 not_run | skirt checker refuses combined face geometry; topology counter 29382; no UCX |

Both validators exit **1**. Skirt nominal depth 1.001 m is **not** a validated
GND-03 pass. Flora source-library counters and different checker semantics are
reported, not filtered away because xView contact pairs are zero. Textures,
proper atlas/UDIM derivation, NPM master pairing, curbs/details and final QA remain
worker-owned; no waiver is requested for these failures.

Actual Ground-only UCX builder attempts excluded skirts/Flora/MAF:

- Full layered envelope: **597 pieces / 6832 triangles**, refused against actual
  incomplete VPM model **66305 triangles -> UCX limit 3316**.
- Base-relief adapter, retaining the need for independent full-envelope distance
  audit: **583 pieces / 6660 triangles**, again refused against **3316**.

No collider FBX was published after either refusal. No fabricated model count,
15k budget substitution or triangle padding was used. Complete actual library
composition must precede the final per-file UCX budget; the present incomplete
composition is not a reason to waive [D012]. UCX is not declared reproduced.

## Library reachability and per-area reproduction

The read-only MAF lookup inspected **3559 files**, **116 ZIP directories**, the
XLSX (**232 nonempty rows across all sheets**) and **931 catalogue identities** with **0 I/O errors**.
None of the 32 site rows obtained a certified article match. An initial broad
numeric substring scan produced false hits in coordinates/triangle counts; the
identity-only scan removed them and retained both audit outputs. This is **not**
proof that opaque native Max labels contain no match. Per `model-maf` Step 2,
Artem must name the object when the audited catalogue does not reach it; no
similar-looking or dimension-only substitute has been placed.

| Area | Reproduced | Remaining value / limit / owner |
|---|---|---|
| Ground | Real source-wide bounded master and both read-back exports; xView contact/vertex pairs zero | 9 bowties / 0 unapproved deviations; skirt/UV/material/details and complete delivery checks: worker. Unhatched material/extra 0.011239 m2 source choice: owner |
| UCX | Two actual shared-builder runs, both fail closed on budget | 6832 or 6660 / 3316 triangles for current composition; worker after complete composition, no waiver |
| MAF | 32/32 source rows accounted for, expanded library identity audit | 0 certified matches/placements; owner names library objects, missing types remain listed; modelling/substitution forbidden |
| Flora | 6 Acer in each profile, fixed seed 1315, numeric controls preserved | Remaining 46 point plants and 4535 hedge plants unplaced; exact cultivar/target checks open; 133 m2 flowerbed remains explicitly unresolved [D275] |

Acer maps remain owned by **#1316**, not another question to Artem. Its latest
instruction rejects Royal Red for this schedule and requests a plain green A101
maple; no restoration approval is invented. Generic Syringa/Hydrangea candidates
are not cultivar-certified by this run. Abies/Red Sunset and unresolved bed species
have no substitute. The historical comparison with #906/#969/#1178 remains in
[PILOT-v003.md](PILOT-v003.md); this checkpoint inherits none of their acceptance.

## One source/library question batch

1. Recommend the Method-C base lawn for the explicitly listed **1.268965 m2**
   unhatched slivers and the same bounded nearest-plane continuation for the new
   **0.011239226 m2** subset. Confirm or name its covering/design heights. The old
   7.597235 m2 permission is not silently expanded; the new subset is excluded now.
2. Which exact MAF library object names/files match this site's articles? For a
   first verifiable placement, one explicit row-to-object pair is sufficient;
   all other unmatched rows stay on the gap list. Recommend **no substitutes**.
   If none exists, explicitly decide how the required MAF-placement acceptance
   should be handled rather than reporting zero placements as completed.
3. For the remaining Flora lower-bound sizes, recommend nominal **1.3 m** lilac,
   **1.1 m** Hydrangea and **0.6 m** hedge plants, each with +/-10 percent inside
   the source bounds (>1.1, >0.9, >0.5 m). Confirm targets and whether the generic
   library Syringa vulgaris / Hydrangea arborescens are intended; otherwise name
   the required cultivar/object or leave it missing. No automatic substitution of
   a cultivar and no invented flowerbed scatter.

These are model/data/library-identity decisions, **not** a request to approve
technical FAILs or final site appearance. Closed zero/boundary/5.6 m/first-fragment/
Rubber18 questions are not repeated.

## Reproduction and handoff

Commands/drivers and real failed attempts are retained under
`G:/Мой диск/AGR-evidence/1315-cold-silikatny/v005/` with SHA256SUMS.
`source-wide-summary-v005.json` records exact values and raw stage findings;
`evidence-v005.json` hashes the durable copies. Original/copy source hashes:
**4/4 equal**. No library/source file was saved or overwritten.

Affected tests: **35 passed** (`tests/test_decisions.py` and
`tests/test_ground_surface_requirement_sheet.py`). The renumbering initially gave
**1 failed / 34 passed** because dates must remain ordered; backfill provenance
preserves the real answer dates without changing them. Final run: **35 passed in
1.48 s**. Actual-source numerical regression RED -> GREEN is separate from these
documentation tests. No shared production module/dependency changed and no final
PR is requested, so the one full suite remains reserved for the completed PR head.
No instrumented whole-run tool-call/elapsed total exists; none is fabricated.

Next: apply the single question batch, update the full-site PartsList, resolve
localized topology/skirt/material/details checks, perform actual certified library
placements, derive atlases and VPM UCX from the complete composition, rerun exported
validators, obtain whole-site visual acceptance, then full SINTEZ. `passed=false`
throughout. Technical QA, user acceptance and publication remain separate.
