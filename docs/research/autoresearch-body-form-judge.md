# Body form — VLM judge qualification, standing #41, frozen contract

**Русское резюме.** Продолжение #40 (`research/autoresearch-standing-40@aba60c66`, тот же фрагмент G22 к.2 SE и те же
FBX). #40 не смог проверить судей: кадры были в текстурном режиме, захватывали соседние этажи, а камеры не смотрели
по нормали фасада (здание повёрнуто на 39,186°). Здесь меряется одно число — доля ложных «Да» (Yes-bias) у двух
независимых судей (свежий Claude CLI и свежий Codex exec) на заложенных видимых дефектах, на нейтральных кадрах,
выровненных по фасадам источника. Только OBSERVE: тела не строятся и не чинятся, заложенные дефекты — контрольные
копии оценщика в памяти Blender, не модели.

## Base, inputs, scope

Base `aba60c66` (= origin/main `8aa00f70` + #40 receipt). Inputs (hash-checked before and after):
A = v002r1 `5b1e8d76…f200` (Artem accepted stage 1, 2026-11-18), R = v001 `8e97a80a…b519` (Artem objected: no apertures,
AC boxes), both copied from `C:/x/autoresearch-body-form-r40/evidence/{A,R}.fbx`; key `C:/x/t_563a40f7/key/heldout-key-v001.json`
(manifest checked with `sha256sum -c`). The key supplies only the facade frame (ring vertices 13–25), the six opening
positions and the crop; rubric text stays in local evidence, the branch carries counts, hashes and verdicts only.
Out of scope: Ground #1738, body construction #1770/#1784, KPP1 production, cold delivery #1315, atlas #1649,
suite #1615, 3ds Max. KPP1 NW / Sokolniki have no exact labelled body pair (#40) — not measured here.

## Rig (frozen before the first judge call)

Blender 5.1, `--factory-startup --disable-autoexec --threads 1`; load with `tools/blender/verifier_views.py::_load`.
Crop: bisect to source box x 536.9–552.5, y 1036.8–1060.5, z 16.8–19.6 (one typical floor, sill 17.3 / head 19.05;
no adjacent floor windows). Workbench, `SINGLE` colour (0.8 grey), `STUDIO` light, cavity + outline on,
background white, 1200×700 px per panel. Orthographic cameras registered to the source facade frame
u = ring 16→17 direction (39.186°): V1 from the −n side (segments 16–21), V2 from the +n side (segments 22–25),
V3 from the +u side (end wall 21–22), V4 plan from above. One composite PNG (2×2, labelled V1–V4) per variant.
Rig preflight is allowed on A only (no judge call); the wrapper and composite hashes are frozen before judging and
never retuned after the first judge answer. A preflight failure gets at most 3 different repairs, each logged.

## Variants and ground truth (fixed before judging)

| ID | What | Salient truth |
|---|---|---|
| A | accepted v002r1 | all rubrics Yes |
| R | rejected v001 | Q1 No, Q2 No, Q3 Yes; Q4/Q5 not labelled |
| P_fill | A + box filling opening 6361420 (seg 22–23) flush with the facade | Q2 No |
| P_recess | A + extra 1.80×1.75 m recess (sill/head as windows), depth 0.13, on seg 16–17 at s 0.6–2.4 | Q1 No |
| P_corner | A + 0.8 m chamfer at convex corner ring 21, full crop height | Q4 No |

Rubrics (render evidence, BlenderWorld-style binary, weight in brackets; spec source = key opening list / ring):
Q1 [3] V1 shows exactly 4 window recesses at one floor; Q2 [3] V2 shows exactly 2; Q3 [3] V3 (end wall) shows no
recess; Q4 [3] every building corner is a sharp right-angle edge, no chamfer/bevel; Q5 [2] all recesses are
rectangles sharing one sill and one head height. Answers Yes / No / Unsure; Unsure = not_measured. The 0.10 m controls
`C_shift_opening` / `C_shift_wall` are not violated by these rubrics: **not exercised**, not rendered as negatives.

## Primary number, gate, stop rule

Per judge J ∈ {claude, codex}: `yes_bias_J = false Yes / labelled negative cells` (5 cells: P_fill Q2, P_recess Q1,
P_corner Q4, R Q1, R Q2), per cell majority of 3 independent fresh calls (median of 3); also true-Yes rate on the
labelled positive cells and per-call flip rate. Qualifies iff yes_bias = 0/5, true-Yes ≥ 80 %, Unsure ≤ 20 % of labelled
cells. Calibration: weighted rubric score S(R) < S(A) for each judge. n = 5 negatives is a small sample: a pass is
"qualified on this rig", not a precision claim.

Second method (only for qualified judges; otherwise reported but marked unqualified): pairwise A vs {R, P_fill,
P_recess, P_corner}, each pair in both orders with opaque labels X/Y, same composites, same short spec text, answer
X / Y / Unsure, never "matches the drawing". Keep order-consistent verdicts; report coverage, agreement with
Artem (A vs R only — the only real verdict), agreement with construction truth (planted pairs, separate), and
Cohen's kappa claude↔codex on common retained pairs (undefined on zero pairs/zero denominator). Proxy: historical
mesh score from #40 for A/R only (83.693 / 90.830, reversed); planted variants: proxy not measured.

H41 confirmed iff both judges qualify and both rank A over R (rubric and pairwise). Refuted iff a judge gives any
false Yes on a salient negative with ≥ 2/3 calls. Otherwise inconclusive. Budget: freeze after one timed call;
≤ 70 judge calls total, ≤ 75 min wall; a budget stop is inconclusive. No KEEP of code in this round (OBSERVE);
candidate budget 0.

## Forbidden

Retuning rig/prompt/rubric after the first judge answer; dropping Unsure; editing FBX inputs, deliveries or other
cards' files; showing judges variant names, file paths, this contract or the truth table; reusing a session between
calls; using 3ds Max; deselecting tests or weakening validators.

## Replay

Evidence root `C:/x/autoresearch-body-form-r41/` (`SHA256SUMS.txt`, local-PC; replay limited).
`"$B" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 --python "$E/rig41.py" -- "$ROOT" "$E/<V>.fbx" <variant> "$E/views/<variant>"`;
judges by `python "$E/judge41.py" rubric|pair` (prompts and raw answers stored per call).
