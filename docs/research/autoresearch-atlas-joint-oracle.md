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
