# Body mesh quality — standing #15: grid-origin robustness of the local penalty (OBSERVE)

**Кратко.** #14 показал, что локальный штраф R1 (сетка 4 м) отделяет отклонённые бадики от принятых с
отрывом 0,611 при пороге 0,5. Но сетка привязана к началу координат мира: сдвиг сетки может поменять,
в какую ячейку попадает дефект. Здесь проверяем, держится ли отрыв при любом сдвиге сетки. Модели,
построители и штатная оценка не меняются.

## Frozen contract (written before any measurement)

**Continues** #13 (merged #1724, `82875426d52dadd63b59814d97e46d44570806e2`) and #14 (branch
`research/autoresearch-standing-14`, head `5a0587665c5f89d27301d36615ada012488d8c25`, R1 definition and
witness). Its next target is "verify whether the fixed-grid ranking survives a translated grid". Production
sources are byte-identical at both bases (git blob ids: `tools/qa/mesh_quality_core.py` `7f27daca`,
`tools/qa/mesh_quality_score.py` `2946e383`, `tools/blender/mesh_quality_dump.py` `7c0b609b`).

**Fixture.** The 13 hash-pinned inputs and 9 same-building pairs of #13 `calibrate.py` at `82875426`
(63B stage-1 v001–v007, 63C v001/v002, KPP1 quad-v003 rest/corners by the frozen #1616 boxes, G22 k1
v002/v003 recorded dumps). 11 distinct source files (KPP1 is one `.blend` scored twice with zones).
No other inputs; 63A and G22 k2/k3 have no matched rejections — not measured.

**One metric.** `worst_min_margin(R)` = the minimum, over all 64 grid origins
`o ∈ {0,1,2,3} m × {0,1,2,3} m × {0,1,2,3} m`, of `min_margin` (the smallest of the 9 accepted − rejected
median-of-3 scores, points). The R1 cell key becomes `floor((c − o) / 4 m)`; everything else is #14 R1.
`o = (0,0,0)` is #14 R1 exactly. Also reported: per-pair min/max over the 64 origins, and the spread
`max − min` of `min_margin` across origins.

**Measurement method.** Each native source is dumped by the unchanged `tools/blender/mesh_quality_dump.py`
via `dt_ai.core.blender_runner` **3 times**; the three dumps must be byte-identical (else the input is
`noisy` and its pairs are not measured). G22 inputs are recorded JSON dumps, read 3 times. Input SHA-256 is
checked against #13 `INPUTS` before and after. Scoring is in-process on the identical dump, 3 times per
variant/origin, through the CLI's own `load_core().score` (R0) or the #14 R1 splice of the pinned core text
with an origin parameter (R1/R2); median of 3, paired spread = max − min of the 3 aligned differences.

**Confirm budget (before any candidate).** One R0 series and R1 at `o = 0`: R0 margins must equal #13
`r0.json` pairs and R1 at `o = 0` must equal #14 `comparison.json` `r1` margins exactly (to 0.001), else stop
— evidence invalid. Witness: #14 `witness.py` clean/injected/reset must pass for R1 at every tested origin
with the synthetic geometry inside one cell, and canonical (score and irregular penalty removed) report
parity R0 vs every R1/R2 variant on all 13 inputs.

**Keep threshold / decision.** R1 is "origin-robust on the fixture" iff `worst_min_margin(R1) ≥ 0.500`.
If and only if it is not, ONE new candidate R2 is measured (no follow-up candidate):
R2 = origin-free-ish multi-grid — the local ratio is the max over the 8 half-cell staggered grids
`o + {0,2 m}³`; same area floor 4 m², same `(global + max(global, local)) / 2` penalty. R2 is reported
robust iff `worst_min_margin(R2) ≥ 0.500` and its 64-origin spread is smaller than R1's. Either way the
outcome is a recommendation for a separate PR + review on `mesh_quality_core.py`; nothing is applied.

**Stop rule.** After R1's 64 origins (+ R2 if triggered), or 40 min of measurement wall time, or any invalid
evidence (hash drift, nondeterministic dump, parity break, confirm mismatch).

**Forbidden.** Changing weights, the 0.5 margin, the 4 m cell, the 4 m² floor, angular predicate or zones;
choosing the origin per input or per pair; editing inputs, delivered packages, production sources, tests,
or other cards' files (#1722/#1726 stage 2, #1649, #1609, #14's branch); deselecting tests; adopting on
these in-sample labels.

**Not measured (declared up front).** Grid rotation; cell sizes other than 4 m; held-out accept/reject
pairs; 63A, G22 k2/k3; any geometry rebuild or package check; full suite.

**Replay.** `PYTHONUTF8=1 ../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-grid-harness/grid.py <new dir>`
(from the worktree root of this branch; needs `C:/x/...` and `G:/Мой диск/AGR-evidence/...` inputs of #13).
