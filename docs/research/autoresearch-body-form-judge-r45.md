# Body form — VLM judge small-defect threshold, standing #45, frozen contract

**Русское резюме.** Продолжение стенда судей #41 (`research/autoresearch-standing-41@77e7e368`) и сценовой лестницы
#43 (`research/autoresearch-standing-43@0e099012`). #41 показал: на КРУПНЫХ дефектах (нет проёмов, ниша 0,13 м,
фаска 0,8 м) оба судьи дают 0 ложных «Да». #43 показал: сценовой readback-детектор C1 ловит нишу от 0,06 м и фаску от
0,10 м. Здесь меряется одно число — **порог обнаружения рендер-судьи**: наименьший размер заложенного дефекта, на
котором судья (большинство из 3 свежих вызовов) отвечает верным «No», и доля ложных «Да» на лестнице. Сравнение с
C1 по тем же размерам. Только OBSERVE: тела не строятся и не чинятся, дефекты — контрольные копии в памяти Blender.

## Base, inputs, scope

Base `49997a1d` (origin/main). Inputs (hash-checked before and after with `sha256sum -c FROZEN-before-judge.sha256`):
A = v002r1 `5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200` (Artem accepted stage 1, 2026-11-18),
copied from `C:/x/autoresearch-body-form-r41/inputs/A.fbx`; key `C:/x/t_563a40f7/key/heldout-key-v001.json`.
Rig = `rig41.py` of #41 with ONE change: the recess depth / chamfer leg is an argv parameter (geometry identical to
`plant43.py` of #43). Out of scope: Ground #1738, construction #1770/#1784/#1609, KPP1 production, cold delivery
#1315, atlas #1649, suite #1615, 3ds Max, KPP1 NW / Sokolniki (no exact labelled body pair, #40).

## Parity proof (before any judge call)

`rig45.py` on A, `P_recess 0.13` and `P_corner 0.80` must reproduce the #41 panels: composites byte-identical to
`C:/x/autoresearch-body-form-r41/comp/{A,P_recess,P_corner}.png`, else pixel-identical (max abs diff 0) after decode.
If not identical, at most 3 different repairs (logged); otherwise the round is inconclusive (rig not reproduced).

## Variants and ground truth (fixed before judging)

| ID | Defect | Labelled cell | C1 (#43) |
|---|---|---|---|
| A | accepted v002r1 (control) | Q1..Q5 Yes | not detected (correct) |
| W_recess = P_recess_0.13 | trigger witness (#41 size) | Q1 No | detected |
| W_corner = P_corner_0.80 | trigger witness (#41 size) | Q4 No | detected |
| P_recess_{0.20,0.11,0.06,0.03} | extra 1.80×1.75 m recess on seg 16–17, depth d | Q1 No | 0.20/0.11/0.06 detected, 0.03 missed |
| P_corner_{0.40,0.20,0.10,0.05} | chamfer at convex corner ring 21, leg l | Q4 No | 0.40/0.20/0.10 detected, 0.05 missed (in tolerance) |

Rubrics, prompts, SPEC, PAIR_SPEC, model ids and call flags: verbatim from `judge41.py` (Q1..Q5, weights 3/3/3/3/2).
Unlabelled cells are reported as noise, not scored. Unsure = not_measured (never dropped, never counted as No).

## Primary number, gate, stop rule

Per judge J ∈ {claude (CLI default), codex exec `gpt-6.1-sol`} and family F ∈ {recess→Q1, corner→Q4}:
- cell verdict = majority of 3 fresh independent calls (no majority / Unsure majority = not_measured);
- **T_J,F = smallest ladder size such that it and every larger size are a correct No** (∞ if the largest ladder size
  is not No); `yes_bias_J = false Yes / 8 ladder cells`.
- Family qualification: A's cell for F is Yes AND the witness cell is No; otherwise T_J,F is reported **not measured**
  (Codex Q4 was a known A miss in #41 — kept, not retuned).
- Calibration: weighted score S(variant) < S(A) for every ladder variant (per judge), reported.

H45 (render judges are less sensitive than scene readback C1 on small form defects):
- **confirmed** iff for every qualified (J, F) T_J,F > T_C1,F (recess 0.06, corner 0.10), and at least one qualified
  (J, F) exists for each judge;
- **refuted** iff for every qualified (J, F) T_J,F ≤ T_C1,F;
- **inconclusive** otherwise (mixed, no qualified family for a judge, parity failure, budget stop).

Secondary (second method): pairwise A vs each of the 8 ladder variants, both orders, opaque X/Y, verbatim
`pair_prompt`; keep order-consistent verdicts; report retention, accuracy vs construction truth, claude↔codex raw
agreement and Cohen's kappa on common retained pairs (undefined if single label / zero denominator). Artem's real
verdict covers only A vs R (#41); planted pairs are construction truth, reported separately. Geometry-validity proxy
(mesh score) for planted variants: **not measured**.

Budget (frozen before measuring; #41 timed pair 11.7 s / 13.4 s): 66 rubric (11 variants × 3 × 2 judges) + 32 pair
calls = 98; cap 110 calls and 60 min wall; 4 workers. Failed invocations are kept and retried once with the SAME
prompt; a budget stop is inconclusive. Confirm-vs-new-candidate budget: 0 code candidates (OBSERVE, nothing kept).

## Forbidden

Retuning rig/prompt/rubric after the first judge answer; dropping Unsure; editing FBX inputs, deliveries or other
cards' files (#41/#43 evidence is read-only, copied); showing judges variant names, sizes, paths, this contract or
the truth table; reusing a session between calls; 3ds Max; deselecting tests or weakening validators.

## Replay

Evidence root `C:/x/autoresearch-body-form-r45/` (`SHA256SUMS.txt`), mirrored to
`G:/Мой диск/AGR-evidence/standing45-body-form-judge-small/`. Render:
`"$B" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 --python rig45.py -- "$ROOT" inputs/A.fbx <variant> <param> views/<id>`,
`python compose41.py views/<id> comp/<id>.png`; judges `python judge45.py rubric|pair` (cached by call id; delete
`calls/` to re-judge); `python aggregate45.py`. Replay limited to this PC (claude/codex CLIs, Blender 5.1, key path).
