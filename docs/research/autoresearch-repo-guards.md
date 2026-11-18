# Autoresearch: duplicate_guard scan time inside repo_guards (standing card #1, t_e730ebd2)

## Кратко для Артёма

Цель: время полного скана `duplicate_guard` - он идёт ~6 раз в каждом `repo_guards.sh` (≈3 мин на карточку,
дважды: исполнитель и ревьюер). Режим OBSERVE: файл `duplicate_guard.py` не правился (им занята #1486).
R1 (мемоизация обхода AST) - медиана 44,3 -> 19,9 с (−55 %), вывод совпадает байт-в-байт, 287 тестов guard
зелёные с подменой, мутационная проверка паритета срабатывает. Предложение - отдельной карточкой после #1486.
R2/R3 отложены на ночь (ПК перегружен).

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

Receipts (outside git, rule 57): `C:/x/ar_t_e730ebd2/r1.json`, `C:/x/ar_t_e730ebd2/m0.json`.
PC was loaded by other workers during all rounds (orchestrator note 2026-11-18: overloaded, no heavy runs
before 00:30); alternation B/C in one process keeps the comparison fair, absolute seconds are not idle numbers.

| Round | Candidate | median B, s | median C, s | C/B | parity | verdict |
|---|---|---|---|---|---|---|
| guard check | `m0_drop_calls` (mutation: walk skips `ast.Call`) | 44.81 (1 run) | 41.15 | 0.92 | **False** (rc 0 -> 1) | parity guard catches it |
| R1 | `r1_walk_memo` | 44.26 (39.77 / 44.26 / 45.84) | 19.86 (16.11 / 21.06 / 19.86) | **0.449** | True (6/6 runs + 757 `tests/*.py` scan_text) | **KEEP (observe)** |

R1 extra parity: `tests/test_architecture_map_1359.py` + `tests/test_duplicate_status_1424.py` with the
candidate injected (`-p ar_dg_inject`, serial): **287 passed**. In-process scans got faster inside the tests
(`test_guard_red_on_synthetic_copy_inside_the_real_repo_tree` 73 -> 24 s, `test_guard_green_on_repo_with_allowlist`
41 -> 16 s, `test_cli_exit_1_on_a_new_live_bypass` 41 -> 15 s); fresh-process CLI tests run the unpatched file.

R2 / R3 not run: the orchestrator forbade heavy runs on the overloaded PC; stop reason = operator load
restriction after R1 (R1 alone is a 55 % reduction, the 60 % target is not reached). Queued for the night
window as next targets (backlog): R2 `call_chains.edges` uses the same per-node `ast.walk` (16 s); R3 one parse
per file shared by `scan` and `call_chains` (1 603 opens / 25 s, many files read twice).

## What R1 would change (proposal, not applied - #1486 / t_ecc3dde7 owns the file now)

In `tools/architecture/duplicate_guard.py`: a module-level memoised walk with the exact `ast.walk` BFS order,
cleared after every file's `_findings`, used by all rule checks (`candidates.py::WalkCache`, `r1_walk_memo`):

```python
_WALK = {}

def _walk(node):   # == list(ast.walk(node)), memoised per tree; the memo holds the node so a reused id never hits
    hit = _WALK.get(id(node))
    if hit is not None and hit[0] is node:
        return hit[1]
    order, i = [node], 0
    while i < len(order):
        order.extend(ast.iter_child_nodes(order[i]))
        i += 1
    order = tuple(order)
    _WALK[id(node)] = (node, order)
    return order
# every `ast.walk(` in the rule checks -> `_walk(`; `_findings` clears `_WALK` in a `finally`.
```

Rules, scopes, allowlist and outputs are unchanged; follow-up card after #1486 merges, normal PR + review,
with the same bench as its parity proof. Expected effect on `repo_guards.sh`: the CLI scan (~44 -> ~20 s on a
loaded PC) and three in-process guard tests (~155 -> ~55 s) - roughly 2 of the ~3 min per card run.

## Итог

R1 (мемоизация `ast.walk`) сокращает полный скан `duplicate_guard` в 2,2 раза (медиана 44,3 -> 19,9 с,
C/B 0,449) при полном совпадении вывода; мутационная проверка паритета ловит поломку. Файл не правился
(им занята карточка #1486) - изменение оформлено как предложение для отдельной карточки после #1486.

## Standing #2 (`t_05244ff2`): frozen contract

Same full-scan metric and unchanged `bench.py` on `origin/main` `c781068a`. R2 tests only
memoizing identical dotted-module lookups within one `call_chains.load_live` (including misses).
`edges` already walks each parsed file once; R1 is not enabled in either variant. No production
files change. #1486 owns guard correctness, #1615 owns full-suite wall time; #1677 is merged.
Readiness `2026-11-18_1001.json`: cold-site readiness blockers belong to #1315/#1608;
polygon floors to #1619, G22 atlas to #1649. This targets per-card verification overhead instead.

- Command: `uv run python docs/research/autoresearch-repo-guards-harness/bench.py --rounds 3 --candidate r2_module_memo --out C:/x/ar_t_05244ff2/r2.json`. Compare median of three full scans for each variant, alternating B/C; not an idle-machine claim.
- Keep as proposal only if C/B <= 0.80 and parity passes: all six clean CLI exits and byte-identical output, all `scan_text` corpus findings, plus complete roots and shortest chains equality on the repo. The existing `tests/test_duplicate_status_1424.py` must pass with the candidate injected, including syntax-error reporting; fresh subprocesses still use unmodified production code.
- Candidate must not share state across graph loads or roots. No deselects, skipped files or rules, weaker checks/tolerances, edited delivered packages, or other cards' files. Timing is not a quality score; no model calibration applies.
- Stop after one candidate round, at C/B <= 0.80 with parity, or 10 minutes from launch, whichever comes first. No full suite or DCC. In OBSERVE only record what would change; any adoption goes through a reviewed PR, not an automatic change to production or deliveries.
