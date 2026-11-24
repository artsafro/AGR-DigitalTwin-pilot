# Autoresearch standing #53 — 63B reveal back-rim coverage and depth reference (OBSERVE contract)

**Кратко (RU).** Продолжение #51/#52 (их «следующие цели» 2–3). Замороженный детектор t_563a40f7 на 63B не измеряет
`sill_head` в 28 из 30 пунктов (v007 3/5, v002–v006 5/5) и читает глубину откоса 0,000 у отклонённых. Диагноз по дампам
#51 (до контракта, только чтение): петли задних откосов есть у всех вариантов, но лежат на |d| = 0,50 м (v007) и
0,71 м (v002–v006) от линии фасада, а детектор ищет петлю в радиусе 0,5 м и точки откоса в окне 0,6 м — константы G22,
где глубина 0,10–0,15 м. Проверяем наблюдателем-надстройкой (детектор, ключ, допуски не меняются): (1) резервный поиск
петли откоса внутри проёма снимает «не измерено»; (2) глубина по задней петле (D037: «фасад → задний полигон»)
сравнивается с двумя эталонами — атрибутом `depth` ключа (0,71/0,713) и самой глубокой гранью стен источника за проёмом
(0,500 на всех 5 проёмах). Какой эталон верен — вопрос Артёму; здесь только замер. OBSERVE, без внедрения.

## Target and why

Focus «форма vs сетка» (card #53): reveal depth and unmeasured share. Not taken: Ground (#1738/#1816), build cards
(#1770/#1784/#1818), cold delivery #1315, atlas #1649, suite #1615, VLM judges #41/#45/#47/#49, section-conflict observer
#48/#50, wall-membership #44/#46, source wall mask #52 (other levels) — owned or done; KPP1 NW / Sokolniki — no exact body
pairs with verdicts.

## Fixtures (frozen; every byte pinned in `run53.py` PINS, preflight + postflight)

- 63B: the six exact #51 evidence FBX (`G:/Мой диск/AGR-evidence/1619-body-training/tower-B/v00N/63B_Stage1_v00N.fbx`):
  v007 accepted 2026-11-20 (`53189b83…`), v002–v006 rejected (`a57cb3fb…`, `83f3289c…`, `6d22c572…`, `a387a459…`,
  `b2b26d44…`). Key: `C:/x/t_fb3a0b98-r51/key` (heldout-key-v001 `67a1ae5b…`, sections `07ce9a5b…`), source JSON
  `f1865bdd…`. Rejection of v005 cites `2_frame_reveals.jpg`; other rejections are not depth-specific — the depth
  calibration below is per-variant ordering, not a claim about Artem's stated reason.
- G22 (accepted k2 v002r1 copy and its planted controls): `C:/x/t_563a40f7/controls/C_none.fbx` (`71eb9db8…`),
  `C_shift_opening.fbx` (`513d5ab4…`), `C_shift_wall.fbx` (`b79ecca6…`), key `C:/x/t_563a40f7/key`.
- Detector: `C:/x/t_563a40f7/detector/{extract.py ee50925b…, score_heldout.py e9d6f65b…}` byte-identical, read-only.
- Witness `W_deep` (positive trigger, made by `mutate53.py` on a copy of v007): back-rim vertices of window `6189f94`
  (seg 18, t 5.5946–7.3046 m, |d_in − 0.50| ≤ 0.01, real z 8.47–10.46) moved inward to d_in = 0.71.
- R_face (source-only, computed before any body measurement, from `modules.A.reference`): deepest source wall face
  parallel to the facade (|Δd| ≤ 0.01 between ends, 0.05 < |d| ≤ 1.5) covering ≥ 95 % of the opening span:
  **0.500 m for all five openings** (faces at 0.25 and 0.50 cover 100 %; nothing deeper overlaps). Key `depth` 0.71/0.713.

## Candidate overlay `score53.py` (the frozen score report is kept unchanged and stored next to it)

Per key opening, with the frozen gap `g` at 18.2 (same code path as the frozen scorer):
1. Rim loop = the frozen match (band loop within 0.5 m of the gap midpoint). Only if none: fallback = band loops whose
   centroid has local t inside `g` and 0.02 < |d| ≤ 1.5 m; take the one with t closest to the gap mid.
2. `sill_head_c` = frozen formula on the rim loop (tolerance 0.02 unchanged); frozen measured statuses must be identical.
3. `depth_rim` = |d| of the rim loop centroid. Items `depth_vs_key` and `depth_vs_face` (tolerance 0.015 = frozen
   `reveal_depth_m`); `not_measured` when there is no rim loop or the opening is missing.

## Metrics, bounds and keep rule

- **M1 (primary, one number):** not-measured count over {`sill_head_c`, `depth_rim`} on 5 openings × 6 labelled 63B
  variants = 60 items; frozen baseline for sill_head 28/30. Expected 0 in every repetition, spread 0.
- **M2 parity:** frozen measured items whose status changes under the overlay = 0 on all fixtures (G22 and 63B).
- **M3 calibration, reported per reference:** depth fails per variant; D_ref = rejected variants with depth fails ≤
  v007. Expected R_face: v007 rim 0.500 ± 0.015 (0 fails), each rejected 0.71 ± 0.015 (5 fails) → D_face = 0;
  R_key: inverted → D_key = 5.
- **M4 rim readout on an accepted body of another building:** G22 C_none `depth_rim` vs key depth, expected 6/6 within
  0.015. On G22 the fallback is expected `not_exercised` (frozen has 0 not-measured there) — reported as not measured.
- **Witness W_deep:** opening 6189f94 depth_rim 0.500 → 0.710 ± 0.015 and depth_vs_face pass → fail; other 4 openings
  changed depth/sill items = 0 (locality). G22 C_shift_opening / C_shift_wall: per-opening depth_rim changes vs C_none
  recorded (expected 0 for shift_wall — whole plane moves; shift_opening moves jambs along the facade only).
- **H53 confirmed** iff M1 = 0 in all 3 reps, M2 = 0, M4 6/6, witness within bounds with locality, D_face = 0.
  **Refuted** if M4 < 6/6, the witness does not fire, or D_face > 0. Otherwise inconclusive. A confirmed H53 is an
  OBSERVE finding: no detector, key or tolerance change; the reference choice R_face vs R_key is Artem's.

## Budget, stop rule, forbidden

- One series: 10 fixtures (6 labelled 63B + W_deep + 3 G22) × 3 fresh Blender 5.1 imports; wall cap 1800 s,
  timing recorded separately from status; a cap hit = `budget_stop` → inconclusive for that run, not a hypothesis change.
- Up to 3 repair attempts of the harness, each logged with its error; no repeat of the same approach.
- Forbidden: editing the detector, keys, tolerances, evidence FBX or delivered packages; deselecting fixtures;
  rescoring frozen dumps as stability evidence; touching other cards' files.

## Replay

`python docs/research/autoresearch-body-form-r53/run53.py <new dir>` (dir must not exist). Replay limited to this PC
(`C:/x/t_563a40f7`, `C:/x/t_fb3a0b98-r51`, Google Drive evidence); every input is hash-pinned and checked pre/post.
