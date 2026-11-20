# Autoresearch: UDIM AST dispatch (standing #10, t_ef1fcf20)

## Кратко для Артёма

Проверяем, ускорит ли группировка узлов AST полный скан `duplicate_guard` без изменений в его выводе. Это OBSERVE: проверяем временный адаптер, а не меняем сканер или поставки.

## Frozen contract

- One metric: median wall seconds of three full `duplicate_guard.main(--root <worktree> --json --table)` calls per variant, alternating B/C in one process via `autoresearch-repo-guards-harness/bench.py`. Fixed source snapshot `29a12bba4ec8944649f94d13bef7ad852b58a522`. B uses existing R1+R4+R5 harness transforms in memory; C adds ordered AST dispatch for `_udim_hits` only. Neither pulls in changes from open PR #1708.
- From the worktree: `uv run python tmp/ar10_udim.py --rounds 3 --baseline r1_walk_memo,r4_lazy_scopes,r5_lazy_int_names --candidate udim_dispatch --out C:/x/ar_t_ef1fcf20/udim.json`. The adapter registers one process-local prototype in the existing bench; it must not modify that bench on disk. Keep only if C/B ≤ 0.80, all paired C faster, and parity/tests/guards pass. Stop after one round, first parity failure, or eight minutes of measurement, whichever comes first. Incomplete runs are not evidence of improvement.
- Parity: complete CLI output and exit code across all six samples; exact ordered `scan_text` output on every existing test file; the existing affected duplicate-guard tests against the candidate; unchanged `repo_guards.sh`. Retain phase ordering (owned definitions, direct hits, then assignment hits), BFS order within each phase, and first-assignment semantics.
- No test deselection, weakened checks or tolerances, changed corpus/allowlists, cross-file or cross-run result cache, edits to other cards’ files or delivered packages. No full-suite or DCC run. Nothing is applied automatically; any replacement of production code requires a normal reviewed PR.

Readiness 2026-11-20 02:43: biggest gaps are cold Ground/UCX/MAF/Flora and cold package/entry tokens (#1315/#1622/#1608/#1614), then delivery gates. Those are owned, as are G22 atlas (#1649), polygon training (#1619), Max (#1105) and idle suite-wall (#1615). Verifier #768 lacks an independently calibrated accept/reject corpus. PDF binding R2 had only a 2.28% gain on full NTR albums (#8). This experiment addresses recurring guard cost without taking over #1708 or claiming movement in a readiness score.
