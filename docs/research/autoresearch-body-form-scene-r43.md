# Body form — scene-readback rubric vs planted form defects, standing #43 (contract, frozen before measuring)

**Русское резюме (контракт).** #41 показал: рендер-судьи надёжны на крупных дефектах, но рубрика Q4 (углы) у обоих
нестабильна. #43 проверяет сценовую рубрику — уже замороженный held-out детектор t_563a40f7 (`extract.py` +
`score_heldout.py`, допуски не меняются) — на тех же вариантах (A, R, P_fill) и на лестнице заложенных дефектов формы
(лишняя ниша глубиной 0.03–0.20 м, фаска угла 0.05–0.80 м). Число: сколько из 12 отрицательных вариантов детектор
ловит при 0 ложных провалов на принятых контролях. Кандидат (только OBSERVE, не внедряется): контурное сравнение
дополнительно в полосе окон (сечения 17.8 и 18.2). Тела не строю и не чиню; дефекты — оценочные контроли на копии A.

## Target and why

Focus of the card: a signal that a body has the RIGHT SHAPE. KPP1 failed with green mesh metrics on extra 110 mm
recesses and a wrong corner. #41 (`research/autoresearch-standing-41@77e7e368`) qualified VLM judges on large planted
defects but flagged Q4 (corners) as unstable for both judges and listed "scene (readback) rubrics" as not measured.
#40/#42 own coverage/inapplicability; #41 owns the judge rig. Not taken: Ground (#1738 relief fix first), build
(#1770/#1784/#1609), cold delivery (#1315), atlas (#1649), suite (#1615), KPP1 NW / Sokolniki (still no exact-hash
accepted/rejected *body* pair, #40 line 25-26).

## Hypothesis H43

The frozen scene detector separates the accepted body from planted form defects only above its wall-line search
window: a recess shallower than `wall_line_search_m` = 0.12 m inside the window band (z 17.3–19.05) is invisible,
because contour sections are at 16.85/19.8 (outside the band) and the band sections only look for wall gaps.
KPP1's 110 mm recesses fall in that blind spot. Expected baseline: recess 0.03/0.06/0.11 missed, 0.13/0.20 caught;
corner legs ≥ 0.10 caught (contour deviation ≈ leg/√2 > 0.05), 0.05 missed; R and P_fill caught.

## Metric (one number)

`M43 = detected negatives / 12` with the hard precondition `false fails on accepted controls = 0`.
Negatives (12): R (v001), P_fill, P_recess d ∈ {0.03, 0.06, 0.11, 0.13, 0.20} m, P_corner leg ∈ {0.05, 0.10, 0.20,
0.40, 0.80} m. Detected = any group-A or group-B `fail`, or `FP_extra > 0`. `not_measured` is never a detection and is
reported separately. Accepted controls (must have 0 fails): A (original bytes), A_rt (A through the same plant/export
script with no plant: round-trip control), C_none (t_563a40f7 control bytes, re-extracted).
Injected controls reported, not in M43: C_shift_opening, C_shift_wall (re-extracted from bytes); J1–J3 only exist
as frozen extracts → rescored and labelled `frozen_dump` (not stability evidence).

## Command

```
R43=C:/x/autoresearch-body-form-r43
blender -b --factory-startup --python $R43/plant43.py -- <worktree> <A.fbx> <variant> <param> <out.fbx>
blender -b --factory-startup --python C:/x/t_563a40f7/detector/extract.py -- <fbx> <out.extract.json> 16.85,17.8,18.2,19.8
python C:/x/t_563a40f7/detector/score_heldout.py C:/x/t_563a40f7/key/heldout-key-v001.json C:/x/t_563a40f7/key/SHA256SUMS.txt <extract> <out.json>
python $R43/run43.py   # drives all of the above, writes result43.json
```

`plant43.py` copies the plant code of `rig41.py` (P_fill / P_recess / P_corner, same frames and positions) with the
size as parameter and exports the full uncropped body; no render. Blender 5.1, offline.

## Candidate C1 (OBSERVE only)

`CONTOUR_Z = ["16.85", "17.8", "18.2", "19.8"]` — the existing two-sided contour Hausdorff (tolerance 0.05 m,
unchanged) also against the key sections in the window band (the key file already holds 17.8 / 18.2). Run as an
in-memory patched copy of `score_heldout.py` in `$R43`; the frozen detector is not edited.
Keep threshold (would be proposed in a PR, not applied): C1 detects ≥ 2 more negatives than baseline, 0 fails on
accepted controls, and every pre-existing item keeps its status on every input (invariance: per-input changed item
counts; inputs where the new item is not computed are `not_exercised`).
Accepted control on which C1 fires (is exercised): A / A_rt / C_none — band sections cut through 6 openings and
reveals, so the new items run on real jamb geometry and must pass.
Positive trigger witness: P_recess 0.11 (KPP1-like depth). Perturbations and expected direction: recess depth ↑ and
corner leg ↑ → detection monotone (once detected stays detected); C_shift_opening / C_shift_wall → stay failed.

## Determinism ("median of 3")

The detector is deterministic: A is extracted 3 times; the 3 extract files must be byte-identical (sha256), else the
round is `inconclusive`. Paired spread reported = number of distinct extract hashes (expected 1).

## Budget and stop rule

One baseline round + one C1 round on the same extracts; ≤ 18 Blender runs; wall cap 90 min. A budget stop is
`inconclusive`. No new candidates after C1 in this card (confirm vs new candidate budget: 1 confirm, 0 new).

## Forbidden

Editing the frozen detector, key, controls or tolerances; editing delivered/accepted bytes (A is read, copies only);
building or repairing bodies; dropping variants after seeing results; 3ds Max; touching other cards' files.

## Replay

Inputs pinned by SHA-256 in `result43.json` (A `5b1e8d76…f200`, R `8e97a80a…`, C_* bytes, key SHA256SUMS verified by
the scorer itself). Evidence `C:/x/autoresearch-body-form-r43/` + `SHA256SUMS.txt`, copied to
`G:/Мой диск/AGR-evidence/standing43-body-form-scene/`. Replay limited to a PC with `C:/x/t_563a40f7` and
`C:/x/review-k2` (same as #40–#42).
