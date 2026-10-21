# Skolkovo — primary exterior-profile tolerance question (v009)

**Gate 1 was approved. The approved design is unchanged. No candidate is accepted.**

## New question — not the earlier cleanup permission

May a **new source-profile retopology plan for the five primary assemblies**
approximate their exterior surfaces by **at most 0.002 m**, with supplied FBX
placement/heights and principal outlines fixed, or must every supplied exterior
facet remain geometrically exact apart from source-coordinate precision?

This is a proposed quantitative bound for contour approximation, not permission
already inferred from "cleanup/weld/retessellation, preserving exterior profile".
It allows no PDF rescale, generic replacement mast, missing silhouette feature,
waiver of BODY-J or lost-pixel/other kernel invariants. A new contour plan would
need its own exact-hash Gate 1 before execution. The present rejected candidates
are **not** offered for approval under this bound.

**Recommendation:** permit the bounded, source-derived profile route (<=2 mm),
then measure it; retain the current exact source as the authority. Feasibility
under that bound is not yet measured or promised. If exact exterior facets are
required, retain this run as failed and plan a different exact-surface repair;
never relabel the failures as a delivery pass.

The <=0.02 m permission for 108 separate KNS members is separate and unchanged.
Their target10,000 is also unchanged; this question does not relax it. Interior,
opaque glazing, VPM appearance authority, FBX-vs-PDF mast heights, storage and the
previous topology-cleanup permission are already settled and are not reopened.

## Execution after the actual approval

Artem's Telegram "yes", relayed on task `t_b205c8e1` at 2026-10-21 13:34,
approved proposal SHA256
`f1867120b2c7072405d32440a27382a0be8bb2bf9edc56c9fbc2876eb3ff2302`.
See [approval](GATE1-APPROVAL-v009.md).

The canonical file is unchanged. A separately hashed confirmed execution copy
changes only `status`, `gate1` and the first question's approval answer; the entire
remaining payload compares equal. Confirmed copy SHA256:
`0a002ad56221c1cddeaa6a9a14d97f3b8c29c120f4ff0a8f3c21b5ebc25fe3f2`.

### Initial failure plus three distinct repairs, not repeated blind retries

| Route | Real measured outcome | Decision |
|---|---|---|
| Initial: exact empty-collection self-union on five raw copies | 55,230 ->296,642 triangles; first mesh33,350 exact duplicate triangles and1,291 zero-area triangles | Reject native exit0; no kernel acceptance |
| Repair1: exact duplicate/degenerate filtering before/after native Boolean + planar dissolve | Five candidates122,610 triangles. First mesh BODY-J19,291>100,62 zero-length edges; kernel rolls back201 open borders and1 close overlap | Reject; no reduced-budget or topology pass |
| Repair2: actual source-surface intersection arrangement, classify internal cut cells against source winding; then planar retessellation | Five candidates47,234 triangles fit55,230 allocation but BODY-J2,264–2,564>100. First mesh kernel rolls back5,705 open borders,4 lost pixels,29 back-face samples. Retess first mesh9,362 ->9,262 triangles still2,278 defects /48 zero-length edges | Reject. A nonclosed source winding field is not sufficient to classify genuinely hidden geometry |
| Repair3: reconstruct nonconforming source boundary seams using existing source vertices, recalculate copied normals, then exact Boolean | Source boundaries262/312/312/286/206 ->0 with no new source vertices or cap faces; maximum precision deviation0.000003802 m. Result on first mesh24,751 triangles, BODY-J19,295>100 and62 zero-length edges | Reject. Fixing source seams is useful but does not validate the subsequent Boolean |

Every route was preceded by a failing synthetic tracer and passing corrected
control. Synthetic positive controls are capability tests, not real-asset
acceptance. No source, kernel tolerance or official check was weakened.

These were isolated source-component kernel scenes, not the full49-part building
or a completed operation on the five-source master part. The real
`run_operation` on row3628 returned `applied=false` and the original mesh object
(`rollback_identity=true`) for both measured candidates. A surviving checkpoint
was reused to add corrected polygon-contract diagnostics; no failed geometry
was accepted.

### All five source-arrangement candidates

| Rods source row | Triangles | BODY-J defects | Zero-length edges |
|---|---:|---:|---:|
| 3628 | 9,362 | 2,283 | 48 |
| 3651 | 10,629 | 2,403 | 31 |
| 3674 | 9,588 | 2,264 | 59 |
| 3697 | 8,730 | 2,564 | 37 |
| 3719 | 8,925 | 2,528 | 23 |

Row3674 also has one isolated polygon. All five remain rejected. Raw
self-intersection counters became zero, but duplicates, collapsed cells, exposed
borders and profile loss prevent acceptance. Topology-count reduction alone is
not enough.

Independent cardinal region-distance checks additionally reject the current
row3628 arrangement at a2 cm source-to-candidate buffer in YZ/XZ; containment
holds at7 cm. This is **not** the proposed2 mm route. It demonstrates why
"no overlap" cannot be obtained by discarding externally visible source cells.
The raw interval probes are preserved, not reported as an exact Hausdorff value.

### KNS target remains unachieved, not a new user question

The first executed varying-section source-contour route produced103 cardinal
silhouette-eligible candidates of108; the five5,306-triangle concave base frames
were explicitly refused, not silently dropped. Candidate-or-unchanged total:
**60,826 vs10,000** (34,296 generated candidate triangles +26,530 retained source
triangles). Of108,96 meet the quad check,15 meet raw topology limits,5 meet texel
readiness; none has whole-scene acceptance. These are independent counts, not
an intersection of passing objects. Next engineering route is componentwise
source-profile reconstruction; no minimum achievable count has been proved.

## Evidence and status

Drive: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v009/`.
Question sheet: `primary-profile-question-v009.png`; it is a diagnostic of a
**rejected** candidate, not the final board-tool visual gate. Committed small
index/measurements: `evidence-v009/`; full drivers, candidates, logs and source
bindings are in the hash-verified archive named there.

Focused kernel/topology/FBX/C5/PartsList tests: **773 passed in213.16s**.
Approval regression: old draft exits1 ->confirmed copy5/5 checks exits0.
Nine negative provenance/no-clobber probes reject9/9;104/104 input hashes and
113/113 original mast buffers are unchanged. These checks are not a master pass.

No full suite yet: no complete first review head (rule49). No final export,
clean-process delivery readback, actual building review page/user approval or
SINTEZ. No PR. `passed=false`; accepted source inventory and Gate1 are not revoked,
but operations and measured production budgets remain failed/incomplete.
