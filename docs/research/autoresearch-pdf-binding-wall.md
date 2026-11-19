# PDF binding wall time — standing #4 (t_c528b5b4)

## Кратко для Артёма

На трёх исходных листах обработка сократилась с **7,072 до 5,860 с (−17,15%)**, без изменения результатов. Порог −20% не пройден: код не принят, исходники и сданные пакеты не менялись.

## Frozen contract

- Base `cc99bfdb985bf4ee5487cdc73acf1cb3f15a8f47`. Continue the [#1321 harness](autoresearch-pdf-dimensions.md) and its exact three-sheet manifest (L03, KNS, KNS-floor); no fixture substitutions. PDF intake is upstream of the cold building flow (readiness areas 1–4); this is not a claim to move the readiness score or improve recognition.
- One metric: wall seconds for the three `bind_album(..., pages=[1])` calls made by `tools.research.pdf_album.dimension_autoresearch.evaluate()`. Exclude setup, corpus hashing, scoring, parity serialization and interpreter startup. Command: `uv run --extra pdf-review python -m tmp.ar_pdf_binding --out C:/x/ar_t_c528b5b4/r1.json`. Thin timing/OBSERVE adapter around the existing evaluator, not an alternative extractor or scorer. Measure three baseline and three candidate samples in one interpreter (B,C / C,B / B,C); import and perform one untimed exact baseline reference replay first. Each sample opens all three PDFs anew; no cross-call memoization. Report all six times and loaded-host scope, not cold-disk or all-album performance.
- Keep threshold: median candidate ≤ 0.80 × median baseline, with every pair faster and all gates green. Stop at one candidate round, first parity failure, or 8 minutes of measurement, whichever comes first. No other rounds under this contract. A failed or incomplete run does not establish improvement.
- Parity: exact complete binding document for each sheet (ordered JSON arrays and all JSON fields, no tolerances/exclusions), identical evaluator results, and successful historical guard on every replay; evaluator's input hash checks run every sample. Prove complete-document comparison detects a change even outside the historical axis/level and semantic-score comparison. Run affected album tests and the prescribed repo guards. No calibration ranking: this is timing with exact output parity, not a quality metric.
- Prohibited: skipping tests or sheets, changing thresholds/semantics, touching corpus/receipts, source drawings or deliveries, changing other cards' files, editing the production binder during OBSERVE, warming a variant from cached binding results. A keeper is a proposal for review, not an automatic change to production.

## R1 — reject (OBSERVE)

The diagnostic profile of the existing evaluator attributed 4.24 s cumulative (instrumented, not the timing metric) to `_chains`. R1 would index parallel inline text by its leading coordinate and project ticks once per orientation/coordinate group, then range-slice projected positions per span. The strict numeric-text uniqueness, exact geometry predicates and tick merge remain in place. Only `_chains` was substituted in process, never on disk in `src/`.

| Pair (execution order) | Baseline, s | Candidate, s | Complete parity |
|---|---:|---:|---|
| 1 B,C | 7.072347 | 6.502651 | yes |
| 2 C,B | 6.315890 | 5.859551 | yes |
| 3 B,C | 7.153781 | 5.736927 | yes |
| Median | 7.072347 | 5.859551 | ratio 0.828516 → reject |

All six samples matched the untimed reference byte-for-byte after canonical JSON encoding of all three complete documents; the exact historical evaluator result also matched and its guard passed. A deliberate change to the document `note` left the historical evaluation unchanged but failed complete-document parity. One-round stop rule reached. These are warm-process, non-isolated workstation results, not an idle-host or complete-album benchmark.

Timing run HEAD: `d6947ba470e53e1b205ea8687ca5ce7e48cb0ef6`; CPython 3.14.7. The receipt `C:/x/ar_t_c528b5b4/r1.json` (SHA-256 `6e84015fc2a8d760085e812a7d49dae99c9c65e1bc586c475c075c3bee7a1986`) carries source, document and score hashes. Reproduction: copy the archived `ar_pdf_binding.py` and `ar_candidate_binding.py` from that directory to the ignored `tmp/` in the worktree at the frozen HEAD. Run the contract command with an unused output path; run `--probe` separately for the mutation witness. No production files or tests were edited.

Next target in the external backlog: independently range-index candidates reaching `_span_gap` while preserving complete output and deterministic strict/padded tie-breaks; exclude R1 from both variants.
