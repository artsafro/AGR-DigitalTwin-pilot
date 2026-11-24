# Body form — scene-readback rubric, standing #43, round log R1

**Русское резюме.** Гипотеза H43 **подтверждена** на G22 к.2 SE. Замороженный held-out детектор t_563a40f7
(`extract.py` / `score_heldout.py`, хеши совпадают с его SHA256SUMS, допуски не менялись) ловит 8 из 12 заложенных и
отклонённых вариантов при 0 ложных провалов на трёх принятых контролях (A, A после экспорта, C_none). Пропущены
лишняя ниша глубиной 0.03 / 0.06 / **0.11 м** и фаска угла 0.05 м. Причина — слепая зона: контурные сечения стоят на
16.85 и 19.8 м, вне полосы окон, а сечения 17.8 / 18.2 ищут только разрывы стены с окном поиска 0.12 м; ниша мельче
0.12 м там не видна. Это ровно глубина лишних ниш КПП1 (110 мм). Кандидат C1 (только наблюдение): тот же контурный
допуск 0.05 м ещё и на 17.8 / 18.2 — ловит 10 из 12 (+2: ниши 0.06 и 0.11), на принятых 0 провалов, у прежних
проверок статус не изменился ни на одном входе. Детектор детерминирован (3 извлечения A — один хеш). Остаются
невидимыми дефекты внутри допуска 0.05 м (ниша 0.03, фаска 0.05: отклонение 0.035) — это допуск, а не ошибка.
Ограничения: один фрагмент, заложенные дефекты на копии A (синтетика), пары тел КПП1 NW / Сокольников по-прежнему
нет. Код в репозитории не меняется: детектор лежит вне репо и заморожен; C1 предлагается как версия v002 детектора
отдельной карточкой. Модели не строились и не чинились; 3ds Max не использовался.

## Scope

Contract: `autoresearch-body-form-scene-r43.md` (commit `c01e33e4`, before any measurement). Base `origin/main`
`1255e9dd`. Blender 5.1 headless; one round, one candidate (budget: 1 confirm, 0 new). Wall: whole run 15.5 s
(19 Blender runs, 4 workers), status OK, no budget stop.

## Results (`receipt.json`, full `result43.json`)

| Variant | Class | Baseline detected | Baseline group A pass/fail/nm | C1 detected | C1 new items (band contour dev) | Pre-existing items changed |
|---|---|---|---|---|---|---|
| A | accepted | no | 29/0/0 | no | 0.000 / 0.000 pass | 0 |
| A_rt | accepted (round-trip) | no | 29/0/0 | no | 0.000 pass | 0 |
| C_none | accepted control | no | 29/0/0 | no | 0.000 pass | 0 |
| R (v001, rejected) | negative | yes | 1/10/18 | yes | 1.500 fail | 0 |
| P_fill | negative | yes | 25/1/3 | yes | 0.901 fail | 0 |
| P_recess 0.03 | negative | **no** | 29/0/0 | **no** | 0.030 pass | 0 |
| P_recess 0.06 | negative | **no** | 29/0/0 | yes | 0.060 fail | 0 |
| P_recess 0.11 (KPP1-like) | negative, trigger witness | **no** | 29/0/0 | yes | 0.110 fail | 0 |
| P_recess 0.13 | negative | yes (FP_extra 1) | 28/1/0 | yes | 0.130 fail | 0 |
| P_recess 0.20 | negative | yes (FP_extra 1) | 28/1/0 | yes | 0.200 fail | 0 |
| P_corner 0.05 | negative | **no** | 29/0/0 | **no** | 0.035 pass | 0 |
| P_corner 0.10 | negative | yes | 27/2/0 | yes | 0.071 fail | 0 |
| P_corner 0.20 / 0.40 / 0.80 | negative | yes | 27/2, 26/3, 26/3 | yes | 0.141 / 0.283 / 0.566 fail | 0 |
| C_shift_opening | injected | yes | 28/1/0 | yes | 0.100 fail | 0 |
| C_shift_wall | injected | yes | 27/2/0 | yes | 0.100 fail | 0 |
| J1 / J2 / J3 | frozen_dump (not stability evidence) | yes / yes / yes | — | yes / yes / yes | 0.900 / 0.581 / 0.000 | 0 |

M43: baseline **8/12**, C1 **10/12**; accepted false fails 0 / 0. Keep threshold (≥ +2, 0 accepted fails, 0 changed
pre-existing items) met → C1 would be proposed; not applied (OBSERVE; frozen detector belongs to t_563a40f7).
Monotonicity: recess depth and chamfer leg ↑ → detection never lost (both ladders). Determinism: A extracted 3×,
1 distinct hash (paired spread 0).

Comparison with render judges (#41, same fragment, same plant code): judges caught P_recess 0.13 and P_corner 0.80
(baseline scene rubric too); Q4 render rubric was unstable on unchanged corners, the scene corner signal is a
deterministic number (0.071 m at 0.10 m leg). Judges on the small ladder: **not measured**.

## Clean / injected / not measured

- Clean (accepted) exercised: A, A_rt, C_none — new band items computed on real opening/reveal geometry, all pass.
- Injected exercised: 12 negatives, C_shift_opening, C_shift_wall. Frozen dumps J1–J3 only rescored.
- Not measured: KPP1 NW and Sokolniki (no exact-hash accepted/rejected body pair), any second fragment, other
  builders' accepted bodies (real jitter vs 0.05 m in the band), VLM judges on the small ladder, 3ds Max state.
- Known limitation of C1: one defect is now reported by up to 3 items (e.g. C_shift_opening) — counts, not
  verdicts, change; a v002 detector should de-duplicate if counts feed a score.

## Replay

```
R43=C:/x/autoresearch-body-form-r43   # or copy of G:/Мой диск/AGR-evidence/standing43-body-form-scene/
python $R43/run43.py <worktree>        # skips existing fbx/extract; delete fbx/ extract/ score/ for a cold run
```
Evidence `SHA256SUMS.txt` sha256 `f962c390…02bc` (117 files, verified on the Drive copy); `result43.json`
`4645e592…1be8`. Scripts also in this folder (`run43.py`, `plant43.py`). Replay limited to a PC with
`C:/x/t_563a40f7` (key + frozen detector, hashes in `receipt.json`) and `C:/x/review-k2` (A bytes).

## Next targets

1. Detector v002 card (owner of t_563a40f7 held-out): apply C1 as a new frozen version, then rerun on a second
   accepted fragment from another builder to measure band jitter vs 0.05 m before using it as a gate.
2. Same ladder on KPP1 NW once an exact-hash accepted/rejected body pair exists (110 mm recesses are the trigger).
3. VLM judges (#41 rig) on P_recess 0.06/0.11 and P_corner 0.10: does render see what C1 sees (yes-bias at small size)?
