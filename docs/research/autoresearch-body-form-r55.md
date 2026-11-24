# Standing #55 — Reveal-flank ownership against decoy segments (OBSERVE)

**Кратко.** #54 показал, что глубина откоса правильно реагирует на сдвиг фасада, но генератор сдвига и селектор опор были одной функцией. Здесь генератор независимый: в копии сечений свежего импорта подкладываем «чужие» параллельные сегменты (задняя/передняя грань в полосе поиска, задняя грань стены вне полосы, соседний сегмент, не касающийся края проёма, сквозной поручень, почти совпадающая грань 0,01 м) и считаем, сколько раз селектор #54 выдаёт **ложную числовую глубину**. Детектор, ключи, допуски и модели не меняем; PR только с контрактом и квитанцией.

## Frozen contract

Base `53d74681880c394ef20f5ecf63789a8aa8d79c5d` (origin/main); readiness `2026-11-24_0543`, areas 3–4. Continues target 1 of #54 (backlog). Not taken: Ground #1738/#1816 (fix on main, SIL13 re-run owned by #1622); build #1770/#1784/#1818; cold route #1315; atlas #1649; suite #1615; render/VLM judges #41/#45/#47/#49 (no exact KPP1 NW / Sokolniki body pairs with verdicts, so the BlenderWorld / VLM-Judge methods of the card focus have no admissible fixture this round); section conflict #48/#50; whole-wall mask #52; the 63B 0.50/0.71 m depth reference (Artem's open question from #53). No `tools/review/verdict.py` invocation, no 3ds Max, no builder.

- **Evaluator reused, not forked.** The replay fetches `docs/research/autoresearch-body-form-r54/{replay.py,pins.json}` from `cc470a6d6e01a5a861f4c00b1145caec727a7d00` (asserting replay.py SHA-256 `f1d1d5c5…01f3` as recorded in the #54 receipt) and runs #54's `main` unchanged: same 10 fixtures × 3 fresh Blender 5.1 imports, same pins, same calibration/parity guards and #54 aggregate. The only hook wraps #54 `perturb` for the `face` mode on the two accepted witnesses (G22 C_none `4259581`, 63B v007 `…194b464`), returns #54's result unchanged and attaches the decoy probes below, computed on the same fresh readback.
- **Independent decoy generator.** Decoys are placed from the KEY (opening `edge_s_m`, `contour_segment` frame and the clean flank line `line` measured by #54 before injection), never by calling #54 `supports`. Each probe adds new segments to both opening slices `17.8`/`18.2` (or only the stated side); original segments untouched except where stated. `s` = sign from the flank line toward the rim (rear = interior side). Segment length 0.60 m, from the gap edge outward along the wall.

| Probe | Geometry (offset from clean flank line) | Expected under #54 selector |
|---|---|---|
| `rear_in` | both sides, rear `+0.05·s`, touching gap edges | **trigger**: `noncoplanar`, no depth |
| `front_in` | both sides, front `−0.05·s`, touching gap edges | `noncoplanar`, no depth |
| `one_side` | left side only, rear `+0.05·s` | `noncoplanar`, no depth |
| `rear_out` | both sides, rear `+0.20·s` (outside the 0.12 m band when \|line\| < 0.07) | measured, Δdepth ≤ 0.001 m |
| `near_miss` | both sides, rear `+0.05·s`, endpoint 0.06 m back from the gap edge | measured, Δdepth ≤ 0.001 m |
| `tiny` | both sides, rear `+0.01·s` (< 0.015 m tol), touching | measured, 0.001 < \|Δdepth\| ≤ 0.010 m |
| `rail` | one segment spanning the gap ±0.30 m at front `−0.08·s` | `flank_missing` (gap closed), no depth |

- **Primary number F55** = count of probe trials (2 witnesses × 7 probes × 3 reps = 42) whose status is `measured` and \|depth − clean depth\| > 0.015 m (false numeric depth). Secondary, reported separately: fail-closed losses (clean measured → unmeasured) per probe; off-target depth change > 0.001 m or status flip on other openings; per-probe exercised flag (decoy segments added > 0, and for `*_in`/`one_side`/`tiny` the decoy \|d\| < 0.12 m, for `rear_out` ≥ 0.12 m; otherwise `not_exercised` = **not measured**).
- **Calibration first:** #54 aggregate must reproduce `all_guards = true`, `hypothesis = confirmed` (63B source-wall 0/5 vs 5/5, G22 A>R, parity of all 30 original reports, primary ≤ 0.001 m). If not, H55 is inconclusive (evaluator drift), not scored.
- **H55 confirmed** iff calibration holds, all 42 trials exercised, F55 = 0, every probe hits its expected status/bound in all 3 reps on both witnesses (spread across reps 0 in status, ≤ 0.001 m in depth), and off-target = 0. **Refuted** if any exercised trial gives F55 > 0 or a deviating status (the deviation is the finding). Otherwise inconclusive. A pass means fail-closed behaviour on this frozen decoy set only — not a proof of wall ownership in general, not a gate.
- **Budget/stop:** one candidate (#54 selector as is), no tuning after the first score, 0 further candidates. #54 measured 35.5 s for the full series; cap 180 s (#54's own budget guard, `R54_CAP_S`); one run, a second run only if the first fails for an environment reason (recorded). No partial KEEP.
- **Forbidden:** changing detector/keys/tolerances, dropping fixtures or probes, editing FBX or delivered packages, copying the hidden key to Git, touching other cards' files, visual-judge runs.

## Replay

`python -X utf8 docs/research/autoresearch-body-form-r55/replay.py <new out dir>` from this branch on the fixture-equipped PC (local #40/#51/#53/t_563a40f7 data + Blender 5.1, pins verified pre/post by #54 code). Replay limited to that PC; receipt in Git records raw path + SHA-256.
