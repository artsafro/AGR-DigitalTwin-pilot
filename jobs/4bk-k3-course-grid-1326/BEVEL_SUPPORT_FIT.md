# Wider-bevel support fit checkpoint (#1326)

**Historical v050–070 snapshot. Budget question answered 2026-11-15 [D304]: two sequential tiles allowed.**
Continue at [TWO_TILE_NORMAL_RESULT.md](TWO_TILE_NORMAL_RESULT.md); do not ask the budget or bevel-cut question again.
Current canonical citations are D309/D303/D304; immutable earlier evidence retains D293/D297/D301 spellings.

The following numbers and NOT-applied statements describe the earlier snapshot, not the current candidate.

**NOT passed. No new native scene, pilot texture, production UV or replication.**
The outer-bevel cut question is answered [D303]: minimal planar cuts on a NEW
copy at the measured original Normal support are authorized, preserving the
10 mm colour band, original relief scale, courses, frozen density, surface and
one tile. Do not repeat the earlier Normal, seam, cap/ring, visual-direction or
source-stair-baseline questions. Opening remains only on Artem's «открой».

## What was actually exercised

Scenario `oks-vpm`, level `full`. Offline Python/NumPy/Shapely plus the existing
`course_grid_native`, `course_grid_cut`, `course_grid_fit` and `uvlayout_core`
were used for source sampling, planar partitions and bounded fit. This phase
needs no live DCC: refusing an incomplete one-tile plan before a native write
preserves Max and the accepted/source scenes. No Blender/Max session was touched.

Evidence root: `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/`.
Continuation receipt: `bevel-fit-checkpoint-v070.json`; evidence `normal-v070/`.
Actual measured packing diagram (NOT a render/model):
`normal-v067/support-fit-NOT-A-MODEL.png`, visually inspected. Small preview is
`normal-v067/support-fit-preview.webp`.

- The original renderer was replayed into **diagnostic** `normal-v051`, not into
  the delivery. It is NOT an exact source oracle: Normal is byte-equal at
  16,754,227/16,777,216 pixels; the sparse differences remain recorded.
- Frozen delivered Normal is authoritative. Its RGB is compared with the
  independently normalized original-renderer no-groove base. Actual signed
  relief is recovered from that frozen image, rather than painted neutral.
- 92,386 active raw residual pixels include **158 one-byte differences outside
  measured bevel support**. These are explicitly unclassified quantization,
  NOT authority for extra cuts. Classification before layout reduces the
  guarded source cells from 116,919 to **116,437** and support components from
  852 to **803**. Earlier v052–060 layouts are superseded diagnostics.
- Classified support occurs on **719/771** source faces; summed area **9.582495
  m²** is not unique union/padding usage. The final footprint also includes the
  independently read frozen colour mask; colour remains owner-side 10 mm,
  intended centre 5 mm inward. Normal support is NOT a new colour-seam width.
- All **771** source identities have a planar partition; **0** partition errors,
  no dropped source faces. A conservative **2 mm support-boundary guard** and
  **1 mm contour simplification** are explicit planning parameters; original
  corners/XYZ are not moved. A fit is not a native topology/surface certificate.
- Pure `sample_chart_field` keeps signed floating fields without RGB clipping;
  `compose_relief_normal` preserves the source additive-slope recipe and
  transports explicit encoded R/G tangent axes. DirectX/OpenGL convention is
  explicit, not silently flipped. These helpers do not write files or certify QA.

## Fresh bounded fit results

Frozen input **512.1 px/m**, 4096 px, 32 px gap and border; no rotation, mirror,
scale search, density fallback or automatic extra tile. Brick repeats still use
**48 × 3.15/38 m** and the unchanged Bricks1 maps.

| Strategy | Fresh saved result | What it establishes |
|---|---|---|
| v069: independent unique support components; 8 px conservative contour grid, longest-extent first | **191/803** placed, **612** unplaced | This bounded no-reuse strategy fails; all unplaced keys are reported |
| v063: source-affine/full-repeat equivalence groups; 4 px conservative contour grid, area first | **235/751** groups placed, **516** unplaced; all **803** members assigned to groups | This stricter appearance-lookup catalog also fails one tile; not every possible appearance-equivalence solver |
| v064: READ-ONLY second-page alternative for the v063 leftovers | **751/751** groups, **803/803** members; **0** missing/duplicate keys | Two-page geometric proposal fits; **tile 1002 is NOT authorized or applied** |
| v066: READ-ONLY additional plain-brick repeat-grid cuts using existing `uvlayout_core.cut_grid` | **370** segments on **324** sources; brick union 8,353,080 → **4,151,891 px²**; still **306/751** groups placed, **445** unplaced | This broader-cut option is unapproved, still incomplete and NOT recommended as a guaranteed one-tile solution |

Heuristic/catalog failure is **NOT a proof that one tile is globally impossible**.
The catalog may miss partial/local appearance reuse. Within the tested disjoint
classes the two-page padded unions total **135.539320%** of one tile; raw support
area alone hid the padding cost. No change of budget or broader cut scope was
silently selected.

### Independent saved-proposal readback

`normal-v068/independent-proposal-readback.json` reloads saved placements, resolves
all member identities and measures exact Shapely geometry. The minimum gaps below
are actual nearest-class distances (`query_nearest`), not merely the minimum of
pairs selected by a 32-px broad-phase probe.

| Counterfactual page | Classes | Raw union | Padded union | Minimum border | True minimum class gap |
|---|---:|---:|---:|---:|---:|
| 1001 | 236, including shared brick | 58.533447% | 86.318366% | 32.813296 px | 34.246865 px |
| 1002, NOT applied | 516 | 11.588167% | 49.220954% | 49.319789 px | 34.879003 px |

These are **fresh proposal geometry measurements**, not fresh native density,
Normal-baking, xView, exported-FBX or delivery-acceptance numbers. Native v045 is
unchanged; its earlier measurements stay historical in `PNG_REPAIR_RESULT.md`.

## Verification and retained failures

- Tests-first commit **b5c0f417**: 3 RED missing-API regressions; implementation
  **2b0d26ab**, then signed-field, invalid/partial/nonfinite/unknown-frame,
  OpenGL/DirectX sign and generated 100-rotation probes.
- Latest affected command:
  `uv run pytest -q tests/test_course_grid*.py tests/test_decisions.py tests/max_tools/test_agr_tools_vpm_layout.py --basetemp=C:/x/t_d517d7c6-affected-relief-v070 -p no:cacheprovider`
  → **274 passed / 1 deselected / 0 failed**, **17.47 s**.
- Initial affected run: 272 passed / 1 failed because D303 lacked its area-sheet
  anchor. Added the real [D303] policy to `uv-atlas.md`, did not weaken the test.
- Actual source replay through the helper: **1,000/1,000** sampled active points;
  all **92,386** active vectors have max unit-vector error **7.8682e-8** against
  decoded frozen Normal. Source RGB triplets are not exactly unit vectors:
  re-normalizing/re-encoding changes one byte at **1,773/12,048,897** covered
  pixels. That byte error is retained, not hidden behind an exact-RGB claim.
- The first replay check wrongly required byte identity after normalization
  (v056 assertion). Replaced only that self-oracle with the independent decoded
  unit-vector comparison and retained the byte result (v058/v065/v068). This
  changes no accepted physical, seam, density or anisotropy threshold.
- Optional OpenCV/SciPy were missing: isolated `uv run --with` dependencies;
  script import root fixed by `PYTHONPATH=.`. No global install or lockfile change.
- The v057 counterfactual refused native-quality triangulation. The subsequent
  broad-cut experiment uses constrained **chart-only** triangles: no native
  density/topology certificate follows. A source-generation comment produced
  v059 `IndentationError`, fixed in v060. v060/v066 then saved their complete
  partial layout before a final-print `NameError: fail`; exit remains **1**, not
  pass. The v066 artifact was independently parsed (751 unique group keys,
  306 placed + 445 unplaced), not promoted to a successful model.
- Frozen sources **10/10**, existing v045 scene and FBX **2/2** unchanged by hash.
  New source fields, diagrams, drivers, failed logs and seals stay outside git.
- No full suite/evals/PR/review yet: this is an incomplete production pilot, not
  its first review head. No CI or final-delivery receipt is claimed.

## New decision needed — budget, not the answered Normal/cut question

**Recommendation:** allow **two tiles for this stylobate-brick pilot**, keeping
source relief, 10 mm colour joint, courses, density, surface and protected IDs.
The saved two-page proposal fits geometrically; it still requires real map
baking, versioned native construction and all remaining QA.

**Question for Artem:** authorize that two-tile budget, or keep one tile strictly
and continue a different appearance-reuse/cut strategy? The tested 370 extra
plain-brick cuts do not solve one tile, so they are not presented as a painless
working alternative. No extra tile/cut is applied until the answer, per [D309].

This is NOT a request to waive the **102** expanded independent PNG findings,
the four thin legacy-trace classifications, all-map support/interval/Normal-frame
checks, source/protected preservation, final native/export readback or final
picture. These remain repairs on this card, not out of scope. The reusable
executable finalizer and final receipts/PR are also still due; the new pure
sampling/transport helpers alone do not complete that acceptance point.

After the answer preserve v050–070 evidence and use **v071+**. If two tiles are
approved, the candidate changes from the original one-tile target only by that
explicit new decision. If one remains strict, discard the counterfactual budget,
keep this as a bounded failed catalog and try other appearance equivalences
without claiming impossibility or lowering density. Earlier approvals remain.
