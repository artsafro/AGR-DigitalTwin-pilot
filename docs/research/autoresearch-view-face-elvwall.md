# H167 — ELV TC Sreda: transfer of the Silikatny wall stack (#163 → #165 → #166), OBSERVE

## Кратко для Артёма

Проверил на независимом альбоме (ЭЛВ ТЦ «Среда»), без единой подстройки, тот метод, который собрали на Силикатном:
стена-кандидат снимается фронтально, вид сравнивается с ней по остеклению, плюс две проверки — длина вида против
длины стены (#165) и ритм остекления по ширине (#166). Сокольники не открывал (#2001 открыт).

- **Ошибок нет:** 0 неверных из 10 реальных видов (и 0 неверных на зеркале, перемешивании и пустых масках).
- **Но покрытие маленькое — гипотеза H167 опровергнута:** верно 2 из 7 полных фасадов (оба вида И-А, восточный
  витражный фасад) и 1 из 3 фрагментов (Д-Г); остальные — честный отказ. Порог был ≥ 4 из 7 (как у #145).
  Причина видна до счёта: у ЭЛВ стекло нарисовано почти только на восточном фасаде (41 % площади вида);
  на остальных фасадах стекла < 1 %, сравнивать нечего.
- **Проверка ритма перенеслась:** на настоящем И-А ритм 0,79 (на Силикатном было 0,36 — на грани), а на
  перемешанном И-А — 0,07, и только эта проверка снимает ложный ответ, который базовый метод оставлял.
  Проверка длины здесь ни разу не сработала и ничего не отняла.
- **Вывод для шага «карта вид↔грань»:** сравнение по стеклу — надёжный, но узкий канал: годится для витражных
  стен, на глухих фасадах молчит. В шаг его ставить только вместе с другим каналом (заливки отделки #149 или
  линии #140B) на тех же стенах-кандидатах; ответ — когда хоть один канал уверен и ни один не спорит. Это
  следующий замер.

## Frozen contract (committed before any score was computed)

Card t_2dfecd45 (standing #167), focus 0 (view↔face map sheet). #2001 is OPEN: Sokolniki held out, not opened.
Takes #166 next (1): the stack built on Silikatny (#163 per-wall frontal renders + width eligibility + tau/delta,
#165 full-view length veto, #166 full-view glazing-rhythm veto) has only been measured on the album it was built on.
This card runs it, parameters unchanged, on an independent labelled album: ELV TC Sreda (#145 fixture: AGR booklet
PDF `49c10527…9545` + Revit 2023 FBX `7ccf502d…b961`, 7 full views + 3 real fragments, side-level truth from
`autoresearch-view-face-elv/fixture.json` on main). Not duplicated: #2073/#2074 finish partition, #2075 wall
exercise; atlas/form/trainer parked.

**H167.** Arm C (= #163 decide → #165 `length_veto` → #166 `rhythm_gate`, all executed from SHA-pinned blobs) on
the 10 clean native ELV views: **0 wrong** AND **≥ 4/7 full views correct** (the #145 bound) AND blank masks abstain
10/10. Any miss refutes. Arms A (#163 only) and B (+#165) are reported beside C; #145 (5/0/2 full) is the reference.

**Primary metric.** Side-level correct / wrong / abstain: an answered wall is correct iff its azimuth equals the
#145 `gt_az` (same truth as #145, so the numbers are comparable). Diagnostic, not scored: whether the answered wall
is an *outer* wall (< 50 % of its length covered by a further-out wall of the same azimuth) — this catches a
parapet-inner face answering for the right side.

**What is adapted for ELV (frozen, the only changes; everything else is the pinned code):**

| Item | Silikatny (#161–#166) | ELV (#167) | Why |
|---|---|---|---|
| Model import | category OBJ, mm → m | FBX import (Blender 4.4), meshes with world max z > 30 m deleted (#145 rule, 1 stray batten) | different source format |
| Facade / glass / hidden sets | `Ctx_steny+okna+paneli_vitrazha` / `okna+paneli_vitrazha` / `perekrytiya` | Revit type regex: facade `^(Базовая стена\|Системная панель\|\(WN\)-RD\|Окно )`; glass `^(Системная панель (С остекление\|Стемалит\|\(CP\)_Glass)\|\(WN\)-RD\|Окно )`; hidden `^Перекрытие` | same categories (walls, windows, curtain panels; doors excluded as on Silikatny) |
| Azimuths | 8 (#161) | 0/90/180/270 (#145) | ELV is orthogonal; the slanted north wall (≈ 6°) falls in az 90 within the ±12° tolerance |
| Band z | 0–12.9 m | 0–16.4 m (#145 building top; facade max z 16.17 = +16.220) | building height |
| Drawing glass mask | legend complement + luminance | exact vector fills of legend items 5/6/7 (p18): RGB (207,227,250) stemalit, (236,244,253) glazing, distance ≤ 8 (white is 22 away) | ELV booklet is vector with exact fills |
| Datum anchors | manual (#162 table) | label rule: nearest exact level text to the view box, anchor y = text bottom; vertical scale = #145 `scale_pt_per_m` (axis labels; p20 level labels). Labels: `+0.000` (p18/p19), `+15.900` sign top (p21, p23, p24), `-0.100` (p20) | no manual reading |
| kind | manual | #145 `kind`; `fragment_top_cut` → fragment | — |

Unchanged (pinned): wall extraction, frontal clipped renders, 0.1 m/px, grid 0.25 m, `min_overlap` 0.8, `fit_tol`
0.10, tau 0.30, delta 0.10, rhythm threshold 0.35 (128 bins), #161 `opening`/`largest_bbox`/`best_offset`, #162
`register`, #163 `wall_masks`/`decide`/`block_shuffle` (2 m blocks, seed 163).

**Pre-score checks (no view scored).**
- *Geometry* (`C:/x/ev_t_2dfecd45/probe2`, 8 min Blender): 1 mesh dropped (z > 30 m), 3 790 facade / 694 glass /
  253 hidden meshes, facade z −2.85…16.17; 27 160 vertical faces in band, 5 716 exterior; 34 walls. Outer shell:
  east az 0 W08 (x 75.9, L 51.0), W09/W10 (x 79.0, 18.4 each, split by the recessed entrance); north az 90 W16
  (y 1.35, L 85.2, includes the slanted part); south az 270 W33 (y −50.6, L 76.5); west az 180 W24 (x −0.4, L 30.4),
  W25/W26 (annex). Many parapet-inner faces pass the 45° sky ray (e.g. W27 az 270 at y 0, W17–W21 az 180 at
  x 47–79): they are candidates exactly as on Silikatny.
- *Front end* (`--probe`, `C:/x/ev_t_2dfecd45/probe_fe`): widths 54.5 / 88.5 / 88.5 / 55.0 / 52.5 / 54.5 / 88.0 m
  for the seven full views (nominal 52.6 / 84 / 84 / 52.6 / 50.4 / 52.6 / 84 + margins), fragments 20.25 / 14.75 /
  3.75 m. Scales 9.44–9.45 pt/m (1:300) on full views. **Drawn glass fraction:** I-A 0.41 (p18), 0.16 (p21,
  faded sheet); 1-10 0.010, 10-1 0.004, A-I 0.003, 6-1 0.001, p21 1-12 0.000; fragments D-G 0.44, 8-9 0.012, 9-10
  0.034. ELV is mostly opaque: only the east curtain wall carries glass. **Expected (written before scoring):**
  low coverage — answers possible on I-A and D-G only; near-empty masks must abstain, not guess.

**Perturbations (per state changed cells recorded; `exercised` = changed > 0).** mirror, blank (must abstain),
shuffle (2 m blocks, seed 163). Candidate-order reversal must reproduce every arm's answer (checked in every state).

**Budget and series.** One fresh run = Blender walls + renders + fresh PDF read + all arms/states. 3 fresh runs,
0 exploratory rounds after this freeze; median and max−min wall time reported. 3600 s budget: stop after a run if the
rest cannot fit → `inconclusive`. Runs must be byte-identical (body digest); inputs hashed before and after.
Forbidden: changing any pinned parameter, the truth, the regexes or the anchors after seeing scores; deselection;
writes to delivered packages or other cards' files; opening Sokolniki.

**Not measured:** wall-level truth inside a side (only the outer-wall diagnostic), within-wall bay localisation,
accepted/rejected delivery calibration, blind full/fragment classification, Sokolniki STOP 04.

**Replay.**
```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-elvwall/run.py <new_dir>
```
Inputs: the #145 fixture paths on the pilot host (owner's `Dima_Andrew/3_sreda/for_ai`), SHA-256 checked before and
after; staged copies in `G:/Мой диск/AGR-evidence/145-view-face-elv/`. Replay limited to the pilot host.

## Round log

**Hypothesis H167: refuted (coverage bound). Safety bound met. Run: finished. Adoption readiness: no.**
Contract commit `4cc2cd76` (before any score); runner measured = that commit (`run.py` SHA-256 `ee621f3d…d124`,
adapter `1fed1428…7fce`, params `220b0cb2…e1db` as read on Windows). 3 fresh runs (new Blender walls/renders +
new PDF read each): 453.2 / 437.0 / 460.1 s, median 453.2 s, spread 23.2 s (Blender stage 416–438 s); all three
bodies byte-identical (digest `04f67ea6…8921`); inputs re-hashed after the run: unchanged; candidate-order
reversal reproduced every arm in every state.

| Group (clean) | A #163 | B +#165 | C +#166 | #145 ref |
|---|---:|---:|---:|---:|
| Full views (7) | 2 / 0 / 5 | 2 / 0 / 5 | 2 / 0 / 5 | 5 / 0 / 2 |
| Real fragments (3) | 1 / 0 / 2 | 1 / 0 / 2 | 1 / 0 / 2 | 1 / 0 / 2 (top-cut incl.) |

Correct / wrong / abstain, side level (answered wall azimuth = #145 `gt_az`).

Per view (clean, arm C; score / margin over the best other eligible wall):
- p18 I-A → W08 (east, az 0) 0.767 / 0.638, rhythm 0.787 — correct. p21 I-A (faded sheet, glass 0.16) → W08
  0.421 / 0.385, rhythm 0.762 — correct. p23 fragment D-G → W08 0.804 / 0.387 among 11 eligible — correct.
- Abstain: p18 1-10 (top W27 0.060), p19 10-1 (W27 0.122 / 0.012), p19 A-I (W33 0.129 / 0.070), p19 6-1
  (W16 = true side 0.190 / 0.030), p21 1-12 (no drawn glass, 0.0); p24 fragment 8-9 (W33 = true side 0.362 /
  0.064), p20 1:20 fragment 9-10 (W33 = true side 0.914 / 0.031 among 34 eligible: a 3.75 m view fits everywhere).
- Every full abstain is a view with < 1 % drawn glass (front-end probe, written before scoring).

Clean vs injected vs not measured:
- **Clean:** above. B and C never changed a clean answer (no coverage lost); #165 never fired.
- **Injected (all rows exercised except p21 1-12, whose mask is empty → mirror/blank/shuffle `not_exercised`, and
  the p20 shuffle with 0 changed cells):** blanks 10/10 abstain in all arms. Mirror: 2/0/5 full, 1/0/2 fragments in
  all arms (I-A is near-symmetric; rhythm 0.862 / 0.842 keeps it — a diagnostic, not a bound). Shuffle (2 m blocks):
  A/B keep W08 on p18 I-A (glass amount carries the answer), **C vetoes it (rhythm 0.071)** → full 1/0/6 → 0/0/7.
  This is the only positive trigger of a veto on this album; it reproduces the #166 shuffle witness off-album.
- **Diagnostic (outer wall):** the frozen 50 %-coverage rule marks W08 *not outer* (72 % of it lies behind the
  curtain-wall planes W09/W10 at +3.1 m), although W08 is the east façade plane; the rule is too strict for a
  façade with projecting boxes and is not a safety signal. Parapet-inner faces (W17–W21, W27) are candidates as on
  Silikatny; W27 was the top eligible wall on 1-10 and 10-1 but far below tau.
- **Not measured:** wall-level truth within a side, bay localisation, accepted/rejected delivery calibration,
  blind full/fragment labels, channel combination, Sokolniki STOP 04.

## Recommendation (OBSERVE)

Do not build the OKS step on the glass stack alone. On ELV it was safe (0 wrong over 10 clean + 30 injected states)
but answered only glazed walls (3/10). For the shared step «view↔face map sheet»: keep per-wall frontal candidates
with the width eligibility and the #166 rhythm veto, and run more than one content channel on those candidates
(glass NCC here; finish-partition D #149, which answered 6/7 full ELV views at side level; #140 B edges). Print per
view the ranked walls, each channel's score and the reason for abstaining; answer only when one channel is confident
and none contradicts; partial views without a confident wall stay a question to Artem. Next: freeze and measure that
channel union on ELV + Silikatny (0 wrong as the bound), then Sokolniki blind after #2001 closes.

## Replay and evidence

Receipt: [receipt.json](autoresearch-view-face-elvwall/receipt.json) (runner-written SHA-256
`9efa230895099ff94acb354d8981966c1af59c2146ed57725ebe712a90f11df2`). Evidence (3 run directories with wall renders,
`walls.json`, bodies, probe): `G:/Мой диск/AGR-evidence/167-view-face-elvwall/` + `SHA256SUMS.txt` (117 files,
manifest SHA-256 `88d17214b077503b8bc99937302fbd7761a439f9b73e1fa959dfaef22ef4adf7`). Replay needs the pilot host
(owner's ELV folder, Blender 4.4 pinned).

Regression: `test_run.py` (outer-wall rule, ELV glass colour rule vs white/grey fills, tally grouping) — 3 passed.
No production change.
Full suite: deferred to merge batch (rule 68).
Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --locked --extra pdf-review pytest -q -p no:cacheprovider --basetemp C:/x/pt_t_2dfecd45 docs/research/autoresearch-view-face-elvwall/test_run.py` — 3 passed.
