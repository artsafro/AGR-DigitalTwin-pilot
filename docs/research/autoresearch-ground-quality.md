# Autoresearch standing #31: calibrated Ground NPM quality number (OBSERVE)

Card t_193a0887, branch `research/autoresearch-standing-31`. Focus set by Artem 2026-11-21 («Переключай»: Ground).
Mode: OBSERVE only. No Ground is built or repaired here (that is #1738); no delivered package is edited.

## Краткий итог (по-русски)

**Гипотеза H31 опровергнута.** Замороженная метрика Q (xView-вершины + xView-грани + трещины на 10 000
треугольников) не отделяет сданные Артёмом Ground от отклонённых SIL13: принятый COD (A3) получает 596,2, а
худший по порогу отклонённый r4 (F4) — 429,0. Отрыв −167,3 (нужно > 0 и двукратный запас). Внедрения нет.

Что держится: совпадение с квитанциями r2–r5 точное (16/1 767, 16/1 751, 27/1 576, 16/1 751; r1 — 843
открытых ребра), три повтора дают одно число, поворот и сдвиг не меняют Q, внесённые 50 разрывов всегда
поднимают Q выше границы.

Почему не вышло: у 6 из 7 сданных Ground NTR ядро xView находит перекрытые грани (16–465 на объект), а у
Vatutino — 334 «трещины» (совпадающие открытые рёбра слоёного пирога). Наблюдение для следующей карточки
(не проверялось как кандидат): близкие вершины xView равны 0 на всех 8 принятых и 1 576–1 769 на всех
отклонённых.

## 1. Contract (frozen before any measurement)

### Metric

`Q` = Ground defect density, defects per 10 000 triangles, lower is better:

    Q = 1e4 * (V + F + C) / T

- `V` = xView overlapping vertices, `F` = xView overlapping faces: the repo kernel `dt_ai.ops.xview_gate.gate_report`
  (inv_xview, profile NPM: vertex 2 mm, face 5 mm, parallel cos 0.9999), coords `local`, summed over the mesh parts.
- `C` = crack edges: open (one-face) edges whose midpoint lies within 5 mm (xView face_m) of another open edge of the same
  part that shares no vertex index with it (unstitched seam / T-junction). The true outer border and building holes
  are open edges too but have no coincident open partner, so they do not count.
- `T` = triangles after fan triangulation (a k-gon counts k-2), summed over the parts.
- Parts whose name starts with `UCX_` are ignored (collision, not render mesh).

One number per input. Components V, F, C, T and the per-part table are published next to Q.

**Amendment 1 (before the series, after the dump):** the delivered NTR `*_Ground.fbx` files carry the whole site
package (objects `*_Ground`, `*_GroundEl`, `*_GroundElGlass`, `*_Flora`). The fixture is the Ground surface, so
the scored parts are the objects whose name ends with `_Ground` (one per input; SIL13 `SM_SIL13_Ground`, Vatutino
`SM_Vatutino_Ground`). The all-parts score is published next to it as `Q_all` (secondary, not used for the
verdict). Seen before this amendment: probe scores of A1, A2 (all parts) and F5 only (first-pair timing).
F3 and F5 dumps are byte-identical (r5 changed no geometry), so the fixture has 4 distinct failed meshes.

### Fixture (frozen; SHA-256 in `docs/research/autoresearch-ground-quality-harness/inputs.sha256`)

Accepted (A), Artem's own delivered NPM Ground (latest revision folder, read-only originals in
`C:/Users/artsafro/Desktop/!3D viz/NTR/`, byte-identical copies in `C:/x/ground-etalons/` and
`C:/x/ev_t_193a0887/inputs/`), plus the accepted Vatutino precedent:

| id | source | why accepted |
|---|---|---|
| A1 | Vatutino Ground v015 NPM, `session-v001.zip!artefacts/ground-v015-dcc-v001/textured/npm/SM_Vatutino_Ground.fbx` (`G:/Мой диск/AGR-evidence/371-ground-v015-route-a-20261104/`) | D193, docs/cases.md |
| A2 | 14_Skolkovo `pravki_15.09/LP/0809_BolshoyBulvar_64_Ground.fbx` | delivered (NTR) |
| A3 | 22_COD `maps/low/0309_Tup_Skladochnyj_ZU_5_1_Ground.fbx` | delivered (NTR) |
| A4 | 29_Donskoy `0610_5jDonskoyProezd_Vl_15/0610_5jDonskoyProezd_Vl_15_Ground.fbx` | delivered (NTR) |
| A5 | 31_Ostrov `0906_NizhnieMnevniki_ZU_66_Ground.fbx` | delivered (NTR) |
| A6 | 32_Kasatkino `blender/0301_Kasatkina_Vl_11/0301_Kasatkina_Vl_11_Ground.fbx` | delivered (NTR) |
| A7 | 6 (Volokolamskoe) `0903_VolokolamskoeShosse_Vl_71_22_Ground.fbx` | delivered (NTR) |
| A8 | Stolbovo `1113_DerevnyaStolbovo_Uch_23_Ground.fbx` | delivered (NTR) |

Failed (F), SIL13 #1315 NPM Ground pilots, not adopted / rejected
(`G:/Мой диск/AGR-evidence/1315-cold-silikatny/`):

| id | file | receipt |
|---|---|---|
| F1 | `npm-ground-stitch-r1-NOT-ADOPTED/pilot/geometry.npz` | 843 one-face edges, stopped before FBX |
| F2 | `npm-ground-stitch-r2-BUDGET-CHOICE-NOT-ADOPTED/working-xview-input.npz` | xView 16 / 1 767, budget 187 102 |
| F3 | `npm-option-a-ground-r3-NOT-ADOPTED/ground-micro.npz` | xView 16 / 1 751 |
| F4 | `npm-ground-reprofile-r4-REJECTED/ground.npz` | xView 27 / 1 576 |
| F5 | `npm-ground-retess-r5-REJECTED/ground.npz` | xView 16 / 1 751 |

VPM: there is no rejected SIL13 VPM Ground, so VPM is **not measured** in this calibration (VPM copies of the
delivered packages are listed in the harness for the next lane only).

FBX inputs are dumped once with the repo dump `tools/blender/xview_dump.py` (Blender 5.1, read-only on the source)
and converted to metres with `xview_gate.to_metres`; the metre dumps are hash-bound in `dumps.sha256`. F1 is
converted from its `vertices/faces` arrays to the dump format (one part `SM_SIL13_Ground`, location 0).

### Calibration rule (keep threshold)

The metric is **calibrated** only if all of these hold:

1. Separation: `min Q(F) > max Q(A)` and `min Q(F) >= 2 * max(max Q(A), 1.0)`.
2. Parity: V and F on F2-F5 equal the sealed receipts above (16/1 767, 16/1 751, 27/1 576, 16/1 751) exactly; F1
   one-face edges = 843.
3. Repeat: three runs per input give byte-identical Q (spread 0; median of 3 is reported).
4. Rigid-motion stability (representative perturbation, every input): translate (+123.456, -78.9, +3.21) m and
   rotate 30 deg about Z (vertices and object location). Expected direction: none. Bound per input:
   `|Q' - Q| <= max(0.01 * Q, 0.1)`.
5. Positive trigger witness (injected, every accepted input): unweld 50 interior vertices (deterministic choice:
   every k-th interior vertex of the first part, k = n_interior // 50) by moving one incident face's corner to a new
   vertex shifted 1 mm along +X. Expected direction: up. Bound: `Q_inj - Q >= 0.5 * 1e4 * 100 / T` (each unweld
   adds at least 2 near vertices).
6. Accepted control on which the rule fires: an accepted input with `V + F + C > 0`. If none exists, this is
   recorded as **not measured** (the rule never fires on an accepted package in this fixture) and collateral
   impact on accepted work is unknown, not zero.

Hypothesis H31: Q is calibrated (1-5 hold). `confirmed` if 1-5 hold, `refuted` if 1 or 2 fails, `inconclusive` if
the series does not fit the budget or 3-5 cannot be run.

### Budget and stop rule

- Core budget: 90 min wall for dumps + 3 repeats + perturbation + injection; frozen after the first measured
  input pair (one A, one F). If the series does not fit, publish `inconclusive` and the exact next command; never
  shorten the series silently.
- Confirm-vs-new-candidate: no second metric candidate in this card. If H31 is refuted, the card records which
  inputs break the order and stops (one candidate, one confirmation).
- Then (only if calibrated): score the first Ground built by the #1738 core. If it does not exist yet, record
  **not measured** and the exact command.

### Forbidden shortcuts

Dropping or replacing an input after seeing its score; changing the xView tolerances; editing delivered packages,
the SIL13 evidence or other cards' files (`C:/x/ground-etalons/` is read only here); counting the outer border as
defects; deselecting tests; any auto-applied change to delivered work.

### Not measured (by design)

NPM triangle budget (site-level, 180 000 for SIL13; failed variants do not differ by intrinsic quality there);
visible deviation of elevations/borders from the source; skirt height >= 1 m (needs the source footprint, #1738
validator); VPM.

### Replay

    uv run python docs/research/autoresearch-ground-quality-harness/dump.py    # FBX/NPZ -> metre dumps
    uv run python docs/research/autoresearch-ground-quality-harness/score.py --out <new.json>

Inputs: `C:/x/ev_t_193a0887/inputs/` (copies; originals and hashes above). Replay is limited to this PC (the inputs
are customer packages and are not committed).

## 2. Round log

Contract commit c21df288; harness + amendment 1 ccedad3b; injection fix 85b28693 (the first series injected into
`parts[0]`, which is Flora on A3-A8; it was stopped after A1-A6, whose clean and rigid rows are byte-identical to
the second series; only the injection rows changed). Receipt: `docs/research/autoresearch-ground-quality-harness/r31.json`
(= `C:/x/ev_t_193a0887/r31b.json` with CRLF -> LF; SHA-256 committed LF `f409f12d9520a5553ec31627a8d059b06856d3bc5cbdb1bb5e5bbee63bde1963`, scratch CRLF `4d0fe3d6570f81c1ef05edc8fdbc131409b5796253f992a62fb506c383ca3870`).
Dumps: `dumps.sha256` (metres, Blender 5.1.2, all METRIC scale 1.0, 0 dropped objects).

Budget: first pair (A1 + F5) scored in about 8 s; the full series (13 inputs x 3 repeats + rigid + inject) took
about 11 min, inside the 90 min budget. No series was shortened.

| id | input | V | F | C | T | Q (median of 3) | spread | rigid dQ | inject dQ (bound) | Q_all |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1 | Vatutino v015 NPM | 0 | 0 | 334 | 46 479 | 71.860 | 0 | 0 | +44.8 (10.8) | 71.9 |
| A2 | Skolkovo | 0 | 16 | 0 | 5 733 | 27.909 | 0 | 0 | +355.8 (87.2) | 10.4 |
| A3 | COD | 0 | 86 | 81 | 2 801 | **596.216** | 0 | 0 | +803.3 (178.5) | 66.4 |
| A4 | Donskoy | 0 | 328 | 2 | 11 528 | 286.260 | 0 | 0 | +111.9 (43.4) | 4 397.1 |
| A5 | Ostrov | 0 | 81 | 0 | 29 760 | 27.218 | 0 | 0 | +81.0 (16.8) | 675.7 |
| A6 | Kasatkino | 0 | 465 | 1 | 59 290 | 78.597 | 0 | 0 | +28.8 (8.4) | 330.9 |
| A7 | Volokolamskoe | 0 | 217 | 0 | 20 614 | 105.268 | 0 | 0 | +97.0 (24.3) | 1 195.8 |
| A8 | Stolbovo | 0 | 0 | 0 | 10 930 | 0.000 | 0 | 0 | +249.8 (45.7) | 0.0 |
| F1 | SIL13 r1 | 1 769 | 16 | 5 | 36 549 | 489.753 | 0 | 0 | - | 489.8 |
| F2 | SIL13 r2 | 1 767 | 16 | 0 | 37 386 | 476.916 | 0 | 0 | - | 476.9 |
| F3 | SIL13 r3 | 1 751 | 16 | 0 | 37 370 | 472.839 | 0 | 0 | - | 472.8 |
| F4 | SIL13 r4 | 1 576 | 27 | 0 | 37 370 | **428.954** | 0 | 0 | - | 429.0 |
| F5 | SIL13 r5 | 1 751 | 16 | 0 | 37 370 | 472.839 | 0 | 0 | - | 472.8 |

Checks against the calibration rule:

| # | check | result |
|---|---|---|
| 1 | separation `min Q(F) > max Q(A)`, x2 margin | **fail**: 428.954 (F4) < 596.216 (A3); x2 margin also fails on A4 (286.260 > 214.477) |
| 2 | parity with sealed receipts | pass: F2 16/1 767, F3 16/1 751, F4 27/1 576, F5 16/1 751; F1 843 open edges |
| 3 | repeat (3 runs) | pass: spread 0 on all 13 |
| 4 | rigid motion | pass: dQ = 0 on all 13 |
| 5 | injected positive witness | pass: every accepted input rises above its bound |
| 6 | accepted control on which the rule fires | measured: the rule fires on 7 of 8 accepted (F on A2-A7, C on A1, A3, A4, A6) |

**H31: refuted** (check 1). Inputs that break the order: A3 (Q above every failed variant) and A4 (inside the x2
margin). Clean = rows above; injected = inject column; not measured = VPM, budget, visible deviation, skirt height,
#1738 core Ground (no build exists yet: no PR or output for #1738 on 2026-11-21 11:15).

Observation only (not a candidate of this card, not tested for stability on its own): the near-vertex count V is 0
on all 8 accepted and 1 576-1 769 on all failed meshes; the face-overlap count F of the repo kernel is non-zero on 6
of 7 delivered NTR Ground objects although Artem delivered them; the crack count C fires on the accepted Vatutino
layered cake (334 coincident open edges). A next card can freeze `V / T` as its single candidate, with a positive
witness that is not SIL13 and an independent rejected set (all four distinct failed meshes come from one SIL13
source mesh, so they are not independent evidence).

Side finding (not fixed here): `tools/blender/xview_dump.py` imports FBX with the default `use_image_search=True`;
on A3 (COD) Blender 5.1.2 ran > 17 min without finishing (flat memory), while the same import with image search
off takes 1.3 s. `dt qa xview <fbx>` inherits this. The harness goes FBX -> .blend (`fbx_to_blend.py`, image search
off) -> unchanged repo dump.
