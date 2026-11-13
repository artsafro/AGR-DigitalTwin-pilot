# PDF dimension autoresearch (#1321)

## Кратко для Артёма

Остановка поиска: **три раунда с приростом <1% (R2–R4)**. По решению Артёма
2026-11-13 восстановлен R1: TUNE вырос с 15/94 до **17/94 (18.09%)**;
цель 80% не достигнута. KPP1 L03 — 7/82, КНС разрез — 10/12 (precision 1.0);
HOLD-OUT КНС план — 0/6,
precision=null, отдельный zero-prediction PASS [D277]. Масштаб не угадывался,
`passed=false`; оси, отметки и их verdicts совпадают с frozen baseline на всех листах.

R1 восстановил два размера КНС (200/250mm, `341A`/`341C`). Первоначально он был
отклонён из-за устаревшего regression «ровно 8 positives». По явному решению
Артёма этот count заменён более сильной проверкой: каждый из восьми прежних и
двух новых native pairs найден с правильными value, line/endpoints и axes/levels;
все positives проверяются oracle, wrong=0, precision guard PASS. R1 теперь сохранён.
Основной барьер L03 — доказуемые identities внутренних граней, а не просто текст.

## Frozen protocol

Baseline production: `3f8b3712cd91f077d9ca4fcb957a8410a9ecc16f` (#1302 final fix),
identical binder at repository base `af2a90f2`. No oracle selection after tuning.
[Corpus](../../tools/research/pdf_album/dimension-autoresearch/corpus.json) freezes
all three native DIMENSION sheets documented by #1302, source DWG/DXF/PDF hashes,
evaluator-only registrations, 100 native handles and split/guard. [Baseline](../../tools/research/pdf_album/dimension-autoresearch/baseline.json)
binds its corpus hash and exact axes/levels/verdict signatures. No binaries in git.

Score is the unchanged #1302 source-location comparator: native measurement
strictly <0.5 mm, both projected extension ends AND dimension-line location
strictly <0.5 pt, one-to-one source handles. All positive semantic predictions
count, including wrong/duplicate/unsupported ones. Raw unbound spans earn no credit.
Non-cardinal floor-plan predictions cannot earn credit without independently
registered geometry; the current cardinal binder produces none. That hold-out is
weak evidence of generalisation (same KNS project and zero baseline predictions),
not an independent expert-labelled or rotated-chain benchmark. It is never used
to choose rules or parameters. No OCR/vision, scale guess, or endpoint-identity relaxation.

Every candidate changes only `src/dt_ai/album/`; control owns trial commit/revert.
Keep iff TUNE recall rises AND guard passes; report HOLD-OUT on every trial.
Stop: recall >=0.8, three consecutive gains <0.01 absolute recall, or 8h
(card runtime cap 120min is stricter). No existing tests may be loosened.

## Baseline accounting (unchanged)

Here found means positive semantic predictions, not nearby text/raw spans.
Every native handle has exactly one success/first-blocking-cause class. No wrong
predictions remain. [Full handle ledger](../../tools/research/pdf_album/dimension-autoresearch/baseline-results.json).

| Sheet / first blocking cause | Found | Correct | Wrong | Missed |
|---|---:|---:|---:|---:|
| L03 total | 7 | 7 | 0 | 75 |
| — correct binding | 7 | 7 | 0 | 0 |
| — displaced/short text not bound to own line | 0 | 0 | 0 | 36 |
| — own span recovered, endpoint identity absent | 0 | 0 | 0 | 36 |
| — native display rounding differs from measurement | 0 | 0 | 0 | 3 |
| KNS section total | 8 | 8 | 0 | 4 |
| — correct binding | 8 | 8 | 0 | 0 |
| — displaced/short text not bound to own line | 0 | 0 | 0 | 3 |
| — own span recovered, endpoint identity absent | 0 | 0 | 0 | 1 |
| KNS floor HOLD-OUT total | 0 | 0 | 0 | 6 |
| — non-cardinal chain unsupported | 0 | 0 | 0 | 6 |
| **All sheets** | **15** | **15** | **0** | **85** |

## Final accounting (restored R1)

[Final handle ledger](../../tools/research/pdf_album/dimension-autoresearch/final-results.json)
is a fresh replay of the same frozen corpus/guard, not a replacement baseline.

| Sheet / first blocking cause | Found | Correct | Wrong | Missed |
|---|---:|---:|---:|---:|
| L03 total | 7 | 7 | 0 | 75 |
| — correct binding | 7 | 7 | 0 | 0 |
| — displaced/short text not bound to own line | 0 | 0 | 0 | 15 |
| — own span recovered, endpoint identity absent | 0 | 0 | 0 | 57 |
| — native display rounding differs from measurement | 0 | 0 | 0 | 3 |
| KNS section total | 10 | 10 | 0 | 2 |
| — correct binding | 10 | 10 | 0 | 0 |
| — own span recovered, endpoint identity absent | 0 | 0 | 0 | 2 |
| KNS floor HOLD-OUT total | 0 | 0 | 0 | 6 |
| — non-cardinal chain unsupported | 0 | 0 | 0 | 6 |
| **All sheets** | **17** | **17** | **0** | **83** |

## Rounds

| Round | One change | TUNE correct/truth | L03 / KNS precision | HOLD-OUT recall / precision | Replay guard | Existing tests | Decision |
|---|---|---:|---|---|---|---|---|
| Baseline | #1302 final | 15/94 | 1.0 / 1.0 | 0/6 / null | PASS | 71 passed | baseline |
| R1 | Short-span text displaced up to 2em beyond ticks | 17/94 | 1.0 / 1.0 | 0/6 / null | PASS (v2) | 70 passed / 1 failed: exact-eight KNS contract | discard |
| R2 | Parallel stroke groups 0.1pt ->0.5pt | 15/94 | 1.0 / 1.0 | 0/6 / null | PASS | 71 passed | discard: no gain |
| R3 | Minimum diagonal tick 1.5pt ->0.75pt | 15/94 | 1.0 / 1.0 | 0/6 / null | PASS | 71 passed | discard: no gain |
| R4 | Perpendicular text search 2.5 ->4 text heights | 15/94 | 1.0 / 1.0 | 0/6 / null | PASS | 71 passed | discard; STOP |
| R1 restoration | Same two-em rule; explicitly authorized source-bound regression replacement | 17/94 | 1.0 / 1.0 | 0/6 / null | PASS | 72 passed (two affected files, including 24 boundary probes) | keep |

[Round receipts](../../tools/research/pdf_album/dimension-autoresearch/rounds.json)
record trial/revert commits, source SHA256 and every sheet's metrics/miss classes.
R1 additionally recovers 21 own L03 spans, all still missing endpoint identity;
no credit. All four synthetic trial witnesses fail before and pass with their
individual candidate: 3 initial failures plus 1 later failure; GREEN 1 passed each.
Rejected witnesses are evidence, not permanent feature requirements.
Control skips regression commands for non-improvements (R2–R4: `not_run`);
their **manual** 71-test logs and full replay guard were run before `finish`.
These are not relabelled as controller guard executions. R2–R4 have zero raw
AND retained gain, so the plateau stop does not depend on treating rejected R1 as zero.

### Harness repairs, not hidden retuning

Initial run `03e54b7cd39242d38c6d418e61de7224` falsely rejected R1: signature also
included dimension-only diagnostics with renumbered IDs. Independent comparison
proved exact axes/levels equal. Failed trial/revert retained. Tests-first
`dcd56a9c` failed 1 test; `e57c19b3` scoped the signature to complete axes,
complete level records minus dimension-dependent IDs, and axis/level findings.
Guard v2 was re-frozen **before** run `5db0a7cba51e458ba2b586b352b73b9d`.
No source/split/score tolerance changed. R1 reran and failed the real regression.

Post-loop packaging exposed raw manifest digests dependent on CRLF/Git-LF.
Tests-first `be05785e` failed 1 test. Final receipt hashes canonical JSON
(UTF-8, sorted keys, no whitespace); native source hashes remain raw-byte hashes.
Original raw corpus SHA256:
`beb7ae3dca186c459239e017c1a067b43da22723459e01a324ddec4d1a757f20`.
Final canonical corpus SHA256:
`351cbe99af8fb29b838d969baaa0c18bca49eb341e9ddcfe0b08d70690918b70`.
Original bytes are archived. Mutation-injection fixture then exposed a captured
default corpus-path argument (KeyError `L03`); explicit active-path calls fixed it.
Final harness replayed all four own trial commits: exact metrics, per-handle
classes and replay guards match archived v2 results **4/4**. No outcome retuning.
Research search status is `stopped_plateau`, not target reached. Control records archived
unchanged; last `active` status is not presented as automated goal completion.
Kanban drove continuation because this runtime has no native Codex Goal API.

### Authorized delta: merge main and restore R1 (2026-11-13)

Artem explicitly authorized the same-PR rework on card `t_4089d009`: merge main,
replace the exact-eight assertion with native-pair correctness/precision, restore R1.
Main `3d48ede1` was merged as `738d02ec`; the only conflict was adjacent D276/D277
rows, both preserved in increasing order. No source or frozen protocol was edited.
The production delta is the original R1 rule with a named `padding` local for readability.
No new search/tolerance round was run. Historical control outcomes in `rounds.json`
and sealed evidence stay byte-for-byte intact; the adoption supersedes R1's discard,
not its historical failing-test receipt.

Tests-first `3e916073` requires both new native pairs plus all old identities:
on merged baseline `738d02ec`, 2 failed / 0 passed. Additional tests-first
`48d056e1` probes both rotations, span lengths 10/16/20pt and offsets
1/15.9/16/16.1pt at font size 8: 4 failed / 20 passed before restoration.
With R1, both complete affected files pass: 72 passed / 0 failed, including
24/24 strict-boundary probes and fresh-process three-sheet replay.
The native regression asserts exact original axes/level pairs and new
`341A` (-8.200/-8.000) and `341C` (-0.350/-0.100); 341E/341F stay refused.
The combined replay additionally proves every baseline correct handle survives,
only 341A/341C are newly credited, and exact frozen axis/level signatures match.
Final affected/full-suite counts and exact tested head are in the updated PR receipts.

### Remaining boundaries

- L03 wall-face identities need a separately proven source graph, not nearest-wall
  guessing. No undecided model rule was needed for these bounded experiments.
- Display-rounded 2360/4720/1520 remain different from native 2355/4715/1515mm.
  Future question for Artem **only if pursuing that class**: may documented native
  DIMRND be scored as annotation agreement separately from exact geometry?
  Current scoring stays exact; no such waiver is needed or applied by this card.
- Non-cardinal support needs independent registration and rotated semantic-axis
  identity; the HOLD-OUT remains measured zero, not omitted.
- R1 adoption now has stronger source-bound expectations for both new pairs and
  every old identity/refusal, under explicit user authorization. The frozen score,
  precision/scale/axis-level guards and all other tests remain unchanged.

## Reproduction

One-time extraction uses `ezdxf.readfile(copy).modelspace().query('DIMENSION')`,
`get_measurement()`, `defpoint2/3`, `defpoint`, `text_midpoint` and native block
MTEXT. The #1302 frozen registration locates native labels within 3pt and must
find exactly one matching run; it never enters `bind_album`. Existing headless
AutoCAD plots from #1290/#1302 are reused byte-for-byte; originals are not reopened
or saved. Extraction driver and hashes are sealed with the experiment evidence.

```bash
uv sync --extra pdf-review
uv run --with ezdxf python -m tmp.freeze_dimensions
uv run python -m tools.research.pdf_album.dimension_autoresearch
uv run python -m tools.research.pdf_album.dimension_autoresearch --guard
```

The evaluator has no output/report/temp-path API: stdout only. It re-hashes inputs
before and after the complete run and rejects aliased inputs and stale corpus
receipts. Source mutation restored between hash snapshots is not detected; single
writer ownership and frozen copies remain prerequisites, not a claimed OS lock.

Evidence root: `G:/Мой диск/AGR-evidence/1321-pdf-dimensions-autoresearch/evidence-v001/`.
[Evidence receipt](../../tools/research/pdf_album/dimension-autoresearch/evidence.json)
binds SHA256SUMS.txt and member count: nine native copies, extraction/replay
drivers, raw control logs/events/config, trial witnesses and RED/GREEN logs.
Mounted bytes verified; cloud-sync completion not measured. Restore
`evidence-v001/drivers/freeze_dimensions.py` into ignored `tmp/` before extraction;
if a native copy is missing, restore it to its manifest path and verify SHA256.
Final tests cover mutation of sources/corpus/baseline, stale receipts, aliases,
duplicates, nonfinite/unsupported evidence, exact score boundaries, hardlinked
output attempts and fresh-process repeat. The evaluator is stdout-only, has no
output/report/.partial API and deletes nothing. Final affected/full-suite counts
and tested SHA are in PR Author receipts/generated CI receipt: no post-suite commit
that would falsify the exact tested head.
