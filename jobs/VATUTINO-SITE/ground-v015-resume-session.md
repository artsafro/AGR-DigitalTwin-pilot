# Ground v015 resumed construction checkpoint — #371

**Historical checkpoint.** The localized notch question was answered by Artem on
2026-10-21 16:58 [D169]. See [approved-notch session](ground-v015-approved-notch-session.md)
for the applied correction, real native readback and the remaining VPM policy
question. The measurements below remain historical; this was not a delivery.


Artem resumed #371 on 2026-10-21. Start: `95ea3be`; merged `origin/main@08b3cb9`
via `863dcd1`. The decisions-log conflict contained independent additions (D156/D157
versus D158–D163); both were retained. No thresholds, budgets, D150 exceptions,
material priorities or source files were changed. Code checkpoint: `d5631211535c79b7d03518d166318a0618e4623e`.

## Measured result and required decision

The current-head real-size replay improves **ours xView 0 OV / 13 OF → 0 OV / 1 OF**
at the unchanged **0.002 / 0.005 m** thresholds. The remaining pair is Skirt/Skirt,
`kind=area`, gap 0 at a shared edge. Contact-rule selection is empty; this does
**not** constitute a native Max measurement or a pass of the stricter area gate.

Top corners of the remaining wedge (metres, world XY/Z):

- A = `(-7691.007, -15248.688, 152.017682)`;
- B = `(-7691.2305, -15248.001, 151.996786)`;
- C = `(-7691.016, -15248.688, 152.017123)`.

It is the acute end of **source-derived footprint hole 0**, not an invented shader
or checker failure. Its cross-section widens from zero at B to **9 mm** at A–C.
The proposed, **NOT executed/authorized**, local closure is triangle A–B–C in XY:
**0.0030915000000045403 m²**, of which **0.0027793467728598753 m²** lies in the source
void. A 1001-position sample of the new closing edge reaches **4.317305 mm** from
the original outline, beyond the existing **2.2 mm** open-edge tolerance.
The safe seam weld itself leaves **one** open base edge **2.402023 mm** off outline
(coordinates recorded in the JSON), versus zero on its predecessor. We cannot call
this pass, silently alter the authoritative footprint, or loosen the tolerance.

**Question for Artem:** may this exact tiny source-footprint notch be closed and
recorded as a localized approved contour correction (with all numerical thresholds
unchanged), or must the source contour remain? No such patch has been constructed.

The **59** edge-disconnected vertex-fan risks remain unchanged: 10 single-slot
and 49 cross-slot contacts. These are indexed-mesh diagnostics, **not native Max**
counts. No fan splitting/displacement was used. Any later bridge ownership across
materials must be explicit; this checkpoint does not pick a winning material.

## Construction changes (opt-in; production CLI not integrated)

1. `ground_details.fit_curb_bottom`: fit only the underside to the actual raised
   cake along its face normal. Overlay extrema bound every intersecting supporting
   plane; top, XY, indices and texture slot remain fixed. Maximum actual trim:
   **4.398461 mm**, below the unchanged 10 mm tolerance.
   This removes all six Curb/Mulch and Curb/LawnReinforced pairs.
2. `ground_cake.weld_base_boundary`: target **measured** curtain defects only,
   midpoint-weld implicated boundary corners, and refuse movement reaching 2.1 mm.
   Five groups move by at most **1.503198 mm**;
   five of six Skirt pairs disappear. Interior and upper-sheet fans are not split.
   The 4.1 mm candidate search is a construction parameter, **not** a changed xView
   tolerance. The new one-edge outline failure remains visible.
3. `ground_details.build_details(..., stair_clearance_m=.012)`: opt-in analytic
   mitred stair cuts avoid dense round-buffer segments collapsing during welding.
   This removes the Curb/Stairs pair. Retained/trimmed area is reported per curb.
   Default zero preserves the complete ordered legacy result: **9/9** checks,
   **9,980 faces**, **481 dispositions**, actual Vatutino replay.

The prior diagnostic skirt/stair slab clip is still a **diagnostic prerequisite**,
not an integrated production operation. It carries replaced-face dispositions;
perimeter-depth continuity is not certified. `build_ground.py`, the source adapter,
the D150 manifest and the original v014 delivery are unchanged.

## Rejected approaches and repairs (not hidden)

- Fixed-datum underside replay first refused incomplete support at face 2492.
  Adding the **original reference TIN**, not invented terrain, exposed a second
  numerical issue: separately clipped support rings invented a 0.0000013407149 m²
  gap at face 2497. Union-before-clip fixes that without raising an area threshold;
  the exact real-coordinate regression is committed.
- Whole-outline projection: 1,358 moved vertices, maximum 3.992180 mm; **0/8**
  xView with two new TileLight overlaps. Rejected; its implementation was removed
  from production and retained only in the evidence archive.
- Global proximity clusters: refused a 3 mm straight-chain displacement, then a
  2.237463 mm nondefective corner. Rejected. Collinear samples and unimplicated
  corners remain unchanged; the third, defect-targeted route is the retained API.
- A 1 µm stair-noding experiment recognized an additional formerly skipped stair,
  leaving 20.146 m² of old surface beneath the changed footprint and 60 fan risks.
  Rejected; it is **not** in production. The final replay preserves v014 recognition
  and returns to 59 risks. The clearance test uses supported 0°/45° source paths at
  local/world coordinates, rather than claiming to fix unrelated recognition.
- The first exact-boundary probe used `build_flat`, which rounds to 1 µm and changed
  its binary-exact width. Corrected the **fixture** to direct exact vertices; the
  exact movement threshold is now refused as intended. No production limit changed.

## Geometry/budget diagnostics (not acceptance)

| Check | Final diagnostic |
|---|---:|
| Ours OV / OF | 0 / 1 — fail |
| Surface polygons | 20,149 / 50,000 |
| Quads / residual triangles | 19,224 / 8,005 (29.399% triangles) |
| Whole geometry triangle-equivalent, excluding placed MAF/Flora | 46,453 / 180,000 |
| Terrain max error / faces over 10 mm | 9.963067 mm / 0 |
| Projection misses / outside material contours at 22 mm | 0 / 0 |
| Uncovered beyond 2.2 mm / outside beyond 2.2 mm | 0 / 0.000174812795467591 m² |
| Open base edges off outline / nonmanifold base edges | 1 / 0 |
| Below-5-mm normal gaps, vertices / centres | 0 / 0 |
| Above-20-mm raw samples, vertices / centres | 18 / 6 |
| Same-level overlap | 0 m² |

The raw 18/6 above-band counters and the minimum normal gaps are identical on the
predecessor diagnostic and this candidate. The source v014 rebuild report also has
18/6 raw counters; these are **not** a claim that 18 unique vertices were accepted
by D150. Geometry-bound D150 re-pinning and unique-sample verification remain open.
Full silhouette/detail deviation, export tessellation, UV, native topology and
per-input-face final dispositions remain uncertified.

| Texture slot | v014 triangles | Candidate quads | Candidate triangles | Triangle share |
|---|---:|---:|---:|---:|
| CurbGarden | 9844 | 4703 | 426 | 8.306% |
| FlowerBed | 134 | 49 | 36 | 42.353% |
| Gravel | 618 | 220 | 178 | 44.724% |
| LawnReinforced | 1311 | 500 | 311 | 38.348% |
| LawnRolled | 2088 | 677 | 734 | 52.020% |
| Mulch | 3263 | 1140 | 983 | 46.302% |
| Pebbles | 291 | 76 | 139 | 64.651% |
| Skirt | 3578 | 1790 | 89 | 4.737% |
| Stairs | 100 | 64 | 8 | 11.111% |
| TileDark | 509 | 220 | 69 | 23.875% |
| TileLight | 21603 | 8559 | 4480 | 34.358% |
| TileRed | 3004 | 1226 | 552 | 31.046% |

This is logical scratch-array inventory only. Triangle reasons and Max/Blender
material-ID readback are **not certified**; the fixed 12-ID specification remains
`ground-material-ids-v015.json`, not a readback receipt.

## Verification and provenance

- `uv sync` completed once after integration.
- Tests-first RED commits: `e2af6a5` (2 failures, underside API), `0bede30` (1 real
  overlay failure), `6b8eee6` / `66333d0` (2 perimeter failures), `feecf26` (1 straight
  chain failure), `d9b2598` (1 unrelated-corner failure), `af6573d` (4 clearance API
  failures), `0f433d4` (2 missing-slot failures). Guards now reject empty, partial,
  unsupported, NaN/inf, unmapped curb slots, blank slots and exact displacement/
  trim boundaries without mutating inputs.
- Final focused verification: **225 passed, 0 failed, 11.87 s**:

```text
uv run pytest -q tests/test_ground_perimeter_straightening.py tests/test_ground_curb_support.py tests/test_ground_stair_clearance.py tests/test_ground_xview_construction.py tests/test_ground_pairing.py tests/test_ground_quads.py tests/test_ground_v015_budget_decision.py tests/test_ground_surface_requirement_sheet.py tests/test_ground_cake.py tests/test_ground_details.py tests/test_ground_cleanup.py tests/test_ground_review_r1.py tests/test_ground_review_r2.py tests/test_ground_gap_exceptions.py -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/resume-focused-final
```

- Three current-head replay commands exited 0; their measured gate still fails:

```text
uv run python tmp/resume-boundary-targeted-v002.py
uv run python tmp/resume-mitred-legacy-inventory-v002.py
uv run python tmp/resume-legacy-final-gates-v002.py
```

Restore archive entries only into a **fresh** scratch workspace; verify recorded
input hashes before use, never overwrite source assets. The `tmp/` programs retain
read-only absolute source paths. The archive supplies copies under `inputs/` for
verification, not authorization to replace those sources. Replays require the
frozen `tmp/resume-curb-fit-reference.npz`; the source-preserving predecessor and
all programs needed for the final replay are included. The old construction program is reused only
for its recorded skirt-clip snippet; do not run its obsolete two-return-value main.

Archive: `G:\Мой диск\AGR-evidence\371-ground-v015-resume-20261021\rejected-checkpoint-evidence.zip`  
SHA-256: `b2282d5e69dc51a84137e448026f08775ccbc240668580a26f1da2e8bcd29912`  
`SHA256SUMS.txt` is adjacent; **5479115 bytes**, no Git LFS.
Rejected noding outputs are separately retained in `G:/Мой диск/AGR-evidence/371-ground-v015-resume-20261021/rejected-stair-noding-supplement.zip`
(SHA-256 `6d40898f39510bf9d3e77a2efdddbfd916a398c7c3ef969ab40b81b1080320ea`; 1005044 bytes).
Its `EXPERIMENT-ONLY.txt` records the uncommitted noding delta; current code does
not reproduce that rejected alternative without it. Both hashes are in the adjacent manifest.
Every main-archive member was read back and checked against the input inventory, and
input hashes were rechecked after freezing. Source mesh hash matches the preceding
checkpoint; adapter hash matches the v014 rebuild report. Exact residual faces,
all 59 fan coordinates/slot groups, metrics and file inventory are committed in
`ground-v015-resume-evidence.json`.

No native Max/Blender run or full suite was spent on a known rejected candidate.
The first-review full suite through `suite_slot.py`, DCC readbacks, D150 re-pin,
triangle reasons, profile UV/material IDs, UCX/placement and review publication
remain open. **No PR/review request; no `passed=true` claim.** The next action is the
localized source-contour decision above, not another blind mesher session.
