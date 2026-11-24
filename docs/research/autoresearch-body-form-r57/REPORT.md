# Standing #57 — Source wall hole vs 63B v007 aperture `О_194b464`, OBSERVE result

**Русское резюме. H57 опровергнута (refuted).** Сужение проёма `О_194b464` у принятого 63B v007 — не ошибка
ключа. В исходном меше `b63B_src.npz` дыра в наружном слое стены (вентфасад 250) в обоих сечениях 8,98/9,38 м
равна ключу с точностью 6 мкм (1,137606..3,437605 против 1,1376..3,4376); габарит самого окна в исходнике — тоже
1,1376..3,4376. Края v007 отстоят от исходной стены на 0,087/0,069 м (E57 = 0,086736 м, три прогона, размах 0).
Значит, `edges fail` у принятого v007 — настоящее отклонение формы, а не ложное срабатывание детектора. Где оно
возникло: уже в плане сборки `floor_A.json` (строка окна шириной 2,1444 м, края 1,2243/3,3687 в кадре ключа), правый
край совпадает с вершиной контура 44 — углом ступени, которую правило D341 («ступень ≤ 0,40 м — фактура») вынесло
наружу (ступень 0,249 м у t = 1,189, вынесенный пробег 2,107 м). Проём сузился на этапе плана (floor_from_dump + D341),
не при построении сетки. Остальные 4 проёма: исходная стена = ключ (≤ 0,0001 м), побочных изменений нет.
Тела, ключ, детектор, допуски и пакеты не менялись; PR и внедрения нет.

**Вопрос Артёму (решение не принималось):** проём 2,144 м вместо 2,30 м у принятого v007 — допустимое следствие
D341 (тогда `edges` для таких проёмов надо считать от вынесенного контура) или дефект, который v007 унаследовал и
который нужно чинить в плане? От ответа зависит, можно ли откалибровать `edges` на 63B (сейчас принятый хуже
отклонённых по этой проверке, и это правда о геометрии).

## Clean measurement (frozen contract `a6f3a5bd`, runner `09dd7e03`)

Run status `complete`; three fresh processes 0.773 / 0.780 / 0.962 s, total 2.848 s (cap 600 s); run files
byte-identical; pins pre/postflight OK.

| Opening | Section | Source wall hole S (m) | Key K (m) | max\|S−K\| | v007 observed (m) | max\|S−O7\| |
|---|---|---|---|---:|---|---:|
| `О_194b464` (target) | 17.8 / 18.2 | 1.137606..3.437605 | 1.1376..3.4376 | 0.000006 | 1.224342..3.368707 | **0.086736** |
| `О_415705d` | both | 0.901561..2.611562 | 0.9016..2.6116 | 0.000039 | passes key (#51) | — |
| `О_6189f94` | both | 5.594508..7.304509 | 5.5945..7.3045 | 0.000092 | passes key | — |
| `О_010a21f` | both | 8.704513..9.704510 | 8.7045..9.7045 | 0.000090 | passes key | — |
| `О_1198368` | both | 10.604511..11.604511 | 10.6045..11.6045 | 0.000089 | passes key | — |

Decision rule: max|S−K| ≤ 0.03 and min|S−O7| > 0.03 at both sections → **refuted**.

## Injected controls (section data only, all 5 openings × 2 sections × 3 runs)

| Probe | Moved endpoints per input | Response | Bound |
|---|---|---|---|
| Positive witness: endpoints within 0.05 m of S left edge, +0.050 m | 20–26 | ΔL = +0.050000, ΔR = 0 on 10/10 cells | ±0.001 met |
| Negative: endpoints > 1.0 m outside search window, +0.050 m | 834–1064 | Δ = 0 on 10/10 cells | ≤ 0.001 met |

No `not_exercised` probes. These are detector-sensitivity witnesses on source slices, not geometry exports.

## Calibration consequence (rescoring frozen #51 extracts — not stability evidence)

Key copy with `edge_s_m` := S (SHA-256 `6097bc9a…a8f6`), unchanged `score_heldout.main`. Because S = K within
0.0001 m, every variant is unchanged: v007 `edges` fail = 1 (`О_194b464`), total fails 9; v002–v006 `edges` fail = 0,
total 5. The expected flip under H57 (v007 1→0, v002–v006 0→1) did not occur. The accepted-worse-than-rejected order
on `edges` stays and is now explained by geometry, not by the key.

## Exploratory, outside the frozen hypothesis (no decision drawn)

- Source layers on segment 16–17 at 9.38 m: d = 0 and d = −0.25 m faces belong to `Базовая стена Вентфасад 250`
  (outer hole 1.138..3.438; a second face at −0.25 m has a hole 1.188..3.388, i.e. 0.05 m per side narrower);
  d = −0.5 m: gas-block wall `СВ-1.1 ГБ-200` and the window `О_194b464` (−0.50..−0.55). v007 edges are 0.036/0.019 m
  from the −0.25 m face hole — close but not within 0.03 on the left. v007 depth 0.50 = the window plane; the
  0.50/0.71 reveal reference stays Artem's open question (#53).
- floor_A.json (SHA-256 prefix `f1f2a541`): ring vertices 43/44 at key-frame t = −0.0194 / 3.3687; window row
  `[0, 76.0458, 78.1902, 0, 1, 0.5]` → 1.2243..3.3687; D341 step row `at [82.72, 14.87]` (t = 1.1892), step 0.249,
  moved run 2.107, `moved: out`.

## Replay and evidence

`python -X utf8 docs/research/autoresearch-body-form-r57/measure.py <fresh dir>` from repo root on the fixture PC
(inputs pinned in the contract; not in git → replay limited to this PC). Committed: `measure.py`, `receipt57.json`
(SHA-256 `a41ecf7f…6486`), `run1.json` (`b0704260…5f1d`). Full output incl. rescoring files:
`G:/Мой диск/AGR-evidence/standing57-body-form-wallhole/` (`SHA256SUMS.txt` SHA-256 `2f154662…0f97`), original
`C:/x/t_04ced2e2-r57/run01/`.
