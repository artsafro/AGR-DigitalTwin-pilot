# Geometry-based PDF dimensions: KPP1 L03 (#1335)

## Кратко для Артёма

**Прироста подтверждённых размеров нет: L03 7/82 → 7/82 (8.54%), precision 1.0.**
Новый geometry-first прототип действительно выполнен на замороженном корпусе
#1321: линия + засечки + обе выносные, затем ориентация текста, продолжение
линии для вынесенной подписи, согласованность значения с масштабом и ближайший
однозначный кандидат. На L03 найдены 45 бумажных кандидатов; 44 совпадают с
native labels и точными линиями/концами oracle, но это **не новые semantic
bindings**. Ни одна из 13 оставшихся displaced labels не восстановлена.
59 размеров с неизвестной идентичностью концов не превращены в «найденные».

Масштаб L03 поддержан пятью независимыми размерами, не взят из штампа или
oracle. Это отдельный исследовательский paper-scale, **не production
calibration**. KNS: 10/12 → 10/12, precision 1.0. HOLD-OUT KNS-floor: 0/6 → 0/6,
precision=null, отдельный zero-prediction PASS [D277]. Общий guard=true,
`passed=false`: никакой приёмки модели или чертежа не заявлено.

Вызван существующий `dt_ai.album.compare` с сохранёнными наблюдениями двух
моделей KPP1 из #1304. Для 76 неидентифицированных PDF labels получены
152 строки `needs manual check`, 0 match / 0 mismatch. Наблюдения #1304 относятся
к южному фасаду, а не к плану L03: подтверждённого соответствия plan endpoints
нет. Позиции оставлены null, значение размера **не использовалось для поиска
похожего размера в модели**. Это честная граница cross-check, не геометрическое
измерение всех 76 пар в FBX. Прототип не переносится в production binder.

## Frozen contract and baseline

- Base: merged #1332, `8eb39d48`; original protocol, corpus and comparator from
  [#1321](autoresearch-pdf-dimensions.md) are unchanged.
- Corpus canonical SHA256:
  `351cbe99af8fb29b838d969baaa0c18bca49eb341e9ddcfe0b08d70690918b70`.
- Source native value strictly <0.5 mm; both endpoints and dimension-line position
  strictly <0.5 pt; one-to-one native handles. Only axis_pair/level_pair semantic
  predictions earn credit. All positive predictions count against precision.
- No oracle registration, native DXF value or model value enters reconstruction.
  Native truth is used only afterwards for evaluation. HOLD-OUT is reported,
  never used to choose a parameter or rule.
- The historical issue's 36 displaced / 36 endpoint misses describe the original
  pre-R1 baseline. A fresh replay of merged #1332 is **13 / 59**, not the older
  note's restored-R1 15 / 57. The note is not rewritten to hide that distinction.

## Method and boundaries

Research entry:
`uv run python -m tools.research.pdf_album.dimension_geometry`.
It emits JSON to stdout only; it has no output/report/temp-path option and never
opens, deletes or replaces an input. Shell redirection is the caller's operation,
not a protected publication API; do not redirect onto any input.

1. Reuse `_chains` only for vector line coverage and slash-tick intersections,
   including existing source-run-identified inline text gaps. Require a real
   perpendicular extension crossing each tick (<0.5 pt, length >2 pt); retain
   extension path indices. Arrowheads/non-cardinal chains are unsupported and
   stay unbound, not extrapolated.
2. Per viewport, use existing named axis/level dimensions as scale evidence.
   A forest over endpoint identities rejects repeated pairs and dependent sums
   as additional independent evidence. Require >=3 forest edges. Fit the median
   written-mm/paper-pt ratio, then require **every** seed residual strictly below
   max(10 mm, 0.5% of written value). Conflicting evidence refuses scale.
   This is paper-scale consistency, not independent metrological calibration.
3. Match parallel positive integer labels by value consistency and geometric
   distance. Outside the tick interval, require an actual continuous baseline
   stroke reaching towards the label (a continuation leader), not just proximity.
   Search perpendicular distance <4 font sizes; refuse distance ties within
   0.5 pt and multiple labels claiming the same span. Every numeric token has a
   disposition; nonnumeric runs have an explicit drop reason.
4. Preserve baseline semantic positives. A recovered span can become a semantic
   prediction only when **both independently extracted named axes** identify its
   endpoints; no nearest-wall identity and no synthetic axes. No new pair met
   that condition here. Raw candidates always carry `credited=false`.
5. Execute the normalized #1304 comparison seam for unresolved L03 tokens. Keep
   unregistered positions null and extraction/correspondence unverified. Model
   observations and evidence are retained; neither source is corrected. The
   `axis` diagnostic category is a carrier for a dimensional query, not an assertion
   that an unbound label names an axis or has a measured model counterpart.
6. Hash all nine native inputs, corpus/baseline and used model evidence before
   and after replay. Reject stale bytes; this is not an OS lock and cannot detect
   an edit restored between snapshots.

## Before / after, unchanged semantic metric

| Sheet | Correct / truth before → after | Recall before → after | Precision before → after | Wrong | Guard |
|---|---|---|---|---:|---|
| L03, TUNE | 7/82 → 7/82 | 8.54% → 8.54% | 1.0 → 1.0 | 0 | PASS |
| KNS section, TUNE | 10/12 → 10/12 | 83.33% → 83.33% | 1.0 → 1.0 | 0 | PASS |
| KNS-floor, HOLD-OUT | 0/6 → 0/6 | 0% → 0% | null → null | 0 | zero_prediction_pass |

| Sheet / first blocking cause | Before | After |
|---|---:|---:|
| L03 correct semantic binding | 7 | 7 |
| L03 text found, not bound to own line | 13 | 13 |
| L03 own span, endpoint identity absent | 59 | 59 |
| L03 display rounding/overrides | 3 | 3 |
| KNS correct semantic binding | 10 | 10 |
| KNS endpoint identity absent | 2 | 2 |
| HOLD-OUT non-cardinal unsupported | 6 | 6 |

## Separate geometry diagnostic, NOT recall credit

| Sheet | Raw geometry candidates | With frozen native label | Exact native line/endpoints | Newly recovered displaced labels |
|---|---:|---:|---:|---:|
| L03 | 45 | 44 | 44 | 0 |
| KNS | 8 | 8 | 8 | 0 |
| HOLD-OUT | 0 | 0 | 0 | 0 |

44/44 and 8/8 are **conditional geometry-location agreement on already labelled
native tokens**, not overall candidate precision or semantic recall. L03 has one
additional candidate outside the frozen native truth; it is not credited and its
correctness is unmeasured. In particular, do not report 45/82 recall or call that
extra candidate a verified dimension. No raw candidate becomes an approved
wall-face identity. This conservative experiment did not solve displacement.

Supported paper-scales: L03 p1-v1 48.51597594028668 mm/pt (5 independent edges),
KNS p1-v1 30.18992331219903 mm/pt (9 independent edges). Other L03 viewports and
HOLD-OUT remain unknown; no shared/printed/oracle scale fallback.

## Model cross-check and unresolved ledger

[Compact results and complete native-handle ledger](../../tools/research/pdf_album/dimension-geometry-results.json)
contains every one of the 100 frozen handles, before/after classes and geometry
location checks, plus all 76 unresolved L03 PDF tokens with bbox, literal numeric
value and manual-check reason. Native misses (75) and unresolved PDF tokens (76)
are **different inventories**, not interchangeable denominators. Compare emits
one row per token per model; both original model observation inventories are
retained in the full evidence report, with unmatched reasons.

Inputs: [#1304 model observations](../../jobs/KPP1/audit-1304/input-final.json).
No live DCC, FBX rewriting, new model observation, wall identity or plan-to-model
registration was invented. A future improvement requires source-bound L03
endpoint identities/leader interpretation, not a relaxed score or forced match.
This is a measured negative research result, not an 80%-recall delivery.

## Reproduction and verification

```bash
uv sync --extra pdf-review
uv run python -m tools.research.pdf_album.dimension_geometry
uv run pytest -q tests/test_pdf_dimension_geometry.py tests/test_pdf_dimension_autoresearch.py tests/test_album_dimension_recall.py tests/test_album_compare.py
```

Tests-first commit `07ab1a62`: 1 failed because the new geometry module was absent;
after the scale slice 1 passed. Next tracer: reconstruction missing, 1 failed /
1 passed; after reconstruction 2 passed. Generated scale-count, cycle/permutation,
nonfinite, exact residual threshold, unsupported orientation, duplicate-label,
missing extension/tick, empty, fresh-process native replay and output-argument
refusal probes are permanent regressions. Final affected/full-suite receipts
and exact tested head are in the PR, not a guessed count in this note.

Full raw replay, reducer and SHA256SUMS are archived under
`G:/Мой диск/AGR-evidence/1335-pdf-dimension-geometry/evidence-v001/`.
Only small text results/hashes are committed. Cloud-sync completion is not measured.
