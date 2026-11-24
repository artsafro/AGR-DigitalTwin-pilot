# Standing #57 — Source wall hole as the aperture-edge reference (63B, OBSERVE)

**Русское резюме.** Продолжаем #55/#56. У принятого 63B v007 проём `О_194b464` уже ключа на 0,087/0,069 м
(2,144 против 2,30 м), и замороженный детектор ставит принятому телу `edges fail`, а отклонённым v002–v006 —
`pass`. Вопрос: это ошибка тела или ключа? Ключ взят из габарита элемента окна (`source_sections_and_openings.json`),
v007 — из дампа исходного меша. Меряем дыру в **стене** исходного меша `b63B_src.npz` в тех же сечениях тем же
детектором (`score_heldout.wall_intervals/gaps`, без изменений) и сравниваем с ключом и с краями v007.
Тела, ключ, допуски и пакеты не меняем; результат — наблюдение, не новый гейт.

## Frozen contract (written before measurement)

**H57.** On aperture `рт О_194b464` (63B east, typical floor A, key ring segment 16–17), the outer wall hole in the
pinned source mesh coincides with the accepted v007 observed edges, not with the key edges: at both opening sections,
max |S − O7| ≤ 0.03 m (existing `opening_edge_m`) and max |S − K| > 0.03 m.
- **Refuted** if max |S − K| ≤ 0.03 and max |S − O7| > 0.03 at both sections (the v007 narrowing is a builder
  artefact the detector correctly reports).
- **Inconclusive** for any other combination, a missing/non-unique wall gap at mid-span, or a failed pin.

**Primary number** E57 = max over both edges and both sections of |S − O7| for `О_194b464` (m, lower = the wall-hole
reference explains the accepted body). Secondary: D57 = same against the key K. Median of 3 fresh-process runs;
deterministic slicing, so spread must be exactly 0 (any spread → inconclusive).

**Inputs (pinned, SHA-256 preflight + postflight, fail closed):**
- source mesh `C:/x/ev_poly63b7/b63B_src.npz` `b5cdbf394e4a10c55db391c13d15096c71e5a4c085be30e0edb595610cd04aea`
  (crop of `STLB-04_RR_AR.fbx` used to build v007; object names per triangle);
- key `C:/x/t_fb3a0b98-r51/key/heldout-key-v001.json` `67a1ae5b…6b14` + sections `07ce9a5b…98b6`;
- detector `C:/x/t_563a40f7/detector/score_heldout.py` `e9d6f65b6373a4fc…` (imported, unchanged);
- frozen #51 candidate extracts `C:/x/t_fb3a0b98-r51/run1/v00{2..7}/rep1/candidate.extract.json` (hashes in receipt).
- Sections: key labels `17.8`, `18.2` (= real z 8.98, 9.38; `z_shift_m` 8.82 from the key). Walls = triangles whose
  object name does not start with `Окн`/`Витр`/`Двер`; windows recorded separately (extent only, not used for S).
- S = the unchanged detector gap on `[e0−0.6, e1+0.6]` that contains the key mid-span (same rule as
  `score_heldout` line 140), on source-wall slice segments in the key frame.

**Controls and witnesses (frozen bounds):**
- Accepted controls (collateral impact): the other 4 in-box openings (`415705d`, `6189f94`, `010a21f`, `1198368`).
  v007 already passes `edges` there, so expected |S − K| ≤ 0.03 on each; any control > 0.03 is reported as
  collateral change of the reference (not hidden).
- Positive trigger witness (injected, section data only): move every source-wall slice segment **endpoint** whose
  axis coordinate lies within 0.05 m of S's left edge by +0.050 m along the key axis → S left edge moves
  +0.050 ± 0.001, right edge Δ ≤ 0.001. Negative perturbation: same move on endpoints > 1.0 m outside the search
  window → S unchanged (Δ ≤ 0.001). (Amended before any measurement, commit after `d3ce0cc8`: whole-segment shift
  would leave a long outer-face segment untouched.)
  Record per-input changed segment counts; a witness that changes 0 segments is `not_exercised` (not measured).
- Calibration consequence (rescoring the frozen #51 extracts — labelled rescoring, **not** stability evidence): copy
  the key with `edge_s_m` replaced by S per opening (other fields unchanged), write its own SHA256SUMS, run the unchanged
  `score_heldout.main` on v002–v007; report per-variant `edges` fail counts. Expected direction under H57: v007 edges
  fails 1 → 0; v002–v006 `О_194b464:edges` 0 → 1 each. Reveal depth (0.50/0.71, open question to Artem since #53) and
  contour are out of scope and reported unchanged.

**Budget / stop.** One confirmation series (3 runs), zero candidate references, zero retuning; wall cap 10 min. Stop on
pin mismatch, one completed series, or cap (→ `inconclusive`, rerun same command to a fresh dir). No Blender, no
3ds Max, no body build/repair, no package edits, no tolerance or detector change, no deselected tests, no edits to
other cards' files (C:/x inputs are read-only; outputs go to a fresh directory).

**Replay.** From repo root: `python -X utf8 docs/research/autoresearch-body-form-r57/measure.py <fresh out dir>`.
Replay limited to the fixture PC (inputs above; not in git). Exact variant measured: this file's commit.

## Selection

Readiness `2026-11-24_0944.json` areas 3–4. Continues #56 next-target 1 (origin of the 0.087/0.069 strips). Not taken:
Ground #1738/#1816 (SIL13 under #1622), construction #1736/#1770/#1784, delivery #1817/#1818/#1315, atlas #1649,
suite #1615, hidden seam #1802, judges #41/#45/#47/#49 (no exact KPP1 NW / Sokolniki body pairs with byte verdicts),
0.50/0.71 reveal reference (Artem's question since #53).
