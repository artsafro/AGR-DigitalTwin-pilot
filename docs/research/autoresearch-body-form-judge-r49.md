# Body form — VLM judge equivalence question, standing #49, frozen contract

**Русское резюме.** #47 показал: парный вопрос «какой рендер лучше отвечает форме» ранжирует «ближе к идеалу», а не
«в допуске / вне допуска» — на копии той же формы с шумом вершин до 33 мм (внутри допуска 0,05 м) оба судьи в обоих
порядках выбрали A. Значит «A побеждает» в #41/#45 не годится как гейт. Здесь проверяется вопрос **эквивалентности**:
«одинакова ли форма X и Y, если не считать сетку, тени и разницу меньше 5 см?» — на тех же кадрах без перерендера
(N_* из #47, лестница P_*/W_* из #45, отклонённый Артёмом R из #41). Одно число: **E49 = число ошибочных
порядок-согласованных вердиктов** (ложное «разные» на копиях той же формы + ложное «одинаковые» на дефектах вне
допуска и на R). Только OBSERVE: тела не строятся и не чинятся, кадры — копии готовых композитов, код в продукт не
вносится.

## Base, inputs, scope

Base `49997a1d` (origin/main). Continues the judge bench #41 (`research/autoresearch-standing-41`), #45
(`research/autoresearch-standing-45@116329e4`) and #47 (`research/autoresearch-standing-47`). Same judges, model ids,
call flags, isolation (fresh process, fresh session, opaque call dir holding only `X.png`/`Y.png`) and SPEC text as
`judge47.py`; ONLY the pair question changes (below). No re-render: the 16 composites are byte copies of the frozen
#41/#45/#47 composites (`FROZEN-before-judge.sha256`, 16 entries; `comp/A.png` sha256 `8f46976ab0c749f0…`, identical
in #41, #45 and #47). A = G22 k2 v002r1 (Artem accepted stage 1, 2026-11-18); R = v001 (Artem rejected, #41).

Not taken (owned/blocked): contour rule C1 #43, wall ownership #44/#46, slice conflict #48, Ground until the #1738
relief fix (#1816), construction #1770/#1784/#1609/#1818, cold delivery #1315, atlas #1649, suite #1615. KPP1 NW /
Sokolniki: still no exact accepted/rejected **body** pair (t_aadee92c handed in no candidate mesh) — not measured.
No Blender, no 3ds Max in this round.

## Question (frozen; SPEC verbatim from #41)

`{SPEC}\nTwo renders of a building fragment, made with the same views: render X = file X.png, render Y = file Y.png
(both in the current directory). Ignore differences that come only from mesh triangulation, shading or rendering noise,
and any geometric difference smaller than about 5 cm. Do X and Y show the same building form (same walls, openings,
recesses and corners)? Answer Same, Different or Unsure. Reply with one line of JSON only, e.g. {"form":"Same"}.`

No required-form text (PAIR_SPEC) is shown: the question is comparison only, never «matches the drawing».

## Cells and truth (fixed before judging; tolerance 0.05 m = #43 contour tolerance)

Every cell is A vs variant, shown in both orders (A,V) and (V,A), one fresh call per order per judge.

| Group | Variants | Truth | Source of truth |
|---|---|---|---|
| core SAME | AA (A vs A), N_tri, N_sub, N_jit_0.005 (max disp 8.2 mm) | Same | construction (#47) |
| stress SAME | N_jit_0.020 (max disp 32.9 mm < 0.05 m) | Same | #43 tolerance, synthetic |
| core DIFF | R | Different | **Artem's verdict** (rejected vs accepted) |
| core DIFF | W_recess (0.13), W_corner (0.80), P_recess_0.20/0.11/0.06, P_corner_0.40/0.20/0.10 | Different | construction (#45; C1 detects all) |
| boundary | P_recess_0.03, P_corner_0.05 (max deviation 0.03 / 0.035 m, inside tolerance) | Same by tolerance | reported only, not in E49 |

Cell verdict per judge: both orders give the same label Same or Different → that label (order-consistent);
otherwise (Unsure in either order, or the orders disagree) → **no decision** (abstention, counted separately, never
an error and never a pass). Unparsed answers after one same-prompt retry → not_measured.

## Primary number, hypothesis, gates

`E49 = Σ_judge [false Different on core+stress SAME cells + false Same on core DIFF cells]` (2 judges × 14 cells),
lower is better, target 0. Also reported per judge: decided share, detection = correct Different / 9 DIFF cells.

H49 (the equivalence question separates in-tolerance mesh change from out-of-tolerance form change):
- **confirmed** iff E49 = 0 AND each judge decides R = Different (calibration vs Artem) AND each judge's detection
  ≥ 6/9 AND AA is decided Same by each judge;
- **refuted** iff any judge gives order-consistent Different on AA, N_tri, N_sub or N_jit_0.005, OR order-consistent
  Same on R;
- **inconclusive** otherwise (e.g. only stress error, detection < 6/9, > 20% calls failed, input drift).

Comparison (recorded, not scored): the same cells under the #45/#47/#41 «better» question, mapping order-consistent
pick of A → Different, anything else → no decision; judge↔judge raw agreement and Cohen's κ on cells both judges
decided (undefined if a single label).

## Budget, stop rule, forbidden

Budget frozen from the #41/#47 per-call timing (11.7–32.2 s): 16 cells × 2 orders × 2 judges = 64 calls, plus ≤ 8
same-prompt retries for unparsed answers; cap 72 calls / 45 min wall, 4 workers. One timed call per judge first; if
1.5 × measured call × remaining calls / 4 exceeds the remaining cap, stop inconclusive with the partial receipt and the
resume command (calls cached per id). Confirm-vs-new-candidate budget: 0 code candidates (OBSERVE). No confirmation
re-run (rescoring cached calls is not new evidence).

Forbidden: changing the question, cells, truth, models or seeds after the first call; dropping Unsure; deleting failed
calls; showing judges variant names, sizes, paths, this contract or the truth table; re-rendering or editing
composites, bodies, deliveries or other cards' evidence (#41/#45/#47 read-only, copied); 3ds Max; weakening validators;
deselecting tests.

## Replay

Evidence root `C:/x/autoresearch-body-form-r49/` mirrored to `G:/Мой диск/AGR-evidence/standing49-body-form-equivalence/`
+ `SHA256SUMS.txt`. Scripts in `autoresearch-body-form-judge-r49/`. Replay (this PC; needs claude/codex CLIs and the
#41/#45/#47 composites): copy the scripts into `E`, copy the 16 composites as listed in `FROZEN-before-judge.sha256`,
then `sha256sum -c FROZEN-before-judge.sha256 && python judge49.py one && python judge49.py pair && python
aggregate49.py`. Judge answers are fresh samples. Replay limited to this PC.
