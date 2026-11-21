# Standing #35 — Ground short-edge density Qe (OBSERVE)

Card t_f4f34f04, branch `research/autoresearch-standing-35`. Focus: Ground quality (Artem 2026-11-21 «Переключай»).
Mode: OBSERVE only. No Ground is built or repaired here (#1738 owns it). No delivered package and no other card's
file is edited.

## Итог (по-русски)

**H35 подтверждена на замороженном НПМ-наборе (только OBSERVE, порог в код не вносится).** Qe — число рёбер
короче 2 мм на 10 000 треугольников объекта `*_Ground`. У Ватутино v015 и всех семи сданных Артёмом NTR Ground
Qe = **0**. У SIL13 r1–r5 Qe = **215,95–250,35** (807–915 коротких рёбер). Отрыв +215,95 при требуемом
двукратном запасе от 1.

Чем Qe лучше Qv из #32: это тот же дефект SIL13 (на r4 1 574 из 1 576 близких вершин — концы коротких рёбер),
но Qe **не меняется** при расщеплении немногообразных вершин, как в Max `convertToPoly`. Разрезание вееров
поднимает Qv принятого Ватутино v015 с 0 до 118, COD — до 14. Qe не меняется ни на одном из 14 входов.

Все проверки прошли: T и V совпадают с #32, три повтора и повторный запуск дают те же числа, поворот и сдвиг
не меняют E и T, 50 внесённых коротких рёбер видны на каждом принятом входе (+50).

Ядро #1738, SIL13 shared v003 (опубликованный OBJ): Qe = **69,84** (185 коротких рёбер, из них 17 нулевой
длины). Это лучше всех пяти отклонённых, но не 0, как у принятых. Порогом сдачи это не является.

Ограничения: (1) ни один принятый вход не даёт E > 0, поэтому влияние правила на принятые работы не измерено;
(2) все пять отклонённых получены из одного меша SIL13, независимого отклонённого участка нет; (3) отклонённый
Ватутино v014 даёт 0, как и ожидалось до замера: его дефект — немногообразные вершины, они есть и у сданных NTR;
(4) нативный Max не измерялся. Модель расщепления воспроизводит 118 вершин #370 на v014, но не 278–580 у Max
на A3–A6. Max делает больше, чем разрезает веера.

## Why this candidate (continuing #31–#34, no new harness)

- #31 `Q = V+F+C` refuted (the delivered COD has many overlapping faces).
- #32 `Qv` (near vertices ≤ 2 mm) separates the frozen corpus on the Blender readback (0 vs 421–484). But #33 showed
  that 3ds Max `convertToPoly` splits non-manifold vertices into coincident copies, so native Max finds 278–580
  near vertices on four delivered NTR Ground. That makes Qv depend on the node state.
- #34 `Qfan` refuted (non-manifold fans: 0 on SIL13, 25 on the delivered COD).

H35 tests the *connected* part of the SIL13 defect: edges shorter than the xView vertex tolerance (slivers and
collapsed stitch edges). Splitting a non-manifold vertex creates coincident copies with **no** edge between them,
and every edge keeps its two endpoints' positions. So Qe is unchanged by construction under the Max-like split, unlike
Qv. Whether SIL13's 1 576–1 769 near vertices are connected by edges at all is unknown before this measurement.

## Frozen contract (before any score)

**Metric.** `Qe = 1e4 * E / T`, lower is better. `E` = unique undirected index edges of the polygon faces of the
scored part (consecutive corners including last→first; an edge (a,b) with a == b counts) with Euclidean length
`<= 0.002 m` (`inv_xview.tolerance_for('NPM').vertex_m`, same comparison as `vertex_pairs`). `T` = fan triangles
(k-gon = k-2), as in #31. Scored part: the only object whose name ends with `_Ground` (amendment 1 of #31).
`V` (#32 near-vertex count) is recomputed next to it for parity only.

**Fixture (frozen, no replacement).** #31 dumps `C:/x/ev_t_193a0887/dumps-v002`, hashes in
`docs/research/autoresearch-ground-quality-harness/dumps.sha256` (A1 Vatutino v015 + A2–A8 Artem's delivered NTR NPM
Ground; F1–F5 SIL13 #1315 r1–r5, F3 = F5 bytes). NTR copies and hashes: `C:/x/ground-etalons/` (#31/#32 custody).
Holdout, declared now and **not** a calibration input: W1 Vatutino v014 NPM Blender readback
`C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz` SHA-256
`29393a0b5ed7ce39a2e5a8d8c7b0014885ecf4bfcde5a9ae07088bfc76aa6683`. Expected for W1: `E = 0`, because its
rejection (#370) is the non-manifold split class that the delivered A3–A6 also carry; W1 is reported, not used for
the verdict.

**Hypothesis H35 (this corpus only).** Confirmed iff all hold on one completed series:

1. Separation: `min Qe(F) > max Qe(A)` and `min Qe(F) >= 2 * max(1, max Qe(A))`.
2. Parity: per input `T` and `V` equal the #32 receipt (`research/autoresearch-standing-32@ebb32458`,
   `autoresearch-ground-near-vertices-r32.json`).
3. Repeat: three evaluations per input, identical `E`, `T` (median reported, spread 0).
4. Rigid motion (#31 `rigid`: rotate 30° about Z + shift (123.456, -78.9, 3.21) m): `E`, `T` exactly unchanged.
   Expected direction none.
5. Max-like split (representative perturbation of the #33 failure mode, every input): split every non-manifold
   vertex into one copy per edge-connected face fan. Bound: `E`, `T` exactly unchanged. `V` after the split is
   published descriptively (expected to rise on inputs with fans; this is the property that broke Qv).
6. Positive witness (injected, every accepted input; Vatutino A1 is the non-SIL13 witness): take interior vertices
   (not on an open edge) in index order, every k-th with `k = n_interior // 50`, first 50; for each picked `v`
   with a picked-free first neighbour `u` (first edge of its first face), move `v` to `u + 0.001 * (v-u)/|v-u|`.
   Expected direction up. Bound: `E_inj - E >= 25` and `T` unchanged.
7. Accepted control on which the rule fires: an accepted input with `E > 0`. If none, recorded **not measured**
   (collateral impact on accepted work unknown, not zero).

Refuted if 1 or 2 fails on a completed series, or 3–6 fail; inconclusive if the series does not complete.

**Then (only if confirmed).** Score the first published #1738 core export, SIL13 shared v003
`C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj` SHA-256
`8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450` (= Drive
`G:/Мой диск/AGR-evidence/1738-ground-shared-core/sil13_shared_v003/`), three evaluations. The #1738 r2/r3 packets
publish reports only (no meshes), so later core builds are **not measured**. No rebuild.

**Budget.** First pair A1 + F4 timed; cap 5 minutes wall for the whole series; if `first_pair * 7` exceeds the cap,
stop `inconclusive` and publish the replay command. Confirm-vs-new-candidate: one candidate, zero new candidates
in this card.

**Forbidden.** Replacing or dropping inputs after seeing scores; changing the 2 mm tolerance; editing delivered
packages, SIL13/#1738 evidence or other cards' files; building or repairing Ground; deselecting tests; any gate or
threshold in production code.

**Not measured (by design).** Native Max readback (no Max geometry dump exists for A1–A8; the split perturbation
models it), VPM (no rejected VPM Ground), skirt (#1738/#1787), visible deviation, triangle budget, overlapping
faces, independent rejected site outside SIL13 (W1 is a different defect class).

**Replay.** From the repo root (the worktree uv env lacks NumPy; the parent venv provides it):
`../../.venv/Scripts/python.exe docs/research/autoresearch-ground-short-edges-r35.py C:/x/ev_t_f4f34f04/NEW.json`.
Inputs are customer packages outside Git, so replay is limited to this PC.

## Round log

Contract `97298a70` (before any score), harness `af0f782f` (before the series; synthetic sanity only: a bowtie
gains 1 vertex on split, E unchanged). One series, no reruns before the receipt. Receipt
[`autoresearch-ground-short-edges-r35.json`](autoresearch-ground-short-edges-r35.json) SHA-256
`49b4c69fd78874c3bfa4430dc705b06a235e068322af695e64bf75778d57ae86` (byte-identical to scratch
`C:/x/ev_t_f4f34f04/r35.json`). A second process (`r35-replay.json`) gives an equal receipt apart from the two
timing fields. Budget: first pair 1.7 s, the full series took 11.6 s against a 300 s cap. NumPy 2.5.3. No DCC was run.

| id | input | E (≤2 mm edges) | T | Qe (median of 3, spread 0) | split: +vertices / V after | V (= #32) |
|---|---|---:|---:|---:|---:|---:|
| A1 | Vatutino v015 | 0 | 46 479 | 0.000 | +59 / 118 | 0 |
| A2 | Skolkovo | 0 | 5 733 | 0.000 | +0 / 0 | 0 |
| A3 | COD | 0 | 2 801 | 0.000 | +7 / 14 | 0 |
| A4 | Donskoy | 0 | 11 528 | 0.000 | +2 / 4 | 0 |
| A5 | Ostrov | 0 | 29 760 | 0.000 | +1 / 2 | 0 |
| A6 | Kasatkino | 0 | 59 290 | 0.000 | +1 / 2 | 0 |
| A7 | Volokolamskoe | 0 | 20 614 | 0.000 | +0 / 0 | 0 |
| A8 | Stolbovo | 0 | 10 930 | 0.000 | +0 / 0 | 0 |
| F1 | SIL13 r1 | 915 | 36 549 | 250.349 | +0 / 1 769 | 1 769 |
| F2 | SIL13 r2 | 914 | 37 386 | 244.477 | +0 / 1 767 | 1 767 |
| F3 | SIL13 r3 | 906 | 37 370 | 242.440 | +0 / 1 751 | 1 751 |
| F4 | SIL13 r4 | 807 | 37 370 | **215.949** | +0 / 1 576 | 1 576 |
| F5 | SIL13 r5 (= F3 bytes) | 906 | 37 370 | 242.440 | +0 / 1 751 | 1 751 |
| W1 | Vatutino v014 (holdout, not in verdict) | 0 | 46 343 | 0.000 | +59 / 118 (= #370 Max) | 0 |
| core | #1738 SIL13 shared v003 OBJ | 185 | 26 491 | 69.835 | not run | 290 |

| # | check | clean / injected / not measured | result |
|---|---|---|---|
| 1 | separation, ×2 margin | clean | pass: min F 215.949 > max A 0.000, ≥ 2 |
| 2 | T and V parity with #32 | clean | pass on all 13 |
| 3 | three repeats | clean | pass, spread 0; second process equal |
| 4 | rigid motion | clean | pass, E/T unchanged on 14 |
| 5 | Max-like non-manifold split | perturbation | pass, E/T unchanged on 14; V rises on A1, A3–A6, W1 |
| 6 | positive witness (50 short edges) | injected | pass: E +50 on all 8 accepted (A1 Vatutino = non-SIL13 witness) |
| 7 | accepted control on which the rule fires | - | **not measured**: E = 0 on all 8 accepted |

**H35: confirmed** on this corpus. Descriptive only (scratch probe, not in the receipt): on F1 all 1 769 near
vertices and on F4 1 574 of 1 576 are endpoints of ≤ 2 mm edges. On the core OBJ 279 of 290 are, and 17 of its
185 short edges have zero length. So on SIL13, Qe and Qv see the same slivers, and Qe drops the dependence on the
node state.

Not measured: native Max (no Max geometry dumps; the split model does not reproduce Max's 278–580 on A3–A6), VPM,
skirt, visible deviation, budget, overlapping faces, #1738 r2/r3 builds (reports only, no meshes), an independent
rejected site.
