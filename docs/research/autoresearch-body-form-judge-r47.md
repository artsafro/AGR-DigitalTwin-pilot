# Body form — VLM judge specificity on form-equivalent copies, standing #47, frozen contract

**Русское резюме.** #41/#45 показали чувствительность рендер-судей: ниши от 0,03 м они видят, в парах A побеждает
7/7. Не измерено обратное — **специфичность**: не «видит» ли судья дефект там, где форма та же, а отличается только
сетка (триангуляция, подразбиение) или мелкий шум вершин в допуске (5 и 20 мм < 0,05 м контурного допуска #43).
Если судья в паре стабильно предпочитает A и копии той же формы, то «A побеждает» в #45 — не сигнал формы, а сигнал
«нетронутого рендера». Одно число: **FD47 = число ложных различений** на форм-эквивалентных копиях. Сравнение с
mesh-proxy (`tools/qa/mesh_quality_score.py`), который на сетке обязан меняться. Только OBSERVE: тела не строятся и
не чинятся, копии существуют только в памяти Blender и как диагностические OBJ вне репо.

## Base, inputs, scope

Base `49997a1d` (origin/main). Continues the judge bench #41 (`research/autoresearch-standing-41@77e7e368`) and #45
(`research/autoresearch-standing-45@116329e4`); same rig, prompts, SPEC, PAIR_SPEC, models and flags (verbatim from
`judge41.py`). A = G22 k2 v002r1 `5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200` (Artem accepted
stage 1, 2026-11-18), copied from `C:/x/autoresearch-body-form-r45/inputs/A.fbx`; key
`C:/x/t_563a40f7/key/heldout-key-v001.json` (evaluator-only, not copied to Git). Hashes checked before and after
(`FROZEN-before-judge.sha256`). Not taken (owned/blocked): contour rule C1 #43, wall ownership #44/#46, Ground until the
#1738 relief fix, construction #1770/#1784/#1609, cold delivery #1315, atlas #1649, suite #1615, KPP1 NW / Sokolniki
(no exact hash-bound accepted/rejected body pair, #40). Blender 5.1.2 headless only; no 3ds Max.

## Variants and ground truth (fixed before judging)

All variants are built in memory from A **before** the crop, by `rig47.py` = `rig45.py` + one variant block.

| ID | Mesh-only change | Max vertex displacement | Truth |
|---|---|---|---|
| A | none (control; composite must be byte-identical to #45 `comp/A.png`) | 0 | Q1,Q2,Q3,Q5 Yes |
| N_tri | triangulate all faces (`bmesh.ops.triangulate`, BEAUTY/BEAUTY) | 0 | same form as A |
| N_sub | one grid subdivision of every edge (`subdivide_edges`, cuts=1, grid fill, no smoothing) | 0 | same form as A |
| N_jit_0.005 | seeded (47) uniform jitter of every vertex, each axis in [-0.005, 0.005] m | 0.0087 m | same form as A (≤ 0.05 m tolerance) |
| N_jit_0.020 | same, [-0.020, 0.020] m (stress) | 0.035 m | same form as A (≤ 0.05 m tolerance) |
| AA | A shown against itself (pair only; forced-choice bias control) | 0 | Unsure / order-inconsistent |

Q4 (corners) is reported as noise only: #45 showed it unstable on A for both judges. A variant whose composite is
pixel-identical to A (max abs diff 0) is **not_exercised** for the judges (render invariant by construction) and is not
sent to them; its proxy is still measured.

## Primary number, hypothesis, gates

Per judge J ∈ {claude (CLI default), codex exec `gpt-6.1-sol`} and exercised variant N:
- rubric false flip = majority (3 fresh calls) of Q1/Q2/Q3/Q5 on N differs from the majority on A in the same session
  (Unsure majority = not_measured, never counted as a flip or a pass);
- pairwise false preference = both orders (A,N) and (N,A) name the same side (order-consistent preference for either
  side). Unsure in either order or order-inconsistent = correct (no discrimination).

`FD47 = Σ_J Σ_N (rubric false flips + pairwise false preferences)`, lower is better, target 0.

- **H47 confirmed**: FD47 = 0 over exercised cells, ≥ 2 variants exercised, AA control shows no order-consistent pick.
- **H47 refuted**: FD47 ≥ 1 on an exercised N_tri/N_sub/N_jit_0.005 cell (the judge discriminates forms that are equal
  within tolerance). N_jit_0.020 alone is reported separately as a stress result.
- **inconclusive**: < 2 variants exercised, AA control picks a side order-consistently for both judges (the forced-choice
  bias swamps the test), > 20% failed calls after repairs, or input/parity drift.

Proxy comparison: `uv run python tools/qa/mesh_quality_score.py <variant>.obj --out <new>.json` on the uncropped
variant OBJ exported by the rig (A exported through the same path for parity). Expected direction: proxy changes on
N_tri/N_sub (mesh differs), judges do not (form same). Recorded, not scored.

## Parity, budget, stop rule

Parity before any judge call: `rig47.py A` composite byte-identical (else pixel-identical) to
`C:/x/autoresearch-body-form-r45/comp/A.png`; up to 3 different repairs, else inconclusive (rig not reproduced).
Budget frozen from #41 timing (claude 11.7 s, codex 13.4 s per call): rubric 2 judges × (A + ≤4 N) × 3 = ≤30 calls,
pairs 2 judges × (≤4 N + AA) × 2 orders = ≤20 calls; cap 60 calls / 45 min wall, 4 workers. One timed call per judge
first; if 1.5 × measured call × remaining calls / 4 exceeds the remaining cap, stop inconclusive with the partial
receipt and the exact resume command (calls are cached per id). Failed call: up to 3 different repairs, logged; else
not_measured. No confirmation re-run budget beyond this series (rescoring cached calls is not new evidence).

Forbidden: changing prompts/rubrics/models/seeds after the first call, dropping Unsure, deleting failed calls, editing
bodies/deliveries/other cards' files, 3ds Max, weakening validators, deselecting tests. Evidence (PNGs, calls) goes to
`G:/Мой диск/AGR-evidence/standing47-body-form-specificity/` + `SHA256SUMS.txt`; Git keeps text, hashes and paths only.
Replay limited to this PC (private key + A copy).
