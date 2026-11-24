# Standing #53 — Round log (OBSERVE)

**Кратко (RU).** Гипотеза **H53 подтверждена** (наблюдение, не гейт). На 63B (вост. фасад, этаж +7,80, 5 окон) замороженный
детектор t_563a40f7 не измерял `sill_head` в 28 из 30 пунктов и читал глубину откоса 0,000 у отклонённых вариантов —
из-за констант G22 (радиус 0,5 м до петли откоса, окно 0,6 м), а не из-за тел. Надстройка `score53.py` (детектор, ключ,
допуски не менялись) ищет заднюю петлю откоса внутри проёма и берёт глубину по ней (D037: «фасад → задний полигон»):
не измерено **28 → 0** из 60 пунктов во всех трёх повторах, размах 0; ни один ранее измеренный пункт не изменился.
Считывание проверено на принятом G22 к.2: 6/6 глубин совпали с ключом (0,10–0,15 м). Порядок принятый/отклонённые
зависит от эталона глубины: по самой глубокой грани стен источника за проёмом (**0,50 м**) принятый v007 — 0 провалов,
каждый из v002–v006 — 5 (глубина 0,71); по атрибуту `depth` ключа (**0,71/0,713**) — наоборот. **Вопрос Артёму:**
какая глубина откоса 63B верна — 0,50 (грани стен; так собран принятый v007) или 0,71 (атрибут проёмов источника)?
Внедрения и PR нет.

## Measured run

Contract [`../autoresearch-body-form-r53.md`](../autoresearch-body-form-r53.md) and harness frozen at `0643b0b1`
before any measurement. Run `C:/x/t_1276e6bc-r53/run01`: status `complete`, wall 32.9 s (cap 1800 s, no budget stop),
30 fresh Blender 5.1 extract imports + 1 witness build, preflight and postflight OK (source, two keys, detector, nine FBX).
Receipt [`receipt.json`](receipt.json), SHA-256 `68f7c1df15501edff195790cd402326c4db7663d5bbf2c3167bf8746cd8cc4a4`.

| Fixture (exact bytes) | Verdict | not measured (overlay / frozen sill) | fallback rims | depth_rim per opening, m | fails vs key / vs R_face |
|---|---|---|---:|---|---|
| v007 `53189b83…` | accepted 2026-11-20 | 0 / 3 | 3 | 0.500 ×5 (±0.0001) | 5 / **0** |
| v002 `a57cb3fb…` | rejected | 0 / 5 | 5 | 0.710, 0.710, 0.710, 0.713, 0.713 | 0 / **5** |
| v003 `83f3289c…` | rejected | 0 / 5 | 5 | same as v002 | 0 / **5** |
| v004 `6d22c572…` | rejected 2026-11-17 | 0 / 5 | 5 | same as v002 | 0 / **5** |
| v005 `a387a459…` | rejected 2026-11-18 | 0 / 5 | 5 | same as v002 | 0 / **5** |
| v006 `b2b26d44…` | rejected 2026-11-18 | 0 / 5 | 5 | 0.710 ×5 | 0 / **5** |
| W_deep (v007 copy, 4 vertices) | planted | 0 / 3 | 3 | 6189f94: 0.500 → 0.710 | 4 / 1 |
| G22 C_none `71eb9db8…` | accepted k2 v002r1 copy | 0 / 0 | 0 | 0.150, 0.100, 0.130, 0.100, 0.150, 0.130 = key | 0 / n.a. |
| G22 C_shift_opening, C_shift_wall | planted | 0 / 0 | 0 | identical to C_none | 0 / n.a. |

All values identical in the three repetitions (per-opening payload identical, spread 0).

- **M1** not measured over {sill_head_c, depth_rim} on 60 labelled items: 0 / 0 / 0 (frozen sill_head alone: 28/30).
- **M2** frozen measured items changed by the overlay: none (G22 and 63B).
- **M3** D_face = 0 (every rejected variant worse than v007), D_key = 5 (every rejected variant not worse).
- **M4** G22 C_none rim depth vs key: 6/6/6.
- **Witness** W_deep: target 0.500 → 0.7098 m, depth_vs_face pass → fail, other 4 openings 0 changed items, all reps.

### Clean / injected / not measured

- **Clean:** the six labelled 63B bodies and G22 C_none above; frozen reports kept next to each overlay.
- **Injected:** W_deep fired with locality. G22 C_shift_opening / C_shift_wall: rim depth changed on 0/6 openings —
  expected for shift_opening; for shift_wall it exposes a **blind spot**: depth_rim is measured from the KEY facade line,
  so a moved candidate facade does not change it (the frozen contour items catch that move, 2 fails). A reveal-depth gate
  would need facade-to-rim distance per candidate; not built here.
- **Not measured:** the fallback on G22 (`not_exercised`: 0 frozen not-measured items there); sill heights beyond
  presence (all rims sit within 0.02 m of the key, so sill_head does not separate A from R); other 63B facades/levels;
  KPP1 NW / Sokolniki (no exact body pairs); render judges. The six variants are one builder lineage, not six buildings.

## What would change (OBSERVE, not applied)

1. In a detector v002 (new frozen version, not t_563a40f7 v001): rim-loop fallback inside the frozen gap and depth from
   the back rim measured against the candidate's own facade line, not the key line.
2. Before any depth gate on 63B: Artem's choice of the reveal reference (0.50 faces vs 0.71 attribute). D037 says
   one opening depth per building, measured facade → back polygon; the source JSON `depth` 0.71/0.713 has no wall face
   behind it (deepest face 0.50 over 100 % of every span).

## Replay

`python docs/research/autoresearch-body-form-r53/run53.py <new dir>` — this PC only (`C:/x/t_563a40f7`,
`C:/x/t_fb3a0b98-r51`, Google Drive tower-B evidence); every input hash-pinned pre/post. Evidence (receipt, R_face,
W_deep.fbx, two overlays): `G:/Мой диск/AGR-evidence/standing53-body-form-reveal-rim/` (SHA256SUMS.txt
`f7ce7db128b62a37bef98a1e2f57ba827248ace7d904efebd7870fc110ba0c58`).

Pre-contract diagnosis (read-only on #51 run1 dumps, not evidence): band loops nearest each gap mid sit at 0.50 m
(v007; floating-point 0.4999/0.5001 decides the frozen 0.5 m match → 2 pass / 3 not measured) and 0.71 m (v002–v006).
