# Source Normal restoration: support/permission checkpoint (#1326)

**NOT passed. No new scene, map, topology, replication, PR or review.**
Artem's 2026-11-14 22:13 answer is recorded as [D295] and
`source-normal-approval.json`: restore the original joint relief/bevel; a flat
neutral Normal is no longer a candidate. Do not repeat that material question.
The current native/exported candidate remains **v045**, not a restored result.

## Fresh source-bound evidence

`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/normal-v049/`
contains the diagnostic drivers, raw samples, exact two-owner witness, source
profile, conservative patch budget and `SHA256SUMS.txt` (13 sealed files).
The small tracked receipt is `normal-support-checkpoint-v049.json`.

Picture: `normal-support-diagnostic.png` in that directory. This is an explicitly
labelled **actual source-sample diagram**, not a render or a new textured model.
The source's visual groove remains shown in the earlier v045 actual lit comparison.
The new diagram was opened and inspected; its 10/20-mm boundaries and labels are visible.

- Frozen source/delivery/Bricks1 hashes freshly verified **10/10**, before/after
  the read-only probe. The original source Normal SHA-256 is
  `fee4b9729673835c524130eaf562a088d5560322c0e370feb89bb1a8f93b847b`.
- Replayed actual v045 XYZ/UV readback into the fixed original source-face charts,
  then sampled the frozen delivered D/ERM/N, not a generated neutral field.
- **18 exact output pixel centres / 1,333 source owners / 0 sample refusals**.
  The broad raw-source transfer diagnostic finds 27,260 pairwise role conflicts,
  including 21,062 Normal conflicts. These are **NOT** 27,260 architectural seam
  defects: many compare the old source brick phase with the new course-grid phase.
  Only the isolated bevel-versus-flat witness below is used for the support finding.
- Source wall face **6**, at its mid-height: raw Normal is approximately
  `[92.71,127,249.65]` at **10 mm**, `[62.60,127,237.36]` at **12 mm**,
  `[119.21,127,254.36]` at **17 mm**, and reaches `[127,127,255]` at **20 mm**.
  Thus the original bevel is not confined to the painted **10-mm** band.

### Exact brick-field witness

At output pixel centre `(841.5/4096, 1965.5/4096)`, both native faces are labelled
**brick**, not the isolated joint field:

| Object | Original source face | v045 native face | Chart metres | Required source Normal RGB |
|---|---:|---:|---|---|
| K3_StylobateWalls.001 | 6 | 856 | `[101.0544301487,-0.2033176372]` | `[74.2448271,127,242.0419876]` |
| K3_StylobateWalls.001 | 17 | 945 | `[120.9491669818,-0.2033176374]` | `[127,127,255]` |

For face 6 that point is **11.061539 mm** inward from the original left edge:
outside the currently isolated 10-mm strip. Source tangent headings are
approximately **0°** and **-0.000006283°** in the common chart; this is not a
90° normal-axis confusion. Maximum raw RGB discrepancy is **52.755173**.
One shared atlas pixel cannot simultaneously retain this groove and the other
face's plain brick. Do not paint the groove into the common repeating brick
field or average the two normals. The helper itself does not transport arbitrary
Normal frames; this near-aligned witness is deliberately separate from a general
Normal-baking certificate.

## Bounded alternatives checked; no global infeasibility claim

1. **Paint the original source relief into the current shared atlas.** The exact
   two-owner witness above rejects it, including in the brick outside the joint
   strip. A vertical/horizontal joint-master split alone would leave that witness
   unchanged because neither owner is in the joint field.
2. **Restore only the current 10-mm isolated strips.** The independently sampled
   10–20-mm profile rejects complete source relief: the outside bevel would stay
   absent. Compressing that source profile into 10 mm would change the approved
   physical appearance, not restore it; no such rescaling was applied.
3. **Keep current topology and use disjoint unique patch rectangles.** Even the
   **1,647 joint polygons alone** have **2,902,511.864 px²** raw bounding-box sum
   and **22,993,282.015 px²** with the conservative 32-px total per-rectangle gap,
   versus **16,777,216 px²** in the entire tile, before the common brick field
   and outside-bevel brick polygons. This rejects only that conservative
   unique-rectangle strategy. Equivalent appearance classes, polygon interlocking
   and other layouts may do better; **global one-tile impossibility is NOT proven**.

These checks are source/fit diagnostics, not three failed native exports. No DCC
was called in this resume; existing native scenes and all maps were left intact.
The next candidate still has to prove fit, topology, density, Normal transport,
all-map intervals and exported readback. No extra tile or density change is chosen.

## Exact scope question

`geometry-cut-approval.json` currently permits new planar cuts **at the inner
boundaries of the 10-mm panel joints**. The source-bevel support extends beyond
that boundary into brick; treating the material answer as permission to create
new geometry boundaries there would silently widen the existing cut permission.

**Recommended next experiment:** on a new versioned copy, permit minimal planar
partition cuts at the **measured outer boundary of the original Normal bevel**
(about **20 mm from the source edge on the explicit face-6 witness**, not a new
universal seam width). Keep the **painted joint 10 mm**, original relief scale,
main courses, fixed density, one tile, original surface and protected finishes.
Report every changed cut location/count and before/after metrics. If that does
not fit, stop with alternatives; do not introduce a second tile automatically.

**Question for Artem:** authorize those bevel-support partition cuts, or require
a no-new-cut UV-only alternative (with tile-budget changes still needing separate
approval)? This is NOT the already answered neutral-versus-relief question.

## Verification and continuation

- `8de88274` RED: source sampler absent; `8f01134f` GREEN.
- `bb104610` RED: all-map reuse audit absent; `4d879490` GREEN.
- The initial sampler assertion compared exact least-squares floats; it exposed
  `50.000000000000014` versus 50. The test now uses a numeric approximation,
  without rounding the production samples or weakening an acceptance threshold.
- New public helper: `tools/materials/course_grid_appearance.py` —
  `new-case: source-bound joint appearance sampling before atlas reuse`.
- Generated affine source-sampling probe: **100/100**, seed **1326**; explicit
  all-pair reuse, empty/partial/unknown/duplicate, NaN/inf/boolean/range/outside and
  exactly-at-RGB-tolerance controls. Finite compatible samples never return
  `passed=true`. This helper has no file writes or alias/publication promises.
- The recovered D295 row initially preceded D292 and failed
  `tests/test_decisions.py::test_log_format`; repaired by moving **our own row**
  after D293, not weakening the increasing-ID test or copying another card's IDs.
- Affected suite: `uv run pytest -q tests/test_course_grid*.py tests/test_decisions.py
  tests/max_tools/test_agr_tools_vpm_layout.py --basetemp=C:/x/t_d517d7c6-affected-normal-v049b
  -p no:cacheprovider` → **249 passed / 1 deselected / 0 failed**, 16.24 s.
  Full suite/evals are deliberately not run before the incomplete pilot's first
  real review request. No CI or delivery acceptance receipt is claimed.

After the scope answer: preserve v049 evidence; use **v050+** for new plans/scenes.
Keep the earlier **102 expanded PNG discrepancies** in scope, including four
thin-stair traces that are not automatically licensed topology paths. Continue
current carrier/junction and all-map coverage, correct the saved Blender preview's
DirectX green link, final export/readback and final picture. Then finalize the
reusable executable driver, merge current main without rebase, reconcile reserved
D-ids, one slotted full suite, author/eval/hostile receipts, push, one PR and review.
Earlier seam/cap/ring/visual-direction decisions and the four-face source stair
baseline [D292] remain settled. Source/accepted files and protected ID7 stay untouched.
