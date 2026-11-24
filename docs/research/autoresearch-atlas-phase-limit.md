# Standing #63 — AC08 NPM atlas phase: detection limit and sign symmetry (OBSERVE)

## Frozen before implementation and measurement

Continues #62 (`research/autoresearch-standing-62@75257229cb561c64bace8250f632c13bc4d694af`, next target 1).
#62 showed the unchanged #61 slide-49 joint oracle flags a native NPM-only **+5 px** atlas UV shift on AC08 v010
(JE 0 → 320) and ignores **+0.5 px**. Open: where between 0.5 and 5 px the oracle starts to fire, and whether a
**negative** shift is caught the same way. This is a detection-limit measurement of an existing oracle, not a new
gate and not an acceptance threshold.

H63: on v010 (accepted visual reference), the oracle is sign-symmetric (JE(+m) > 0 iff JE(−m) > 0 for every
magnitude m of the grid) and its detection limit L63 ≤ 2 px (≈ 20.6 mm at 96.9 px/m), with JE(±0.5 px) = 0.

- Fixture: identical to #62 — four original AC08 ZIPs pinned by #58 driver `d45e1ea44471de876f577b63a403f1be43c118ec`
  (full SHA-256 preflight before and after), slide/checker of #61 `d45346548e06847167b386c2c0c71b50ccdfb18e`
  (oracle rev `543652498f34756feef1a729a364c569b3dc8663`, `joint_count` tol 0.01 m, dark 0.85), historical renderer
  `a1f41ee216ba881ada1d1460e6b67f048446e14e`, per-revision `npm_atlas.json` at the pinned spec commits. Blender 5.1.2
  exe SHA-256 `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5`, headless, no Max.
- Variant (exact): #62 `phase.py` at `75257229` is staged unchanged for `panel_cell`/`scene_state`; a thin
  `phase63.py` applies a signed shift `s/2048` in U to loops of faces wholly inside one `PanelVJ*` cell. Guard is
  symmetric: every shifted U must stay in `[u0 − pad/2048, u0 + size + pad/2048]` (pad 6 px; v010 layout:
  cell 409 = region 397 + 2 × 6), i.e. never into a neighbouring cell. Same float32 readback, geometry/material/
  other-UV invariance as #62. Frozen grid on v010: `s ∈ {−5, −2, −1, −0.5, +0.5, +1, +2, +5}` px plus clean;
  v007 clean only (label order). No other values.
- Single number: `L63` = smallest magnitude m of {0.5, 1, 2, 5} such that for every grid magnitude ≥ m both
  JE(v010,+m) > 0 and JE(v010,−m) > 0; `∞` if none. Median of 3 fresh rounds; per-state JE must have spread 0.
- Verdict: `confirmed` if L63 ≤ 2, sign symmetry holds at every magnitude and JE(±0.5) = 0 in every round;
  `refuted` if a valid run gives L63 > 2 or an asymmetric magnitude or JE(±0.5) > 0;
  `inconclusive` on label-order failure (needs v007 clean JE > v010 clean JE = 0), spread > 0, parity/coverage,
  timeout or budget stop. ±1 px (≈ 10.3 mm, just above the 10 mm tolerance) is the expected boundary: recorded,
  not bounded beyond the verdict rule.
- Positive trigger witness: v010 +5 px must reproduce #62 JE 320 (expected direction up; any other value is
  recorded as a replay discrepancy and makes the run inconclusive). Accepted control on which the rule fires:
  v010 itself (accepted visual reference, #559 comment 6345392389) under the injected shifts. Rejected label:
  v007 (#559 comment 6341991856), clean only — its perturbations were measured in #62 and are not re-run.
- Parity (as #62): per state, the four VPM decoded images and all cameras equal across states and rounds; NPM
  alpha unchanged; every injected NPM view must change RGB pixels (else `not_exercised`, run refused); per-cell
  changed loop counts and loops in the padding band recorded per state; input hashes before/after; code hashes.
- Budget: 3 fresh rounds × (readback + v007 clean + v010 clean + 8 shifts) = 30 renders. First round ≤ 180 s;
  total cap 600 s; after round 1 require remaining ≥ 2 × round 1 + 15 s, else `budget_stop` → inconclusive and
  replay the same command in a fresh directory. Zero candidate-code rounds (no production change exists).
- Forbidden: tuning rows, tolerance, grid or labels after seeing results; deselecting tests; weakening checks;
  editing delivered packages or other cards' files; rescoring frozen images as stability evidence.
- Not measured here: other objects (KPP1 / Vatutino / Staropetrovskiy MAF — no labelled seam pair), UV padding
  8/32 px, texel density, vertical (V) drift, bleed beyond the pad, production false-positive rate.
- Not taken (owners): form check v1 (closed for research), G22 atlas #1649, KPP1 v004 #1817/#1818,
  Staropetrovskiy #1500, MAF numbering #1809. Readiness 2026-11-24 13:45, areas 4/11.

Replay: `uv run --frozen python docs/research/atlas-phase-limit-r63/replay.py tmp/r63-run-NEW` (Windows, pinned
Blender, Drive ZIPs and slide 49 required; replay limited to readers with those inputs and the #58/#61/#62 Git objects).
