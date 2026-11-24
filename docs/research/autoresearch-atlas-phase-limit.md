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

## R0 — confirmed (OBSERVE)

**Итог:** на АС.08 оракул швов слайда 49 ловит чистый сдвиг UV атласа НПМ (ВПМ не меняется) начиная с **1 px
атласа (≈10,3 мм при 96,9 px/м)** в обе стороны: L63 = 1 px, медиана трёх свежих раундов, размах 0. ±0,5 px
(≈5,2 мм) не поднимает JE; знак сдвига на обнаружение не влияет (JE +1 px = 182, −1 px = 186; ±2 px = 312;
±5 px = 320, свидетель #62 воспроизведён). Отклонённый v007 по-прежнему хуже принятого v010 (JE 202 против 0).
Это предел чувствительности синтетического сдвига на одном объекте, не порог приёмки и не причина отказа v007.

Run status `completed`, hypothesis `confirmed`; wall 423.699 s (rounds 145.112 / 132.213 / 145.037 s; first-round
gate ≤ 180 s and remaining-time gate passed). Measured script commit `88f8dc296ba3c862986fb5bd54f82bf09ee58a4a`.

| JE on v010 (all 3 rounds identical) | −5 | −2 | −1 | −0.5 | clean | +0.5 | +1 | +2 | +5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JE (missing + extra joints, 8 rows, tol 0.01 m) | 320 | 312 | 186 | 0 | 0 | 0 | 182 | 312 | 320 |

**Clean:** v007 JE 202 > v010 JE 0 in every round; clean-vs-clean NPM repeat across rounds 0 changed pixels.
**Injected:** every state changed exactly 114 UV loops (PanelVJ30 90, PanelVJ12 24) and RGB pixels in all four NPM
views (round 1, e.g. ±0.5 px ≈ 0.68–1.76 M, ±5 px ≈ 0.79–2.06 M per view); VPM decoded pixels, NPM alpha, cameras
and the four original ZIPs + slide + Blender exe unchanged (`originals_match_after: true`).
**Not measured (`not_exercised`):** no shifted loop entered the 6 px padding band (`loops_in_pad` 0 in all states),
so cell bleed/padding behaviour is not measured; V-direction drift, v007 perturbations (run in #62), other objects
(KPP1 / Vatutino / Staropetrovskiy), UV padding 8/32 px, texel density and production false-positive rate.

Interpretation for a future gate (not applied): the oracle resolution equals its 10 mm tolerance; atlas drift
≤ 0.5 px is invisible to it, and drift ≥ 1 px on a jointed panel would be flagged whichever way it goes.
Nothing in the pipeline or delivered packages was changed.

Receipt: `atlas-phase-limit-r63/receipt.json` SHA-256 `b390277d7a20799503be1b21e70fadd3993dda4ed1ba88354c0bf27ac25dfe08`.
Evidence (renders, logs, staged code): `G:/Мой диск/AGR-evidence/standing63-atlas-phase-limit-r001/`, 700 files,
`SHA256SUMS.txt` SHA-256 `1c207b99299ba528caba39ab2870fe75a508a6a25829d85b427bc71a0c74111d` (verified with `sha256sum -c`).

Affected tests: `uv run --frozen pytest -q -o addopts= docs/research/atlas-phase-limit-r63/test_phase63.py tests/jobs/test_tec26_ac08_pilot.py tests/jobs/test_tec26_ac08_slide_overlay.py tests/jobs/test_tec26_joint_visibility_controls.py tests/test_npm_atlas_padding.py` — 155 passed, 25 skipped (fixture gates), 1 warning. The new verdict test first failed (test bug: float keys via `**`), then passed.

`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 553 passed, `repo_guards: GREEN`.

Full suite: deferred to merge batch (rule 68)
