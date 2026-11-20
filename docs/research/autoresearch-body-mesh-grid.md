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

**Replay.** From the worktree root (needs the `C:/x/...` and `G:/Мой диск/AGR-evidence/...` inputs of #13):
`PYTHONUTF8=1 ../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-grid-harness/grid.py <dir1> R1`,
the same with `<dir2> R2` (may run in parallel), then `grid.py --combine <dir1> <dir2> <grid.json>` applies the
frozen decision rule.

**Harness amendment (before any result was used).** The first single-process run (`C:/x/ar15/g1`) showed
~28 s per origin (3 repeats × 13 inputs), i.e. ≈ 64 min for R1 + R2 in series, beyond the 40 min stop rule.
It was stopped after 3 origins; its partial log already showed R1 below 0.5 at `o = (0,0,1)`, which triggers
R2 under the frozen rule. The harness was split into one process per variant (each re-dumps and re-confirms
R0 and the witness independently) plus a `--combine` step; metric, origins, repeats, R2 definition and
decision rule are unchanged.

## Result — OBSERVE, nothing kept

**Кратко.** Отрыв 0,611 из #14 — удачное положение сетки, а не свойство штрафа. Если сдвинуть сетку на 1–3 м,
минимальный отрыв падает до **−2,292**: тогда отклонённые углы КПП1 получают балл выше принятой части.
Отрыв не ниже 0,5 держится только при 15 из 64 сдвигов, медиана по сдвигам −0,175. Для сравнения, у
штатной оценки R0 отрыв 0,427, и он не зависит от сетки. Вариант R2 (максимум по восьми сеткам со сдвигом
на полклетки) уменьшил разброс с 3,32 до 1,20, но всё равно опускается до −0,506 (8 из 64). Оба варианта
отклонены. Ядро, построители и модели не менялись. Причина в том, что у **принятых** корпусов тоже есть
ячейки 4 м почти целиком из косых граней: у 63B v007 максимум по ячейкам 0,17–0,84, у остальной части
КПП1 0,47–0,98. Максимум по одной ячейке измеряет, где прошла сетка, а не дефект.

| Variant | worst min_margin (origin) | best | spread over 64 | origins ≥ 0.5 | robust |
|---|---:|---:|---:|---:|---|
| R0 (unchanged, origin-free) | 0.427 | 0.427 | 0.000 | — | below 0.5 (as #13) |
| R1 (#14, 4 m grid) | **−2.292** (2,1,0) | 1.028 | 3.320 | 15/64 | **no** |
| R2 (8 half-cell staggered grids) | **−0.506** (1,0,0) | 0.696 | 1.202 | 8/64 | **no** |

Per-pair minimum over the 64 origins (R1 / R2): 63B v007−v001 0.403 / 1.265; −v002 0.417 / 1.280;
−v003 0.408 / 1.303; −v004 0.401 / 1.295; −v005 1.223 / 1.579; **−v006 −1.102 / −0.506**; 63C v002−v001
2.171 / 3.194; **KPP1 rest−corners −2.292 / −0.264**; G22 k1 v003−v002 1.028 / 1.028 (no irregular faces;
origin-independent). The failing pairs are 63B v006 and KPP1, where the accepted side has irregular cells of its own.

- **Measured clean.** 11 sources dumped 3× each by the unchanged Blender dump (Blender via
  `dt_ai.core.blender_runner`), all three dumps identical; input SHA-256 equal to #13 `INPUTS` before and after.
  R0 reproduced #13's nine margins exactly and R1 at `o = 0` reproduced #14's nine margins exactly (min 0.611),
  in both processes. Every score was repeated 3× per input per origin. Every paired spread was 0.000 for
  R0, R1 and R2. Canonical report parity held for each R1/R2 report against R0: 13 inputs × 64 origins × 2
  variants, with score and the irregular-area penalty removed.
- **Injected (synthetic).** #14 witness clean/injected/reset passed at all 64 origins (each process). Synthetic
  geometry, not native acceptance.
- **Not measured.** Grid rotation, other cell sizes, held-out pairs, 63A, G22 k2/k3, rebuilds, packages, full suite.

Receipts (committed, measured on Windows, LF): `autoresearch-body-mesh-grid-harness/R1.json`
`3d14e3c32951fd12…`, `R2.json` `756b38c25bc3d4b0…`, combined `grid.json` `1eb4ad7cdb1eac39…`. Logs and
copies: `G:/Мой диск/AGR-evidence/ar15-body-mesh-grid/` (`SHA256SUMS.txt` sha256 `ec3c77adc651ad48…`).
Measured at harness commit `6e9d0bbd` on base `82875426`. Wall time: R1 35.3 min, R2 41.8 min, run in parallel.
The R2 process ran ~2 min past the 40 min stop rule because parallel runs slowed it; its result was complete
and was used.

**Would change (separate PR + review, not applied).** Do not adopt #14 R1 or any single-cell maximum.
A local defect signal has to be independent of where the grid falls and must not fire on the accepted bodies'
own oblique cells. Candidates for a future contract: (a) per-element or per-facade-panel ratio (object/element
ids from the dump, not world cells); (b) count of irregular faces whose neighbours are rectangular (isolated
defects), not irregular area per cell. Each one is first checked on this 64-origin bench (worst ≥ 0.5), or is
origin-free by construction.
