# Autoresearch: duplicate_guard scan time inside repo_guards (standing card #1, t_e730ebd2)

## Кратко для Артёма

(заполняется после раундов, см. «Итог» ниже)

## Why this target

`repo_guards.sh` runs on every card twice (implementer + reviewer, rule 68 addendum). Measured at
`acd287e1` on 2026-11-18 (loaded PC, 32 logical CPUs): `duplicate_guard.py` 52.6 s, guard tests 134 s
(541 passed, `-n 4`). Five guard tests each re-run the full-repo scan in a fresh process or in-process
(`test_guard_red_on_synthetic_copy_inside_the_real_repo_tree` 73 s, `test_guard_green_on_repo_with_allowlist`
41 s, `test_guard_fresh_process_cli` 40 s, `test_repo_guard_cli_fresh_process_exit_0_and_prints_the_russian_table`
43 s, `test_cli_exit_1_on_a_new_live_bypass` 41 s). So the per-card guard cost is about six full scans.
cProfile of one CLI run (206 s under the profiler): 40.6 M `ast.walk` steps (every one of the 9 rules
re-walks every tree; `_findings` 153 s of 185 s in `scan`), 25 s in 1 603 file opens, `call_chains.load_live` 16 s.

Not owned elsewhere: #1615 / t_82b1bc95 owns full-suite wall time (blocked on a drained window, no code
in `tools/architecture/`); #1608 owns cold entry tokens; #1486 / t_ecc3dde7 is RUNNING on the correctness of
`tools/architecture/duplicate_guard.py::_owner_names`. Therefore this card does **not edit
`duplicate_guard.py`** (OBSERVE): candidates are applied in-process by the harness and recorded as a patch.

## Frozen contract

- Base: `origin/main` `acd287e1` (pilot). Harness: `docs/research/autoresearch-repo-guards-harness/bench.py`.
- Metric (one number): wall seconds of one in-process `duplicate_guard.main(["--json", "--table"])` on the repo
  root (= the full CLI scan that `repo_guards.sh` and three guard tests run, plus the parity printout),
  interpreter start excluded. Command: `uv run python docs/research/autoresearch-repo-guards-harness/bench.py
  --rounds 3 --candidate <name> --out C:/x/ar_t_e730ebd2/<name>.json`.
  Median of 3 per variant; baseline and candidate alternate inside ONE process (B, C, B, C, B, C) so PC
  load hits both equally.
- Keep threshold: candidate median <= 0.80 x baseline median (>= 20 % gain), with parity.
- Parity proof (every run, fail-closed): identical exit code and identical stdout of
  `main(["--json", "--table"])` (findings, stale rows, #1424 status problems, Russian table), plus identical
  `scan_text` findings on every `*.py` under `tests/` (synthetic copies the guard tests feed it) and the guard
  tests green with the candidate injected (`AR_DG_CANDIDATE=1`, see harness `conftest`-free injection below).
- Stop rule: 3 candidate rounds, or 2 h of card time, or >= 60 % reduction - whichever first.
- Forbidden: deselecting / skipping / merging guard tests, removing a rule or a scope, changing allowlist rows,
  `contexts.yaml` or any context map, weakening any check, caching results across processes or across commits
  (a stale cache could hide a new copy), editing `duplicate_guard.py` or other cards' files, editing delivered
  packages. Calibration (rule 3 of the card) does not apply: a wall-time metric, not a quality score; parity
  replaces it.
- OBSERVE: the harness only records what it would change (`candidate.patch` + round log). The retained change
  becomes a follow-up card on `duplicate_guard.py` after #1486 merges, through a normal PR + review.

## Rounds

(appended by the rounds below)
