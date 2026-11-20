# Autoresearch: UDIM AST dispatch (standing #10, t_ef1fcf20)

## Кратко для Артёма

Проверяем, ускорит ли группировка узлов AST полный скан `duplicate_guard` без изменений в его выводе. Это OBSERVE: проверяем временный адаптер, а не меняем сканер или поставки.

## Frozen contract

- One metric: median wall seconds of three full `duplicate_guard.main(--root <worktree> --json --table)` calls per variant, alternating B/C in one process via `autoresearch-repo-guards-harness/bench.py`. Fixed source snapshot `29a12bba4ec8944649f94d13bef7ad852b58a522`. B uses existing R1+R4+R5 harness transforms in memory; C adds ordered AST dispatch for `_udim_hits` only. Neither pulls in changes from open PR #1708.
- From the worktree: `uv run python tmp/ar10_udim.py --rounds 3 --baseline r1_walk_memo,r4_lazy_scopes,r5_lazy_int_names --candidate udim_dispatch --out C:/x/ar_t_ef1fcf20/udim.json`. The adapter registers one process-local prototype in the existing bench; it must not modify that bench on disk. Keep only if C/B ≤ 0.80, all paired C faster, and parity/tests/guards pass. Stop after one round, first parity failure, or eight minutes of measurement, whichever comes first. Incomplete runs are not evidence of improvement.
- Parity: complete CLI output and exit code across all six samples; exact ordered `scan_text` output on every existing test file; the existing affected duplicate-guard tests against the candidate; unchanged `repo_guards.sh`. Retain phase ordering (owned definitions, direct hits, then assignment hits), BFS order within each phase, and first-assignment semantics.
- No test deselection, weakened checks or tolerances, changed corpus/allowlists, cross-file or cross-run result cache, edits to other cards’ files or delivered packages. No full-suite or DCC run. Nothing is applied automatically; any replacement of production code requires a normal reviewed PR.

Readiness 2026-11-20 02:43: biggest gaps are cold Ground/UCX/MAF/Flora and cold package/entry tokens (#1315/#1622/#1608/#1614), then delivery gates. Those are owned, as are G22 atlas (#1649), polygon training (#1619), Max (#1105) and idle suite-wall (#1615). Verifier #768 lacks an independently calibrated accept/reject corpus. PDF binding R2 had only a 2.28% gain on full NTR albums (#8). This experiment addresses recurring guard cost without taking over #1708 or claiming movement in a readiness score.

## Round 1 — reject (OBSERVE)

The candidate groups AST nodes by type once and then evaluates the unchanged predicates in their original phases. Both variants ran in CPython 3.14.7. These are scan times, not `repo_guards.sh` times or idle-host claims.

| Pair | Baseline (s) | Candidate (s) |
|---|---:|---:|
| 1 | 13.495 | 14.453 |
| 2 | 14.372 | 13.372 |
| 3 | 14.614 | 15.079 |
| **Median** | **14.372** | **14.453** |

C/B = **1.0056**, versus the keep threshold of 0.80. Only one pair was faster. The full CLI output and exit code matched in all six runs; ordered `scan_text` results matched on 764 test files. The candidate did not demonstrate a useful speedup; this is not evidence of a reproducible slowdown. No production code or delivered work changed.

- Affected tests: `uv run python tmp/ar10_udim.py --pytest -q tests/test_duplicate_guard_count_1396.py --basetemp C:/x/ar_t_ef1fcf20/pytest` — 28 passed. In-process tests use the trial; the existing fresh-process smoke uses the untouched scanner on disk.
- `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, `repo_guards: GREEN` on the unchanged scanner and frozen contract commit. Full suite: not run.
- Raw receipt: `C:/x/ar_t_ef1fcf20/udim.json`, SHA-256 `214fa34f5daaccf29313e6d6be89139b7eea191bd960b2a7b7bf8d851cd873b0`. Restore the archived adapter to `tmp/ar10_udim.py` on the frozen contract commit `a99799ac` and use a fresh output filename to reproduce.
