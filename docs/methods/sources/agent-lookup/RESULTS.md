# Agent lookup: measured results

Date: 2026-10-26. Frozen source/truth: [PROTOCOL.md](PROTOCOL.md).
**80 measured rows, 80 fresh sessions, one answer model (`claude-sonnet-4-6`).**
All 56 numeric answers were script-scored; all 24 API answers were independently graded by
`claude-haiku-4-5-20251001` (original 18 grades plus six new D grades, no regrading A-C).
[Rows](results.jsonl), [original judge](judge.json), [D judge](judge-D.json),
[80-row isolation receipt](isolation-80.json), [commands/versions](COMMANDS.md), [D preregistration](extension-D.json).
Partial answers count separately, not as fully correct. A-C rows remain byte-identical to their
original frozen 60-row result; D was added later by the operator, not interleaved four ways.

## Overall comparison

| Variant | Correct / partly / wrong | Accuracy | Median total tokens | Median CLI wall (s) | Token change vs A | Accuracy change vs A | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| A — grep/read baseline | 20 / 0 / 0 | 100% | 12,666.5 | 7.8265 | +0.00% | +0.00% | reference |
| B — local AST graphify | 20 / 0 / 0 | 100% | 20,127.0 | 11.0615 | +58.90% | +0.00% | **not adopted** |
| C — context7 MCP | 20 / 0 / 0 | 100% | 18,635.5 | 8.2980 | +47.12% | +0.00% | **not adopted** |
| D — local xerj MCP | 19 / 1 / 0 | 95% | 41,262.0 | 11.0370 | +225.76% | -5.00% | **not adopted** |

Adoption rule fixed before any measurements: relative accuracy improvement **>=10% OR
median-token reduction >=30%**. None of B/C/D qualifies. Equal accuracy is not an improvement.
Baseline 20/20 creates an accuracy ceiling on this small question set.

## Category comparison

| Category (questions per variant) | Variant | Correct / partly | Median tokens | Median CLI wall (s) |
|---|---|---:|---:|---:|
| repo (8) | A | 8/8 / 0 partly | 19,489.0 | 11.6195 |
| repo (8) | B | 8/8 / 0 partly | 20,127.0 | 12.3605 |
| repo (8) | C | 8/8 / 0 partly | 20,705.5 | 10.7435 |
| repo (8) | D | 8/8 / 0 partly | 42,930.5 | 17.2785 |
| job (6) | A | 6/6 / 0 partly | 10,491.0 | 5.3485 |
| job (6) | B | 6/6 / 0 partly | 19,896.5 | 8.5310 |
| job (6) | C | 6/6 / 0 partly | 15,406.5 | 5.4005 |
| job (6) | D | 6/6 / 0 partly | 38,655.0 | 7.1040 |
| api (6) | A | 6/6 / 0 partly | 12,666.5 | 9.4845 |
| api (6) | B | 6/6 / 0 partly | 20,582.0 | 11.5460 |
| api (6) | C | 6/6 / 0 partly | 18,214.5 | 9.5130 |
| api (6) | D | 5/6 / 1 partly | 39,248.0 | 13.6085 |

## Token and tool accounting

| Variant | Uncached input | Cache-read input | Cache-creation input | Output | Total tokens | CLI wall total (s) | Explicit Read calls | MCP calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 235,656 | 100,855 | 11,424 | 348,035 | 188.582 | 3 | 0 |
| B | 118 | 511,651 | 137,996 | 14,931 | 664,696 | 280.154 | 14 | 20 |
| C | 101 | 292,485 | 97,226 | 10,946 | 400,758 | 186.938 | 5 | 8 |
| D | 116 | 890,393 | 120,908 | 15,725 | 1,027,142 | 255.365 | 9 | 26 |

Original A-C independent judge (18 API answers): **6,390 tokens**, **25.419 s**, separate from answer-model medians.

D independent judge (six API answers): **2,876 tokens**, **11.528 s**, separate from answer-model medians.

Files read means explicit Read tool targets, not an invented count of files internally scanned
by Grep/Glob or an index. `tool_calls` preserves search scopes/MCP inputs; raw transcripts preserve
retrieved passages and citations. Q06-B reads its own isolated CLI tool-result overflow file.
Wall time is Claude `duration_ms`, excluding parent process startup. MCP tool schema/startup and
retrieval costs are included; this experiment does not separately attribute them to ranking algorithms.

## Local index/setup coverage

- B: **17,839 nodes / 48,230 edges**, **1,500 code files**; skipped **463 docs / 1 paper / 10 images**, plus 66 unclassified files. Build/install wall time was not separately measured.
- D: xerj **1.0.0-rc.99**, **1,940 file paths / 1,911 unique contents / 1,909 indexed contents / 29 duplicates**, **48,415 records / 99 datasets**, **1,048/1,048 code files indexed**. File classification differs from graphify, so code-file counts are not a like-for-like recall denominator.
- D junk files (reported, not silently dropped): `adapters/cad/__init__.py` (empty); `tools/assembly_inventory/NuGet.Config` (XML yielded no records). Default ignores also skipped 31 files / pruned six directories. See setup receipts, not a claim that every repo byte was indexed.
- D uses loopback-only offline lexical embeddings and local code **and documents**. Reranking, feedback and hub tools are disabled; no `xerj init` or profile registration. Native seven read-only MCP tools are available.
- D setup: first foreground command hit a 240 s timeout after sealing indexed records. The same journal completed in background with documented exit 3 `completed-with-junk`; final terminal wall 75.6 s (JSON reports 68.7 s for its narrower invocation-summary scope). These are not per-question times or a fabricated full build duration.

## Per-question table

| Question | Category | A grade / tokens / s | B grade / tokens / s | C grade / tokens / s | D grade / tokens / s |
|---|---|---|---|---|---|
| Q01 | repo | correct / 17,947 / 7.769 | correct / 20,154 / 12.719 | correct / 47,376 / 16.080 | correct / 112,569 / 21.012 |
| Q02 | repo | correct / 21,031 / 14.095 | correct / 20,100 / 12.002 | correct / 20,406 / 13.309 | correct / 109,943 / 22.467 |
| Q03 | repo | correct / 14,096 / 6.828 | correct / 17,929 / 9.894 | correct / 14,463 / 8.123 | correct / 40,364 / 9.502 |
| Q04 | repo | correct / 43,375 / 16.696 | correct / 206,588 / 52.544 | correct / 31,839 / 12.872 | correct / 42,160 / 14.144 |
| Q05 | repo | correct / 55,596 / 20.791 | correct / 29,222 / 21.073 | correct / 25,866 / 18.130 | correct / 87,869 / 23.957 |
| Q06 | repo | correct / 31,893 / 12.662 | correct / 84,115 / 19.202 | correct / 17,216 / 7.138 | correct / 43,701 / 17.636 |
| Q07 | repo | correct / 8,237 / 5.124 | correct / 17,954 / 8.742 | correct / 21,005 / 8.615 | correct / 35,864 / 16.921 |
| Q08 | repo | correct / 17,328 / 10.577 | correct / 17,360 / 10.738 | correct / 15,114 / 5.375 | correct / 36,237 / 6.418 |
| Q09 | job | correct / 10,612 / 5.971 | correct / 23,340 / 9.088 | correct / 14,981 / 5.080 | correct / 47,474 / 8.055 |
| Q10 | job | correct / 10,883 / 5.551 | correct / 23,400 / 8.931 | correct / 15,832 / 5.221 | correct / 47,712 / 7.317 |
| Q11 | job | correct / 10,319 / 5.146 | correct / 16,276 / 8.131 | correct / 21,843 / 8.085 | correct / 34,734 / 5.634 |
| Q12 | job | correct / 10,370 / 4.714 | correct / 16,453 / 7.616 | correct / 14,751 / 5.421 | correct / 34,844 / 6.891 |
| Q13 | job | correct / 10,265 / 5.050 | correct / 16,363 / 7.725 | correct / 14,875 / 5.380 | correct / 34,712 / 5.325 |
| Q14 | job | correct / 11,427 / 6.062 | correct / 40,576 / 14.238 | correct / 22,469 / 7.311 | correct / 42,466 / 7.803 |
| Q15 | api | correct / 12,905 / 12.489 | correct / 12,489 / 11.385 | correct / 20,650 / 10.146 | correct / 72,565 / 22.544 |
| Q16 | api | correct / 12,428 / 7.884 | correct / 18,511 / 8.823 | correct / 11,186 / 8.473 | correct / 39,341 / 12.572 |
| Q17 | api | correct / 8,806 / 6.754 | correct / 22,653 / 12.048 | correct / 23,267 / 15.083 | correct / 39,155 / 14.645 |
| Q18 | api | correct / 17,579 / 15.450 | correct / 23,792 / 23.660 | correct / 16,374 / 8.880 | correct / 64,241 / 19.526 |
| Q19 | api | correct / 10,013 / 9.102 | correct / 12,207 / 11.707 | correct / 20,055 / 12.538 | partly / 36,748 / 7.089 |
| Q20 | api | correct / 12,925 / 9.867 | correct / 25,214 / 9.888 | correct / 11,190 / 5.678 | correct / 24,443 / 5.907 |

## Error analysis

D Q19 is **partly**: `rt.exportFile(str(target), rt.Name('noPrompt'), using=rt.FBXEXP)` omits
`selectedOnly=True`, essential to exporting **selected** objects. The independent judge retained
credit for the no-prompt FBX arguments but did not count the incomplete call as fully correct.
No answer, threshold or earlier grade was repaired after scoring.

## Limits and excluded attempt

- One trial per question/treatment, 20 questions and six API questions: no confidence interval or broad superiority claim.
- D was added by operator after all A-C sessions had finished. Same source/questions/model/prompts and frozen adoption threshold; later block ordering can confound wall-time comparisons. Original A-C rows/grades are preserved byte-for-byte.
- Job questions are all KPP1 facts because frozen main lacks AC07 and D186. Not representative of every pilot job.
- B tests strictly local AST graphify, not semantic prose/PDF indexing. D indexes documents locally; this is an important coverage difference, not a hidden reranker.
- C can retrieve current API docs, not necessarily version-pinned Blender 5.0 docs. It made eight calls across Q15-Q18 (4/6 API questions); Q19-Q20 used local lookup. Q16 resolved a library without querying docs. This measures offered tools, not a forced context7-only solver.
- All 14 repo/job questions per variant stayed local; hosted context7 received only public API queries, never private drawings or source snippets.
- The initial complete 60-session attempt was excluded wholesale after automatic global Claude runtime-cache writes. Its raw evidence is retained separately; never mixed into these 80 rows. PROTOCOL.md discloses the repair.
- Final 80 sessions plus both independent judge calls left the three monitored global config paths unchanged (isolation-80.json); no global graphify/context7/xerj setup or persistent MCP configuration was installed.
- Vendor xerj claims (2.7x fewer **output** tokens, 94% first-file localization) describe a different corpus/task/metric. Here the adoption test counts **all input and output tokens** and scores answers; first-file localization was not separately scored. No direct validation/refutation of those vendor percentages is claimed.
- No candidate is adopted or registered for workers. User authorization for adoption is separate.
