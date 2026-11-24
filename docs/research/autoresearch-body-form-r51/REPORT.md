# Standing #51 — перенос детектора формы на 63B (OBSERVE)

**Кратко (RU).** Замороженный детектор формы t_563a40f7 (`extract.py` + `score_heldout.py`, байт-в-байт) впервые
запущен на втором здании — 63B, этаж +7,80…+10,95, восточный фасад, 5 окон по источнику. Ключ построен только из
`source_sections_and_openings.json` (без байтов тел). Результат: **порядок перевёрнут** — принятый v007 получил
F = 4 провала формы, отклонённые v002–v006 — F = 0 (медиана из 3 свежих импортов, размах 0 у всех).
Причина найдена (пост-хок, вне метрики): кольцо ключа — это контур сборщика v002, тот же, по которому строились
v002–v006; он закрывает нишу на фасаде. Сырые стены источника (`reference`) на внешней линии имеют разрыв
**3,414–4,718 м**, v007 показывает разрыв **3,444–4,715 м** (совпадение ≤ 0,03 м). Т. е. прав принятый v007, неверен
ключ. **Гипотеза H51: inconclusive** по замороженным правилам (отклонение контура v007 > 0,5 м на обоих сечениях,
не измерено 3/18 > 10 %, свидетель «сдвиг стены» замаскирован уже проваленным контуром). Готовность к ревью:
наблюдение готово; это не гейт. Внедрения нет.

## Measurement (contract `autoresearch-body-form-transfer63b.md`, frozen at d89197b2)

Run `C:/x/t_fb3a0b98-r51/run1`, status complete, wall 26.9 s (cap 3600 s, no budget stop), hash preflight and
postflight OK (source, key, detector vs t_563a40f7 SHA256SUMS, six evidence FBX). Blender 5.1, fresh import per rep.

| Body (exact evidence bytes) | Verdict | F median (3 reps) | spread | not measured / 18 | TP/FN/FP_extra | reveal depth read |
|---|---|---:|---:|---:|---|---|
| v007 `53189b83…` | accepted 2026-11-20 | **4** | 0 | 3 | 5/0/2 | 0.500 (detector cap 0.6) |
| v002 `a57cb3fb…` | rejected | 0 | 0 | 5 | 5/0/0 | 0.000 |
| v003 `83f3289c…` | rejected | 0 | 0 | 5 | 5/0/0 | 0.000 |
| v004 `6d22c572…` | rejected 2026-11-17 | 0 | 0 | 5 | 5/0/0 | 0.000 |
| v005 `a387a459…` | rejected 2026-11-18 | 0 | 0 | 5 | 5/0/0 | 0.000 |
| v006 `b2b26d44…` | rejected 2026-11-18 | 0 | 0 | 5 | 5/0/0 | 0.000 |
| W_shift_opening (v007 copy, 8 vertices) | planted | 5 | 0 | 3 | 5/0/2 | — |
| W_shift_wall (v007 copy, 714 vertices) | planted | 4 | 0 | 3 | 5/0/2 | — |

v007 failures (identical in all reps): `contour@16.85` and `contour@19.8` max 0.768 m at (87.39, 19.381) on seg 18;
`openings:no_extra_in_box` gaps seg 18 [3.444, 4.715] m and seg 15–16 [0.05, 0.678] m; window `194b464` edges 0.087 m.
Rejected v002–v006: all 13 measured F-items pass; all 5 `sill_head` not measured (no open back rim in the band).

- Clean: v007 and v002–v006 above. Injected: W_shift_opening fired (+1, `6189f94:edges` 0.100 m).
  **Not measured:** W_shift_wall — its target items already fail on v007 (masked by the 0.768 m pocket), F 4→4.
- Not in F: reveal depth (frozen scorer reads jamb points only within 0.6 m; source depth 0.71 → fail by construction),
  scope item. Not measured: KPP1 NW / Sokolniki (no exact body pairs), render judges, full-height curtains.

## Post-hoc diagnostic (outside the frozen metric)

`python docs/research/autoresearch-body-form-r51/posthoc51.py "<EV>/v002/source_sections_and_openings.json"` →
outer-line source walls on seg 18 for t 2.0–6.2 m: piers [2.612, 3.414] and [4.718, 5.595], gap **[3.414, 4.718]**,
set-back walls at d 0.25 / 0.5 m. The key ring spans straight across this gap; v002–v006 follow the ring. The seg 15–16
gap and the 0.087 m window edge were not diagnosed.

## Replay

`python docs/research/autoresearch-body-form-r51/make_key63b.py "<EV>/v002/source_sections_and_openings.json" C:/x/t_fb3a0b98-r51/key`
then `python docs/research/autoresearch-body-form-r51/run51.py <new dir>`; `<EV>` =
`G:/Мой диск/AGR-evidence/1619-body-training/tower-B`. Detector read-only from `C:/x/t_563a40f7/detector` (PC-limited).
Receipt: `receipt.json` here (SHA-256 bb000b9f552da263ce754081772f18b0f8d43da1b89e5b25571eeb81cb4a67a6).
Evidence (key, witnesses, receipt): `G:/Мой диск/AGR-evidence/standing51-body-form-transfer63b/`
(SHA256SUMS.txt f5dd88a472f4a8dc403a12d0bc53fc266f0b1baee3a3eba9a937f8f37c2fc197).

## Next targets

1. Key v002 from raw source outer-line walls (`reference`), not from a builder ring; same fixture/detector. Prediction:
   v007 contour/extra fails at [3.41, 4.72] vanish, v002–v006 gain them — the first real cross-building calibration.
2. Reveal depth: the 0.6 m jamb window is a G22 constant; v007 reads 0.500, the JSON says 0.71, source has set-back
   walls at 0.5 — decide the reference depth from source walls before any detector v002.
3. `sill_head` coverage: v002–v006 give 0/5 loops in the band — find why before counting their F = 0 as clean.
