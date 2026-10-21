# Skolkovo L4 — revised source-profile Gate 1 proposal v010

**Request to start a changed recipe, not acceptance of geometry. `passed=false`.**

## Decision already settled

Artem's task comment 2026-10-21 15:19 ("Yes, I permit") authorizes source-profile
approximation of the five primary mast assemblies with **bidirectional exterior
surface deviation <=0.002 m**. Supplied FBX placement and heights stay fixed;
no PDF rescale or generic replacement. Exact preservation of each supplied exterior
facet is not required. Report per mast: both directed max/p95 distances,
defects/mesh vs100, and triangles before/after.

This resolves the v009 tolerance question. Do not ask it again. It does not accept
the failed v009 candidates, relax BODY-J, waive kernel invariants or approve the
bytes of a revised PartsList that did not exist at the time of that decision.
The v009 handoff/question explicitly requires a fresh exact-hash Gate1 for this
changed contour recipe (D111/D124/D125, TASK_TO_MODEL parts gate).

## Exact proposal

PartsList SHA256:
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`

Canonical file:
`G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v010/parts-gate1-proposal-v010.json`.

Recipe SHA256:
`ccfbe7a217b562f226a493981d3514e536967b10bf0046672488faf7ae5ddfba`

Recipe: [primary-source-profile-recipe-v010.json](evidence-v010/primary-source-profile-recipe-v010.json).
The complete canonical recipe text is embedded in the PartsList question answer
and its hash is named in the Gate1 question. Approval binds the recipe, not just
a general word such as "cleanup". The file remains `draft`, `gate1=null`.

### Change boundary

Compared with the previously approved canonical proposal
`f1867120b2c7072405d32440a27382a0be8bb2bf9edc56c9fbc2876eb3ff2302`,
**only policy/Gate1 questions differ**. The public schema has no per-part recipe
parameter field; the hash-bound design is carried explicitly in those questions,
not invented as an unsupported schema field.

All49 part entries,6955 retained source references,291 conditional joint entries,
source inventory, appearance associations and budgets are unchanged. The changed
recipe applies only to `rods_primary_mast_meshes_rod_ladder_contour_rebuild`, source
rows3628/3651/3674/3697/3719. All other48 parts remain unchanged.

Master allocation147000/150000, primary ceiling55230 and108-KNS target10000 are
**not achieved measurements**. KNS <=0.02m source-profile permission remains
unchanged; the v00960826 candidate-or-unchanged total remains a rejected route.
Candidate-conditioned weld/embed recipes still require actual contact measurement;
no artificial bridging, movement of primaries or new budget is authorized.

### Source-profile route and refusal conditions

1. Start from original pinned source buffers, not failed Boolean/arrangement outputs.
2. Recover connected source pieces, true contours and varying sections with source
   face provenance. Remove only witnessed duplicates/internal faces; unknown faces
   remain exterior candidates. A nonclosed winding field alone proves nothing.
3. Retessellate the source-derived exterior within the newly permitted bound,
   keeping supplied world placement, Z extrema and externally visible features.
4. Measure both directed distances. A finite sample maximum, vertex-only check or
   cardinal silhouette is **not** a whole-surface maximum certificate. Use exact
   distance where supported or conservative adaptive subtriangle upper bounds;
   reject uncovered/unprovable cells. Area-weighted p95 is reported separately,
   deterministic seed35310,65536 samples per direction per mast.
5. Check BODY-J at0.002m (combined duplicates/intersections<=100; isolated elements
   and zero-length edges=0), all six mandatory kernel invariants, actual whole-scene
   contacts, quad/texel checks and budgets. Failure rolls back, not a threshold waiver.
6. Preserve source/output hashes and each per-mast before/after result. Then derive
   NPM/VPM, versioned export/readback, delivered/album comparison, board-tool user
   review and final SINTEZ. Component-only checks are not building acceptance.

No new geometry is generated or certified in v010. Distance certification tooling
is a proposed execution route, not an implemented capability or measured max/p95.

## Verification actually executed

- Proposal data regression: old plan fails with "Missing newly authorized
  bidirectional source-profile recipe"; revised plan passes,20/20 negative policy
  mutations rejected (one-sided/sample-only, nonfinite/out-of-bound values,
  source omission, placement/budget/topology changes, stale binding, invented Gate1).
- Existing source/material/joint proposal probe:18/18 checks,12/12 negative rejects.
- Public PartsList/import-order/procedure tests:163 passed in84.81s.
- Read-only rehash:104/104 copied inventory entries,16/16 SHA256SUMS entries and
  113/113 original mast buffers match. Originals were not opened for writing.
- First focused command selected nonexistent `tests/procedure` and ran no tests;
  repaired selection uses `tests/test_task_to_model.py`, with the successful result
  above. Manifest diagnostic spelling `utf8-sig` was corrected to `utf-8-sig`.
  Neither failure changed inputs or acceptance thresholds.
- Full suite deferred to complete first-review head, through suite_slot.py only.
  CI: not run (billing lock). No PR until acceptance is complete.

This is proposal-data validation, **not** a surface-distance, topology, kernel,
export/readback or visual-review pass. Prior failed production evidence remains in
v009; no final model review path exists. L5 timing additions are planning/tests
only; earlier failed/component stage timings remain in RESUME-v009.md.

## Exact question

Approve Gate1 on PartsList SHA256
`fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`
to start this revised source-profile recipe with the already authorized <=2mm
bidirectional bound, unchanged49-part allocations and conditional joints?
This is not a repeat tolerance question and not acceptance of failed geometry.
