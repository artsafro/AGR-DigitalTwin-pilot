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

## Standing #5 (t_e21acbc0) — frozen contract, R2 / R3

Frozen before any candidate code exists. Base `f6a8793b` (origin/main; `src/dt_ai/album/` and
`tools/research/pdf_album/` are byte-identical to `cc99bfdb`, so the #4 harness and corpus apply unchanged).

- Metric, command, order, exclusions, parity and prohibitions: exactly the #4 contract above. Command:
  `uv run --extra pdf-review python -m tmp.ar_pdf_binding --round R2 --out C:/x/ar_t_e21acbc0/r2.json`
  (then `--round R3 --out .../r3.json`). The driver and candidate builder are committed this time in
  [`autoresearch-pdf-binding-harness/`](autoresearch-pdf-binding-harness/) (review P3 of #4); they are copied
  to the ignored `tmp/` to run. Median of 3 per variant, pairs B,C / C,B / B,C in one interpreter.
- R2 (the backlog target): inside `_bind_page`, the strict/padded text search for each span
  (`strict_hits`, `candidates`) reads only runs whose along-axis centre lies in an index window
  `[a - pad, b + pad]` (bisect over runs sorted per text direction; `pad` = largest possible R1 padding,
  0 for spans not shorter than it). `_span_gap` still decides every hit; sorting by `(gap, run)` and the
  strict-over-padded and ownership rules are unchanged, so the window must be a superset of all hits.
  The candidate is built from the current `binding.py` text by exact, count-checked replacement of the two
  loops and patched in memory as `binding._bind_page`; R1 `_chains` is NOT included.
- R3 (declared now, run only after R2 is recorded regardless of its result): R2 + #4's R1 `_chains`
  (archived `C:/x/ar_t_c528b5b4/ar_candidate_binding.py`, SHA-256 recorded in the receipt) against the
  same unmodified baseline — the question "would adopting both clear the bar".
- Keep threshold per round: median C <= 0.80 × median B, every pair faster, exact parity in all six samples.
- Stop: these two rounds only; per round 8 minutes or first parity failure. No retuning between rounds.
- Extra parity proof: affected album tests run with the candidate patched in (same file set as #4);
  `--probe` mutation witness re-run.
- OBSERVE: a passing round is a proposal for a separate production PR + review, never applied to
  `src/` on this branch.

### R2 — keep (OBSERVE proposal)

Indexed `_span_gap` search ([`ar_candidate_r2.py`](autoresearch-pdf-binding-harness/ar_candidate_r2.py)), R1 not included.

| Pair (execution order) | Baseline, s | Candidate, s | Complete parity |
|---|---:|---:|---|
| 1 B,C | 7.152 | 4.105 | yes |
| 2 C,B | 6.460 | 4.330 | yes |
| 3 B,C | 6.776 | 4.554 | yes |
| Median | 6.776 | 4.330 | ratio **0.639** → keep |

### R3 — R2 + R1, keep (OBSERVE proposal)

| Pair (execution order) | Baseline, s | Candidate, s | Complete parity |
|---|---:|---:|---|
| 1 B,C | 6.119 | 3.396 | yes |
| 2 C,B | 5.494 | 4.638 | yes |
| 3 B,C | 5.577 | 3.243 | yes |
| Median | 5.577 | 3.396 | ratio **0.609** → keep |

Both rounds: all six samples byte-identical to the untimed reference (three complete documents), the
historical evaluator result identical (`result_sha256 5c93ea5f…`, same as #4) and its guard green; `--probe`
again showed the `note` mutation passes the historical score but fails complete-document parity.
Affected album tests with the candidate patched in (#4 file set): R2 **192 passed**, R3 **192 passed**.
Loaded-host, warm-process numbers; baseline itself drifted 5.5–7.2 s between rounds, ratios are within-round.

Receipts: `C:/x/ar_t_e21acbc0/r2.json` (SHA-256 `8777f50bf4c9e78081b7c679ce1a57d29b10e25d436aec51090ff5f78d4262e8`),
`r3.json` (`00847247bfce5f1d72753c34b8d26c520cc934685bb7c760ba961a22f64b3313`); timing HEAD `7c264d80`
(contract commit), binding.py SHA-256 `b8af892b…`, R1 archive `039db4b0…`. Stop rule reached (two rounds).
Reproduce: copy `autoresearch-pdf-binding-harness/*.py` to `tmp/`, run the contract command with a new `--out`.

Verdict: R2 alone clears the bar (−36 %); R1 adds ~3 points on top. Per OBSERVE neither is applied to
`src/` here: adoption is a separate production PR (R2 first, R1 as its own reviewed change), with this
bench as the parity proof plus a boundary unit test that the window is a superset (short span with
padding, NaN centre, labels exactly at `a - pad` / `b + pad`).
