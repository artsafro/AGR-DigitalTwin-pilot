# Autoresearch: adopt R1+R4+R5 in `duplicate_guard.py`, measured on `repo_guards.sh` (standing #9, t_a334c185)

## Кратко для Артёма

Приёмы R1+R4+R5 из стенда #7 теперь внедрены в `tools/architecture/duplicate_guard.py` как обычный код, без подмены.
Проверка `repo_guards.sh` (каждая карточка запускает её дважды) ускорилась: медиана **199,8 → 103,8 с (C/B 0,519, −48 %)**.
Быстрее оказались все три пары. Все 8 прогонов GREEN, в каждом 542 passed. Вывод сканера совпадает со старым модулем
байт-в-байт: полный вывод CLI и `scan_text` для всех 1812 `*.py` репозитория, 339 находок в 153 файлах. Две
намеренные поломки проверка паритета ловит: 125 и 64 файла с расхождением. Затронутые тесты: 1021 passed, плюс 3 новых
регрессионных. Правила guard'а не менялись, ни одного allowlist-исключения не добавлено. Слияние — после ревью и вашего решения.

## Why this target

Standing #7 (PR #1707, `autoresearch-repo-guards-e2e.md`) measured `repo_guards.sh` - run twice on EVERY card -
at median 186.1 -> 98.4 s (C/B 0.529) with R1 (per-file `ast.walk` memo) + R4 (lazy `_scopes`) + R5 (lazy
`_int_names`) injected as a monkeypatch. Its first next target: land them as real code in a normal PR. Nobody owns
it: kanban board agr-pilot has no non-done card on duplicate_guard / repo_guards; #1486 and #1688 are CLOSED; no
open PR touches `tools/architecture/` (open: #1706, #1704, #1703, #1692, #1661).

Considered and not taken (backlog): `_span_gap` share on full NTR albums (standing #8 next target; R2 gave only
-2.28 % on 13 pages, so the binding line is exhausted for now), cold Ground/UCX/MAF/Flora and entry tokens
(#1315/#1608, card t_0b0c6be1), floors quality (#1619), G22 atlas (#1649), suite wall (#1615), Max stage times
(#1105, heavy runs paused), verifier #768 (no independent accept/reject calibration set).

## Frozen contract (written before the code change)

- Base B: `origin/main` `69cf3a7c` in a scratch detached worktree `C:/x/ar_t_a334c185/wtB` (unchanged).
  Candidate C: this branch's committed head in `C:/x/ar_t_a334c185/wtC` (detached at the candidate commit; no
  injection). The only production file that differs is `tools/architecture/duplicate_guard.py`.
- Change = R1 + R4 + R5 written as real code, scoped to the scan (`_findings` and the check functions it calls):
  - R1: `_walk(node)` - BFS identical to `ast.walk` (same nodes, same order), memoised per node identity; the memo
    is cleared in `_findings`' `finally`, so it never outlives one tree. Walks outside the scan (`calls_owner`,
    `_owner_names`, `_scope_node`, loaders) stay on plain `ast.walk`.
  - R4: `_findings` builds `_scopes(tree)` on the first hit only.
  - R5: `_udim_hits` builds `_int_names(tree)` on the first Name lookup only.
- Metric: wall seconds of `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` in each worktree, driver
  `docs/research/autoresearch-repo-guards-e2e-harness/e2e_bench.py` (`--work C:/x/ar_t_a334c185`, `setup --c-ref`).
  One untimed warm-up per worktree, then pairs B,C / C,B / B,C; median of 3 per variant; all six times reported.
- Keep threshold: median C <= 0.80 x median B, every pair faster, every run `repo_guards: GREEN` with the same
  pytest pass count.
- Parity (untimed, before timing):
  1. `duplicate_guard.py --json --table` stdout byte-identical between wtB and wtC (e2e `parity`);
  2. `adopt_parity.py`: old module (`git show 69cf3a7c:tools/architecture/duplicate_guard.py`) vs new module,
     in one process: `main(["--json","--table"])` stdout + rc, and `scan_text` (findings or exception type+text)
     of EVERY tracked `*.py` in the repo;
  3. mutation witness: the same comparison with `_scopes` answering `<module>` for every node (candidate
     `m1_scope_module` on the new module) must differ; a second witness with `_walk` dropping `ast.Call` nodes must
     differ (proves the new `_walk` is on the scan path).
- Stop: R1 recorded, first parity failure, or 75 min of measurement. One round only (no tuning after seeing numbers).
- Forbidden: deselecting / skipping tests, changing `-n`, editing `repo_guards.sh`, weakening any guard rule or
  allowlist, touching delivered packages or other cards' files. Calibration (card rule 3) does not apply: wall time
  with exact output parity, not a quality score.
- OBSERVE: the code change ships only through this PR + dt-reviewer review + Artem's merge; nothing is applied to
  delivered work.

## Round log

Parity (untimed, before timing; candidate `13e737a7`):
- `adopt_parity.py --base 69cf3a7c`: 1812 tracked `*.py`, 153 with findings, 339 findings, 0 raising; `main` rc 0/0,
  stdout SHA-256 `f256cf73…effe94` old == new (= standing #7's value); `scan_text` diff files 0 -> identical.
- Mutants on the new module: `scope_module` main rc 1, SHA `dec135dd…`, 125 files differ; `walk_drop_calls` main
  rc 1, SHA `ba2d6324…` (= #7's `m0_drop_calls` witness), 64 files differ -> both caught, `_walk` is on the path.
- e2e `parity`: `duplicate_guard.py --json --table` wtB == wtC, rc 0/0, SHA `f256cf73…effe94` both.

### R1 = R1+R4+R5 as real code — KEEP

| Run (execution order) | B, s | C, s | GREEN / passed |
|---|---:|---:|---|
| warm-up (untimed for the metric) | 179.753 | 114.325 | yes / 542 both |
| pair 1 B,C | 199.778 | 97.335 | yes / 542 |
| pair 2 C,B | 215.918 | 105.400 | yes / 542 |
| pair 3 B,C | 199.756 | 103.767 | yes / 542 |
| **median** | **199.778** | **103.767** | ratio **0.519** -> keep |

Every pair faster, every run GREEN with 542 passed, no problem lines. Loaded workstation, not an idle slot; the
ratio is within-run and matches #7's monkeypatch measurement (0.529), so scoping the memo to the scan (plain
`ast.walk` elsewhere) lost nothing. Stop rule reached (R1 recorded).

Receipts (outside git, `C:/x/ar_t_a334c185/`): `r1.json` SHA-256 `ff85e77ad0de0293…`, `parity.json` `285f915a09dd4267…`,
`parity_m_scope.json` `23917d1ef46a5154…`, `parity_m_walk.json` `b160696dde92c3a1…`; wtB at `69cf3a7c`, wtC at
`13e737a7`. Reproduce: `python docs/research/autoresearch-repo-guards-e2e-harness/e2e_bench.py --work <dir> setup
--base <main> --c-ref <branch>`, then `parity`, `run --out <new path>` (~27 min on this PC).

Regression test `tests/test_duplicate_guard_walk_memo.py` (3 tests): `_walk` == `ast.walk` order on real files,
memo empty after a scan and after a raising check, lazy scopes / int names still give `Packer.tile` on a
named-constant `BASE + int(u) + 10 * int(v)`; 3 failed on `69cf3a7c`'s module, 3 passed after.
