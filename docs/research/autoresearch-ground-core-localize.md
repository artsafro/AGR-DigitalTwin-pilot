# Standing #37 — Qe on the merged #1738 core output, stage localisation (OBSERVE)

Card t_e5884443, branch `research/autoresearch-standing-37`. Focus: Ground quality (Artem 2026-11-21 «Переключай»).
Mode: OBSERVE only. No Ground is built or repaired here (#1738 owns it); the core OBJs are read, never rewritten.
No delivered package and no other card's file is edited.

## Итог (по-русски)

**H37 опровергнута (только OBSERVE, ничего не внедряется).** Короткие рёбра (≤ 2 мм) в Ground влитого ядра
#1738 (ab5a8f4d, вывод v006) появляются **не на этапе плоской разбивки, а на этапе рельефа**.

- SIL13, ядро v006 (те же байты, что v003 из #35): E = 185, T = 26 491, Qe = **69,84** (совпадает с #35).
  По этапам: рельеф **167**, юбка 9, стык «верх/юбка» 9, плоская разбивка **0** (0 %, порог гипотезы 90 %).
  У всех 167 рельефных рёбер **оба конца — новые вершины**, которых нет в `ground-flat.obj`. 128 из 167 лежат
  внутри плоских граней, 39 — на рёбрах разбивки (вставлены при разрезании). 17 рёбер нулевой длины, 9 на открытой
  границе (это юбка), на границе материалов — 0.
- Ватутино, ядро v006 (раньше не измерялось): E = **3**, Qe = **1,20** против **0** у принятого Артёмом v015. Ядро
  добавляет короткие рёбра даже на исходниках принятого участка: рельеф 2, плоская разбивка 1 (1,5 мм, отрезок по
  одной оси; 1 ребро на границе двух плиток).
- Проверки: 3 повтора и повторный запуск дают тот же результат; сдвиг с поворотом на 30° не меняют E, T и классы;
  50 внесённых рёбер на Ватутино видны (3 → 53); сумма классов = E. Счёт E, T совпадает с #35.
- Для #1738 (без ремонта, только адрес): если нужен Qe = 0, расстояние между вершинами нужно ограничивать на этапе
  **рельефа** (вставка/разрезание), а не разбивки. Координаты первых 400 рёбер лежат в квитанции (`rows.*.samples`).
- Не измерено: нативный 3ds Max; принятый контроль, на котором правило срабатывает (у принятых Ground E = 0, а
  Ватутино ядра не принят: в его отчёте `geometry_status: fail`).

## Why this candidate (continuing #35/#36, no new harness)

- #35 froze Qe = 1e4 · E / T, E = edges ≤ 2 mm (`inv_xview.tolerance_for('NPM').vertex_m`) on `*_Ground`; 0 on 8
  accepted, 215.95–250.35 on SIL13 r1–r5. #36 carried it to three paired NPM/VPM etalons (all 0).
- Open next targets (#35/#36 backlog): score the next published #1738 OBJ; localise the 185 short edges of the core
  SIL13 OBJ and hand them to #1738 without repair.
- PR #1787 (#1738 core) is merged at `ab5a8f4d`; its v006 outputs `C:/x/ev_t193/*_shared_v006/` are the merged-core
  Ground. SIL13 `SM_SIL13_Ground.obj` is byte-identical to the v003 that #35 scored (sha256 `8f519409…`). The
  Vatutino shared OBJ (`2ba2811d…`, the core on the site whose v015 Artem accepted) was never scored.
- Not taken: building/repair/skirt (#1738/#1787), cold delivery (#1315/#1622), body mesh (closed), atlas (#1649),
  suite speed (#1615).

## Frozen contract (before any score)

**Metric** (unchanged from #35): Qe = 1e4 · E / T on the single `o SM_*_Ground` object of the core OBJ (groups
`ground` + `skirt`), E = unique undirected edges with 3D length ≤ 0.002 m, T = Σ(len(face) − 2).

**Localisation** (new, read-only) — every short edge of the final OBJ gets exactly one class:
1. `skirt` — every face using the edge is in group `skirt`;
2. `seam` — the edge touches the `skirt` group and the `ground` group (top/skirt junction);
3. `flat` — both endpoints match (XY ≤ 1e-6 m) vertices of the same core run's `ground-flat.obj` and that vertex pair
   is an edge of `ground-flat.obj` (born in the flat partition stage, Z = level·step);
4. `relief` — any other `ground` edge (born after the flat stage: relief/refinement).
Sub-labels recorded, not scored: zero length (≤ 1e-9 m), on an open border, on a material boundary (faces with
different `usemtl`).

**Hypothesis H37** (frozen): the merged core's short edges are born in the flat partition stage:
(a) on SIL13 core v006, `flat` ≥ 90 % of E; and (b) the Vatutino core v006 Qe = 0 (the core adds no short edges on
the accepted site's sources). Confirmed only if (a) and (b) hold and all checks are green; refuted otherwise;
inconclusive if the series does not finish within the cap.

**Inputs (hash-bound, read-only)**:
| id | path | sha256 |
|---|---|---|
| C1 SIL13 core | `C:/x/ev_t193/sil13_shared_v006/SM_SIL13_Ground.obj` | `8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450` |
| C1 flat | `C:/x/ev_t193/sil13_shared_v006/ground-flat.obj` | recorded in the receipt (`fdda9363…`) |
| C2 Vatutino core | `C:/x/ev_t193/vatutino_shared_v006/SM_VATUTINO_Ground.obj` | recorded in the receipt (`2ba2811d…`) |
| C2 flat | `C:/x/ev_t193/vatutino_shared_v006/ground-flat.obj` | recorded in the receipt (`be4268b7…`) |

**Checks** (recorded separately as clean / injected / not measured):
- parity: C1 (E, T) = (185, 26491) of the #35 receipt `core.clean_runs[0]`;
- 3 repeats identical; rigid shift (+1000, −2000, +50 m) and 30° Z-rotation keep E, T and every class count;
- injection on C2: 50 interior vertices moved 1 mm onto a neighbour (the #35 `inject`) → E rises ≥ 25, T unchanged;
- class partition: classes sum to E on every input.
- Not measured: native 3ds Max; an accepted control where the rule fires (no accepted Ground has E > 0; C2 is not
  accepted — its own report is `geometry_status: fail`).

**Positive trigger witness**: C1 (E = 185 > 0). **Expected direction**: C1 > 0, C2 ≥ 0 (no prediction of the value).

**Budget**: one pass ≈ seconds (#35 core in < 2 s); cap 300 s for the whole series, 1 round, no new candidate
beyond H37. Stop rule: one round, then report. **Forbidden**: changing the 2 mm tolerance, dropping skirt faces from
E, editing core outputs or etalons, editing #1738 files.

**Replay**: `../../.venv/Scripts/python.exe docs/research/autoresearch-ground-core-localize-r37.py C:/x/ev_t_e5884443/NEW.json`
(replay limited to this PC: inputs are under `C:/x/ev_t193`; also mirrored with hashes in the #1738 evidence folder
`G:/Мой диск/AGR-evidence/1738-ground-shared-core/`).

## Round log

Round 1 (only round; stop rule reached). Variant: Qe = 1e4·E(≤ 2 mm)/T, #35 tolerance, stage classes as frozen.
Receipt `docs/research/autoresearch-ground-core-localize-r37.json` (sha256 in the PR body / backlog); replay into
`C:/x/ev_t_e5884443/r37-replay.json` is identical except `series_seconds` (1.90 s / 1.74 s, cap 300 s).

| id | sha256 (OBJ / flat) | E | T | Qe | flat | relief | seam | skirt | zero | open | mtl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 SIL13 core v006 | `8f519409…` / `fdda9363…` | 185 | 26491 | 69.835 | 0 | 167 | 9 | 9 | 17 | 9 | 0 |
| C2 Vatutino core v006 | `2ba2811d…` / `be4268b7…` | 3 | 25011 | 1.199 | 1 | 2 | 0 | 0 | 0 | 0 | 1 |

Relief detail (diagnostic, not scored): C1 167/167 ground-only short edges have 0 endpoints on a flat vertex;
endpoints on a flat edge 0/1/2 = 128/17/22. C2: on flat vertex 2/0 = 1/2; on flat edge 2/1 = 1/2.
Matcher sanity (scratch probe, same functions): 9 954 of 34 784 C1 ground edges and 17 978 of 31 297 C2 ground edges
classify as `flat`, so a 0 % flat share is not a matcher failure.

Checks — clean: repeats ✓, rigid E/T ✓, rigid classes ✓ (flat index moved jointly), partition ✓, parity #35
(185, 26491) ✓. Injected: C2 +50 moved → E 3 → 53, T unchanged ✓. Not measured: native Max; accepted control that
fires.

**H37: refuted** — (a) flat share 0.0 < 0.9; (b) C2 Qe 1.20 ≠ 0. Review readiness is separate: no code is kept.
