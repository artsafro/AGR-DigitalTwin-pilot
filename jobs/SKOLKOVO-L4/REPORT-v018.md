# Skolkovo L4 — v018 resumed kernel execution and texel-policy question

**Incomplete; `passed=false`. No new delivered FBX, PR, or user geometry acceptance.**

The previous v009/v011 questions in `STATE.md` are historical. The five mast repairs and
108 KNS proxies remain the v015/v016 results; their approved source authorities, tolerances
and budgets are not reopened. Revit/DCC was not called in this continuation.

## Decisions retained

- Artem 2026-10-22 10:37: `from_face` variant B, in neighbour context, not closed boxes;
  its **15,692-triangle allocation is not raised**.
- Exclude all 92 `v1_baseline_external_structure_frame_contour_rebuild` source objects.
  [The exact source-reference/name list](evidence-v018/excluded-external-frame.json)
  records that answered scope decision; no other omitted source is silently dropped.
- Canonical proposal SHA256 remains `fca5b23b4e4939ad44f01abde68d8b510b0daad18c5e7bf3072a22e05fcd0d2a`.
  Its bytes were not rewritten to manufacture approval of new geometry or budgets.

## Implemented and actually exercised

`src/dt_ai/ops/face.py` / `tests/ops/test_face.py`, commit `45598d3`:

1. Keep only the exterior cap when its border is already seated in receiving solids;
   do not add eight unnecessary skirt triangles. A separate fresh-process regression
   against immutable pre-fix `c2edc3b` fails **10 != 2**; the current test passes.
2. `band_between_walls`: retain a source section's sides, hiding contacted end rings
   inside unchanged receiving slabs/walls, with at most 20 mm end adjustment. An
   already buried end may be trimmed into its receiver. One genuinely exposed end
   retains its original cap only with the explicit `allow_exposed_end=True` request;
   this is not a closed-box fallback. No-contact ends are never artificially bridged.
3. Recover actual closed section loops of open-ended source skins, rather than treating
   their zero-area projected side triangles as a missing source. Unsupported loops refuse.
4. Reject duplicate receiver names and a Context override below the 10 mm embedding floor.
   Source/receiver arrays and unchanged receivers are tested for preservation.

The standard operation runner measures four geometric invariants. BODY-J, quad-dominance
and texel readiness are additional checks, **not implicitly supplied by `run_operation`**.
The border invariant uses finite edge samples; these results are not continuous whole-edge
certificates or whole-building acceptance.

### Real source runs

| Run | Measured | Kernel-applied | Candidate triangles | Qualification |
|---|---:|---:|---:|---|
| inherited `run-01` | all from-face parts | mixed faces/closed fallbacks | 40,229 | Historical incomplete prototype, not approved variant B |
| `band-01` | 815 roof skins | 651 | 5,208 | Pre-45598d3 prototype; cached geometry and raw checks retained |
| independent `band-audit-01` | 651 cached bands | BODY-J + quad: 651; texel: **619** | unchanged | 32 texel failures remain; exact oriented triangle inventory preserved when recovering quads |
| `band-02` | 164 previous refusals | 125 | 1,250 | Current kernel, explicit exposed-cap mode; D129/whole-scene acceptance still pending |
| `small-repair-01` | 70 previously missing/refused objects | 33 | 1,112 | Source-derived contour simplification or keep in actual context; not a blanket all-six-invariant pass |
| `aerator-run-02` | 16 named roof aerators | **16** | **3,008** | Each passes kernel, BODY-J, quad and texel checks; 14 are newly represented, two replace older candidates |

Aerator repair evidence retains both failures: the old section recipe loses 110 hole-probe
pixels on source row 7934; a covering interval-envelope recipe fixes the hole test, but its
20-sided version fails texel aspect 9 > 8 on 20 quads. The 16-sided covering version passes
without changing any checker threshold. This is the standard 0.07 m silhouette route for
these roof details, **not** the KNS 0.02 m exception or the primary-mast 0.002 m permission.

### Previously reported missing inputs were a loader omission

The 29 v1 buffers already existed in the same task's v008 `baseline-supplement-v002`.
The v017 driver ignored that supplement. The new job-only loader verifies its buffer hashes,
source indices/names, shape/counts and native bbox facts. All **29/29** are recovered;
**4/4** hash/shape/identity/truncation negatives refuse, with a clean reset control.
The original v1 FBX SHA256 was rechecked. No material slots, normals or UV were invented;
appearance still needs the explicit confirmed PartsList bindings and later export checks.
The first audit command accidentally included the separate rod authority and failed with
`unmapped facts fabc99979d3d`; the corrected audit explicitly selects v1 supplement refs.
The first empty failed output is retained; its `unmapped facts` error is recorded here and
in the task tool transcript, not relabelled as a pass.

## Current arithmetic inventory — not an assembled model

[Machine-readable summary](evidence-v018/summary-v018.json):

- Original retained references: 6,955; user-excluded external frame: 92; in-scope: **6,863**.
- **6,840** have staged historical/local kernel candidates; **23** remain unbuilt, each
  named in the summary. They are unresolved retained objects, **not authorized drops**.
- Mixed staged from-face pieces total **38,023 / 15,692** triangles. Closed fallbacks are
  still present; they do not satisfy variant B merely because a new operation now exists.
- Mixed staged total: **163,241 / 150,000** master ceiling. This is an arithmetic inventory
  across different local contexts, **not** a joined-scene or exported-file measurement.
- No current UV/material/UCX, joined-scene topology, board review or final SINTEZ receipt.

The historical comparison in [REPORT-v017.md](REPORT-v017.md) and its `cmp-v017.json`
remains available: its external structure extended 33.97 m outside the delivered bbox,
which motivated the now-answered exclusion. The 104 source/reference inventory hashes
still match. No new v018 export-to-delivered comparison or visual review is claimed.
There is no final-model review path yet; the v017 FBX is an earlier diagnostic artifact.

## Exact decision needed: slender-strip aspect policy, not a budget increase

`src/dt_ai/ops/inv_texel.py:16,43` explicitly calls **aspect <= 8 an orchestrator default,
with no decision number**, unlike the cited tile/density rules. It has not been waived here.
This real run exposes the difference:

- 32 kernel-clean roof bands fail texel readiness; examples include aspect **18.7 > 8**.
  Some also exceed the 4 m side limit; **that size failure is independent and must be cut**.
- For all **2,632** current cassette-perimeter primitive boxes, geometry-side tile fit
  requires no extra cuts at 1024 px/m, 4096 px, padding 32. **2,428** nevertheless exceed
  aspect 8. Actual UV density/padding is not measured yet.
- They currently cost **31,584** triangles vs the part's approved **21,056** allocation.
  A straightforward conforming Cartesian grid satisfying aspect 8 costs **179,040**
  triangles for this part alone. This is a measured construction-cost calculation,
  **not a mathematical minimum or proof that every other recipe is impossible**.
  [Source-bound diagnostic](evidence-v018/frame-texel-cost.json).

**Question to Artem:** for source-bound long thin rectangular profiles, should aspect 8
remain mandatory (requiring a revised Gate1 representation, e.g. texture baking/simplification),
or become diagnostic-only when actual tile fit, density and padding are demonstrated?
Do not silently choose either. Do not relax the 4 m/tile, density, padding, topology, source,
master 150k or from-face 15,692 limits. This is not permission to apply the KNS exception
elsewhere or to mark currently failed strips passed.

## Tests and probes

- `uv sync`: completed; no new dependency/library.
- `uv run pytest -q tests/ops/test_face.py -p no:cacheprovider --basetemp=C:/x/t_b205c8e1-face-green-v002`:
  **114 passed / 11.59 s**.
- `uv run pytest -q tests/ops -p no:cacheprovider --basetemp=C:/x/t_b205c8e1-ops-focused`:
  **549 passed / 102.96 s**.
- Frozen pre-fix cap regression: **1 expected assertion failure / 0.53 s**, `assert 10 == 2`.
  Initial tests-first commit: `518fdad`. Additional RED logs cover duplicate receivers,
  context floor, missing source section, buried-end trim and explicit exposed-cap support.
  The first positive cap fixture used separate touching receiver boxes: a dense independent
  border probe found their unembedded transition seams. It was corrected to a continuous
  closed ring receiver; the frozen pre-fix replay uses that same corrected fixture.
- Generated bands: ten seeds across all three axes; generated seated panels: 40 seeds.
  Empty/open/unknown/duplicate receivers, unsupported view, NaN/inf/over-limit parameters,
  below-floor embedding, no-contact gaps and input preservation are exercised.
- Copied source/reference inventory: **104/104 hashes unchanged**.
- Full suite: **not run yet**; no complete first-review head or PR. On completion use the
  card's `suite_slot.py --card t_b205c8e1 -- ...` command exactly once before first review.
- CI: not run (billing lock). No user approval, checker pass or missing receipt synthesized.

## L5 timing

[Timing evidence](evidence-v018/timings-v018.json) uses new log-file birth-to-last-write
intervals on this Windows host, so these are approximate wall-clock stages, not CPU time.
Runs overlap and **must not be summed** as total throughput:

| Stage | Approximate hours |
|---|---:|
| Band prototype, 815 objects | 0.645 |
| Refused-band repair, 164 objects | 0.111 |
| Source-complete small repair, 70 objects | 0.350 |
| First aerator before/after probe | 0.026 |
| Corrected aerator probe | 0.024 |
| 16-aerator batch | 0.076 |
| Focused kernel tests | 0.029 |

## Durable evidence and resume

The publication index in `evidence-v018/index.json` records the actual Drive directory,
its checksum-manifest hash and independently verified file count. Scripts, raw logs,
JSONL checkpoints and NPZ candidates are external; only small text/hashes are committed.
The inherited `run-01` and prototype failures remain intact. No Git LFS or source overwrite.

After the aspect/representation decision:

1. Retain all earlier decisions. Consolidate the already authorized 92-object exclusion
   and variant B in the execution plan; do not ask those answered questions again.
2. Complete D129/BODY-J audits for later candidates; retain raw failures. If aspect stays
   mandatory, actual source-bound subdivision/baking needs a revised allocation/recipe,
   not an unapproved threshold change or a silent move between budget buckets.
3. Repair the **23 named retained objects** and replace remaining closed from-face fallbacks
   within 15,692. The staged arithmetic is not the final assembly; do not reuse its counts
   as an exported receipt. Do not re-add either already represented aerator twice.
4. Assemble true source contacts/291 conditional joints, remove witnessed hidden interfaces,
   preserve material identities, measure all applicable whole-scene invariants and budgets.
5. UV/materials, UCX/derivation, versioned FBX and clean-process readback, delivered/album
   comparison, board-tool user geometry review, then complete final SINTEZ.
6. Only at the complete first-review head: suite slot, real eval receipts, one PR ending
   `Closes #353`, push/readback and `kanban_request_review(reviewer="dt-reviewer")`.
