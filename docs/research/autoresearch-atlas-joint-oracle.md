# Standing #61 — NPM joint count/phase against the slide-49 contract (OBSERVE)

## Frozen before implementation and measurement

H61: the existing AC08 joint oracle (`compare_facades.py` + `joint_count.render_row/count_joints`, slide 49 contract
29/29/11/11 joints [D171]) applied to the rendered **NPM** facades scores the rejected v007 (wrong joint pitch, #559
comment 6341991856; retro O4 «шаг швов 0,6 м по текстуре пользователя») worse than the accepted visual reference v010
(#559 comment 6345392389). This continues #58 (refuted same-revision drift) and #60 (fixed-reference drift, not a
seam detector): it isolates the seam pitch/phase that Artem actually rejected. A builder moves the number by placing
the atlas joints at the contract positions. Readiness 2026-11-24 09:44, areas 4/11. Not taken (owned elsewhere): G22
atlas #1649, KPP1 v004 #1817/#1818, Staropetrovskiy etalons #1500, MAF numbering #1809, form check v1, suite #1615.
Padding (8/32 px), texel density and other objects are **not measured** here (no labelled rejected pair).

- Fixture (pinned): the four AC08 ZIPs of `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-{v007,v010}/` with the
  #58 SHA-256 values, the #58 render path unchanged (`render_facades.py`/`vpm_uv.py` at `a1f41ee2`, version specs at
  `5febf7cd` / `54365249`, Blender 5.1.2 `ec6e62d40fa9`, `PX_PER_M=400`, four orthographic FLAT views, no Max).
  Oracle frame = v010 only: spec `54365249:jobs/TEC26-OKS/AC08/vpm_textures.json` (contract ribs, finishes, slide),
  `54365249:jobs/TEC26-OKS/AC08/sheet-facades.json`, slide `559-…-v010/slide49.png` (SHA-256 `256f32da…08a8fd`, checked
  by `compare_facades` itself; only the spec's `presentation.image` path is rewritten to the staged copy), and a fresh
  `qa_readback.py` dump of the v010 VPM FBX for the field extent. Checker code = blobs at `54365249` of
  `compare_facades.py`, `joint_count.py`, `finish_map.py`, `qa_readback.py`, `KPP1/scripts/vpm_textures.json`
  (identical to origin/main `5861e61a` for the four scripts). Cameras must be byte-equal across profiles and
  revisions (as #58), else refuse — the v010 field frame is then valid for the v007 pixels.
- Score: `JE(rev)` = sum over the 4 facades × 2 rows (z at 0.2 and 0.95 of the field, as `compare_facades`) of
  `len(missing) + len(extra)` of the NPM row in the **unchanged** `compare_facades.main` `compare.json`
  (tol 0.01 m, dark 0.85). One number `D61 = median_3(JE_v007 − JE_v010)`. Descriptive only: joints found vs
  expected (count error), `max_position_error_m` (phase), found pitch, VPM rows, slide joints.
- Keep for further study (never production): every round delta ≥ 1, spread 0, accepted control `JE_v010 = 0`,
  slide joints = contract on 4/4, parity passes. Valid scores with any round delta ≤ 0 refute H61. Preflight,
  parity, control, coverage or budget failure is inconclusive.
- Parity: an in-process reproduction (same pinned `joint_count` calls, same arguments) must equal the
  `compare.json` NPM rows for both revisions in every round before any probe is scored.
- Positive trigger on the accepted control (v010 NPM, in memory, sampled rows only): RGB shifted right by
  20 px = 0.05 m (no wrap; pixels `x<20` keep the original) → predict `ΔJE ≥ 8`. Same probe on v007: recorded,
  no prediction. Tolerance invariance: shift by 2 px = 0.005 m (< tol 0.01 m minus the v010 historical phase
  error ≤ 0.00326 m) → predict `ΔJE = 0` on v010. Negative: RGB=17 on every NPM pixel **outside** the two
  sampled rows of each view → predict `ΔJE = 0` on both revisions with > 0 changed pixels. Per view and state
  record changed pixel counts; zero changed pixels = `not_exercised` = not measured.
- Budget: exactly three fresh rounds (per round: two renders as #58, one v010 VPM readback, two `compare_facades`
  runs), one metric variant, zero candidate code rounds. Round 1 ≤ 120 s and the remaining 420 s global cap must
  cover 2 × round 1 + 15 s, else stop `budget_stop` (inconclusive) and rerun the identical command later in a fresh
  directory. Hash all four ZIPs before/after. Forbidden: retuning tol/dark/rows/masks after seeing results,
  relaxing checks, editing packages, deselecting tests, touching files owned by another card.
- OBSERVE: no rule is applied to any delivered work; any later gate goes through its own PR and review.

Replay (from the branch, Windows with Drive access and Blender 5.1.2 `ec6e62d40fa9`):

```bash
uv run --frozen python docs/research/atlas-joint-oracle-r61/replay.py tmp/r61-run-NEW
```

## R0 — H61 confirmed on AC08 (OBSERVE; not a production gate)

**Итог (рус.):** существующий оракул швов `compare_facades`/`joint_count` по контракту слайда 49 на рендере НПМ
даёт отклонённому v007 JE = 202 ошибочных шва, принятому v010 — 0. D61 = +202 в каждом из трёх свежих раундов,
размах 0, все контроли пройдены. В отличие от #58/#60 это число измеряет именно то, за что Артём отклонил v007
(шаг 0,6 м вместо 0,195/0,186 м). Но JE ВПМ = JE НПМ в обеих версиях: атлас НПМ честно переносит швы ВПМ, поэтому
сигнал ловит неверный шаг/фазу швов в текстуре, а не дрейф атласа НПМ↔ВПМ. Ничего не внедрено.

Measured driver commit `bea1c9a6d3f8d961020e937ca966e4625921e837` (reducer SHA-256 `26c0a203ffc6c244…`, full value in
the receipt), run `tmp/r61-run-001`, status completed, wall 63.058 s, all six renders and three readbacks exit 0,
four ZIPs unchanged after, cameras byte-equal across profiles and revisions.

| Round | Wall s | JE v007 NPM | JE v010 NPM | Delta | compare exit v007 / v010 |
|---|---:|---:|---:|---:|---|
| 1 | 20.905 | 202 | 0 | +202 | 1 (MISMATCH) / 0 |
| 2 | 20.589 | 202 | 0 | +202 | 1 / 0 |
| 3 | 20.437 | 202 | 0 | +202 | 1 / 0 |

D61 = +202, paired spread 0. Parity: in-process rows equal `compare.json` NPM rows for both revisions in every round.

- Clean (per facade, NPM, rows z=0.570/2.285): v007 1-2 found 11 of 29 (missing 28, extra 10, phase error
  0.0958 m, found pitch 0.599 m); 2-1 11 of 29 (24+8 / 28+10); А-Б and Б-А 3 of 11 (11+3, pitch 0.600-0.601 m).
  v010: 29/29/11/11 found, missing = extra = 0, max phase error 0.0017-0.0033 m, pitch 0.195 / 0.186 m. Slide
  joints = contract 29/29/11/11 on 4/4. VPM JE equals NPM JE (202 / 0): the defect is in the seam design common to
  both profiles, so this is a seam-pitch/phase oracle, **not** an NPM-vs-VPM drift measure.
- Injected (sampled rows only, in memory): +20 px (0.05 m) on v010 → ΔJE +320 (prediction ≥ 8), 13,095 changed px;
  on v007 ΔJE 0 (already fully wrong; no prediction). +2 px (0.005 m) on v010 → ΔJE 0 (prediction 0), 11,140 px;
  on v007 −6 (recorded, no prediction). Outside the sampled rows RGB=17 → ΔJE 0 on both, 14,570,496 changed px
  per revision. Every probe exercised in every view of every round.
- Not measured: other objects (no slide-type rib contract or labelled seam rejection), MAF board seams, padding
  (8/32 px), texel density, NPM-only atlas mutation, any enforcement threshold. The v010 VPM readback JSON hash
  differs per round (486718d7…, 3490f9bd…, 1996597a…) while the scored rows are identical; cause not isolated.

Receipt `docs/research/atlas-joint-oracle-r61/receipt.json` (raw Windows file SHA-256
`662cef564366c262acec83ec902f17e6bae363ccc833030a4203e4e8d07bfa17`). Evidence (renders, compare sheets, logs,
readbacks; FBX/input copies omitted): `G:/Мой диск/AGR-evidence/standing61-atlas-joint-oracle-r001/`, 131 files
verified against the run directory, `SHA256SUMS.txt` SHA-256
`88a07df78ab2b29fee6402954e55b568f387234f1071e19a9969a73522e3d7d7`. Replay limited to Windows with the pinned
Blender build and Drive access to the four ZIPs and `slide49.png`.

Next: (1) apply the same oracle to an NPM-only phase mutation built natively (UV offset of the atlas cell on a copy,
VPM fixed) to measure whether a pure atlas drift is caught; (2) generalise the contract input (ribs per facade) to
another object that has a rib/board count in its source (MAF board seams) before any gate.
