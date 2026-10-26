# Agent lookup: measured results

Date: 2026-10-26. Source and preregistration: [PROTOCOL.md](PROTOCOL.md).
**60 final measured rows, 60 fresh sessions, one answer model (`claude-sonnet-4-6`).**
All 42 numeric answers were script-scored; all 18 API answers were independently graded by
`claude-haiku-4-5-20251001`. [Raw rows](results.jsonl), [judge](judge.json), [isolation receipt](isolation.json),
[exact commands / versions](COMMANDS.md). Partial answers count separately, not as correct.

## Overall comparison

| Variant | Correct / partly / wrong | Accuracy | Median total tokens | Median CLI wall (s) | Token change vs A | Accuracy change vs A | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| A — grep/read baseline | 20 / 0 / 0 | 100% | 12,666.5 | 7.8265 | +0.00% | +0.00% | reference |
| B — local AST graphify | 20 / 0 / 0 | 100% | 20,127.0 | 11.0615 | +58.90% | +0.00% | **not adopted** |
| C — context7 MCP | 20 / 0 / 0 | 100% | 18,635.5 | 8.2980 | +47.12% | +0.00% | **not adopted** |

Adoption rule fixed before measurement: relative accuracy improvement **>=10% OR median-token
reduction >=30%**. Neither candidate qualifies. Equal accuracy is not an improvement. With baseline
at 20/20, this small set has an accuracy ceiling; it cannot demonstrate a 10% accuracy gain.

## Category comparison

| Category (questions per variant) | Variant | Correct | Median tokens | Median CLI wall (s) |
|---|---|---:|---:|---:|
| repo (8) | A | 8/8 | 19,489.0 | 11.6195 |
| repo (8) | B | 8/8 | 20,127.0 | 12.3605 |
| repo (8) | C | 8/8 | 20,705.5 | 10.7435 |
| job (6) | A | 6/6 | 10,491.0 | 5.3485 |
| job (6) | B | 6/6 | 19,896.5 | 8.5310 |
| job (6) | C | 6/6 | 15,406.5 | 5.4005 |
| api (6) | A | 6/6 | 12,666.5 | 9.4845 |
| api (6) | B | 6/6 | 20,582.0 | 11.5460 |
| api (6) | C | 6/6 | 18,214.5 | 9.5130 |

## Token and tool accounting

| Variant | Uncached input | Cache-read input | Cache-creation input | Output | Total tokens | CLI wall total (s) | Explicit Read calls | MCP calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 235,656 | 100,855 | 11,424 | 348,035 | 188.582 | 3 | 0 |
| B | 118 | 511,651 | 137,996 | 14,931 | 664,696 | 280.154 | 14 | 20 |
| C | 101 | 292,485 | 97,226 | 10,946 | 400,758 | 186.938 | 5 | 8 |

Independent judge overhead (not in answer-model medians): **6,390 tokens**, **25.419 s**.
Files read means explicit Read tool targets, not an invented count of every file scanned by Grep/Glob.
`tool_calls` preserves actual search scopes and MCP inputs. One B Read (Q06) reads its own
isolated CLI tool-result overflow file; that is recorded, not mislabeled as a source file.
Wall time is Claude `duration_ms`, excluding parent process startup. Graph build/setup time was
not separately timed and is not hidden in the query medians. The graph contains **17,839 nodes /
48,230 edges** from **1,500 code files**, excluding **463 docs / 1 paper / 10 images**.

## Per-question table

| Question | Category | A grade / tokens / s | B grade / tokens / s | C grade / tokens / s |
|---|---|---|---|---|
| Q01 | repo | correct / 17,947 / 7.769 | correct / 20,154 / 12.719 | correct / 47,376 / 16.080 |
| Q02 | repo | correct / 21,031 / 14.095 | correct / 20,100 / 12.002 | correct / 20,406 / 13.309 |
| Q03 | repo | correct / 14,096 / 6.828 | correct / 17,929 / 9.894 | correct / 14,463 / 8.123 |
| Q04 | repo | correct / 43,375 / 16.696 | correct / 206,588 / 52.544 | correct / 31,839 / 12.872 |
| Q05 | repo | correct / 55,596 / 20.791 | correct / 29,222 / 21.073 | correct / 25,866 / 18.130 |
| Q06 | repo | correct / 31,893 / 12.662 | correct / 84,115 / 19.202 | correct / 17,216 / 7.138 |
| Q07 | repo | correct / 8,237 / 5.124 | correct / 17,954 / 8.742 | correct / 21,005 / 8.615 |
| Q08 | repo | correct / 17,328 / 10.577 | correct / 17,360 / 10.738 | correct / 15,114 / 5.375 |
| Q09 | job | correct / 10,612 / 5.971 | correct / 23,340 / 9.088 | correct / 14,981 / 5.080 |
| Q10 | job | correct / 10,883 / 5.551 | correct / 23,400 / 8.931 | correct / 15,832 / 5.221 |
| Q11 | job | correct / 10,319 / 5.146 | correct / 16,276 / 8.131 | correct / 21,843 / 8.085 |
| Q12 | job | correct / 10,370 / 4.714 | correct / 16,453 / 7.616 | correct / 14,751 / 5.421 |
| Q13 | job | correct / 10,265 / 5.050 | correct / 16,363 / 7.725 | correct / 14,875 / 5.380 |
| Q14 | job | correct / 11,427 / 6.062 | correct / 40,576 / 14.238 | correct / 22,469 / 7.311 |
| Q15 | api | correct / 12,905 / 12.489 | correct / 12,489 / 11.385 | correct / 20,650 / 10.146 |
| Q16 | api | correct / 12,428 / 7.884 | correct / 18,511 / 8.823 | correct / 11,186 / 8.473 |
| Q17 | api | correct / 8,806 / 6.754 | correct / 22,653 / 12.048 | correct / 23,267 / 15.083 |
| Q18 | api | correct / 17,579 / 15.450 | correct / 23,792 / 23.660 | correct / 16,374 / 8.880 |
| Q19 | api | correct / 10,013 / 9.102 | correct / 12,207 / 11.707 | correct / 20,055 / 12.538 |
| Q20 | api | correct / 12,925 / 9.867 | correct / 25,214 / 9.888 | correct / 11,190 / 5.678 |

## Limits and excluded attempt

- One trial per question/treatment, only 20 questions, six API questions: no confidence interval or broad superiority claim.
- Job questions are all KPP1 facts because the frozen main lacks AC07 and D186. This is a bounded pilot lookup set, not representative of every job.
- B measures strictly local AST graphify, **not** semantic indexing of documentation/PDFs. Most rule answers require fallback search.
- C can retrieve current upstream API docs; these are not guaranteed to be version-pinned Blender 5.0 docs. Actual resolved IDs/queries are in the rows.
- Context7 was used only for API questions; no repo/job text, drawings or private PDFs were submitted to it.
- The initial complete 60-session attempt was excluded wholesale after automatic global Claude runtime-cache writes were detected. Its raw evidence is retained separately, not mixed into these medians. See PROTOCOL.md for the repair and reproducible isolation hashes.
- Final sessions plus their independent judge left the three monitored global config paths unchanged (byte hashes and absent-path state match in isolation.json). No global tool/skill installation or persistent MCP change was made.
- No candidate is adopted or registered for workers. User acceptance of tooling is a separate later decision.
