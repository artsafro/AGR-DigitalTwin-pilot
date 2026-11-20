# Autoresearch: Blender exit-code guard full-repo scan time (standing #11, t_95ce9e1f)

## Кратко для Артёма

Проверка «каждый фоновый запуск Blender передаёт `--python-exit-code`» сканирует весь репозиторий. Она входит в
`repo_guards.sh` (каждая карточка, дважды) и в полный suite. Один проход по дереву вместо трёх вложенных сократил
скан с **15,32 до 10,31 с (C/B 0,673, −33 %)**. Все 5 пар быстрее, результат совпадает точно: реальный репозиторий,
каждый из 1814 `.py` и 760 `.md` и 3000 сгенерированных программ. Все 37 тестов guard проходят с подменой.
Мутант, который не видит вложенные списки, ловится только генератором (1069 расхождений). Существующие 37 тестов
его пропускают, поэтому в PR внедрения нужен регрессионный тест на вложенный литерал. Режим OBSERVE: в `tests/`
ничего не изменено. Внедрение — отдельный PR с ревью, решение за вами.

## Why this target

`tests/test_blender_exit_code_guard.py::test_repository_headless_blender_calls_pass_exit_code` is one of the
7 guard files of `repo_guards.sh` (every card, twice) and of every full suite. Decomposition on open PR #1708
head `b96f0223` (R1+R4+R5 already in `duplicate_guard.py`), loaded PC: guard tests under `-n 4` 63.8 s wall,
542 passed; slowest calls 22.3 s (MAF seat bench), 22.0 / 19.1 / 18.4 / 17.3 / 16.7 s (duplicate_guard real-repo
scans) and **19.4 s this Blender guard**. In-process profile of `repository_violations()` (2590 tracked files):
`.py` 1814 files 14.6 s, `.md` 760 files 0.3 s, `.sh/.ps1` 0.01 s; `ast.parse` alone ~5.3 s, the rest is
three `ast.walk` passes per file: bindings, the main walk, and a fresh `_string_constants` walk of EVERY
`List`/`Tuple` subtree (nested literals are re-walked once per enclosing literal).

Owner check: no open PR touches `tests/test_blender_exit_code_guard.py` (#1706, #1708, #1709 checked); no other
module imports its helpers. Not taken: next targets of standing #10 - `call_chains.edges` share needs #1708
merged; scan reuse inside pytest workers would cache in `duplicate_guard.py`, which #1706 and #1708 both edit
(hotspot). Cold Ground/UCX/MAF/Flora and tokens (#1315 / #1608 / #1614), floors (#1619), G22 (#1649), full-suite
wall (#1615), Max stage times (#1105), verifier #768 (no independent accept/reject calibration): owned or not
measurable now.

## Frozen contract (written before any candidate code)

- Base: `b96f0223c73860b2e568a26064980c849c2cd26e` (#1708 head), scratch detached worktree
  `C:/x/ar_t_95ce9e1f/wtB`. The baseline module is loaded from `git show <base>:tests/test_blender_exit_code_guard.py`.
- Metric: wall seconds (`time.perf_counter`) of one `repository_violations()` call on the real tracked tree of
  wtB, in-process, default GC. Driver: `docs/research/autoresearch-blender-guard-scan-harness/bench.py`.
- Samples: one untimed warm-up per variant (file cache), then 5 alternating pairs B,C / C,B / B,C / C,B / B,C in
  ONE process; median of 5 per variant (>= the card's median of 3). Loaded workstation, ratio is within-run.
- Keep threshold: median C <= 0.80 x median B AND at least 4 of 5 pairs faster AND exact parity below.
- Parity (all must hold, else the round is discarded regardless of time):
  1. `repository_violations()` list identical (order included) B vs C on the real tree;
  2. per-file `_scan_py_source` output identical on every tracked `.py` file and every python fence of every
     tracked `.md` file;
  3. generated differential corpus (seeded, >= 3000 programs): nested list/tuple/set/dict literals, implicit
     string concatenation, f-strings, calls via `subprocess` / `os` / aliases / `from ... import` / star import,
     keyword `args`/`cmd`/`command`, flags at random depth; outputs identical;
  4. all 37 tests of the guard file pass with the candidate substituted in the module;
  5. mutation witness: a candidate that ignores nested literals (only direct children) must FAIL parity 3.
- Candidates (declared now, nothing invented after seeing numbers):
  - R1 `one_walk`: a single BFS over the tree (same order as `ast.walk`) records parents, import bindings, and
    candidate `List`/`Tuple`/`Call` nodes; `--background` / `--python-exit-code` presence for every literal
    is aggregated bottom-up from string constants instead of re-walking each subtree; violations are emitted
    in BFS order after the walk (bindings are file-global in the baseline, so exec calls are decided after all
    imports are seen - same as baseline).
  - R2: none declared. A raw-text prefilter (skip files without `background` in the text) would be faster but
    is defeated by implicit concatenation (`"--back" "ground"`) or escapes, i.e. it weakens the guard:
    forbidden, not a candidate.
- Stop: R1 recorded, or first parity failure after 3 repair attempts, or 60 min of measurement.
- Forbidden: skipping/deselecting tests, raw-text prefilters that change what is scanned, narrowing the file
  inventory, editing `repo_guards.sh`, `duplicate_guard.py` (#1706/#1708), delivered packages or other cards'
  files. Calibration (card rule 3) does not apply: wall time with exact output parity, not a quality score.
- OBSERVE: nothing in `tests/` or `src/` of this branch changes. A keeper is a proposal for a separate PR that
  rewrites `_scan_py_source` as real code with this bench as parity proof.

## Round log

Harness: `docs/research/autoresearch-blender-guard-scan-harness/` (`bench.py`, `candidates.py`,
`pytest_candidate.py`, `receipts/`), committed after the contract; metric, threshold and samples unchanged.

### Parity (untimed, before timing)

| Check | R1 `r1_one_walk` | Mutant `m0_direct_children_only` |
|---|---|---|
| 1. `repository_violations()` B == C | yes (0 == 0) | yes (0 == 0) |
| 2. per file: 1814 `.py` + 760 `.md` | all equal | all equal |
| 3. generated corpus seed 1111, 3000 programs (1882 with violations) | 0 diffs | **1069 diffs -> caught** |
| 4. 37 guard tests with substitution | 37 passed | 37 passed (**not caught**) |

The real tree has no violations, so checks 1-2 only prove "no new false positives"; check 3 is the one that
catches a broken nested walk. Check 4 shows a test gap in the guard file itself (side finding below).

### R1 = `r1_one_walk` — KEEP (OBSERVE proposal)

| Run (execution order) | B, s | C, s |
|---|---:|---:|
| pair 1 B,C | 14.896 | 10.405 |
| pair 2 C,B | 15.322 | 9.291 |
| pair 3 B,C | 16.589 | 10.310 |
| pair 4 C,B | 17.635 | 10.335 |
| pair 5 B,C | 14.716 | 9.924 |
| **median** | **15.322** | **10.310** |

Ratio **0.673** (<= 0.80), 5/5 pairs faster, every timed run returned the warm-up's violation list. Loaded
workstation, ratio within one process. Stop rule reached (R1 recorded, no R2 declared).

Receipts: `receipts/r1.json` SHA-256 `c07a28ce73f70d886acfacd5fe010266e722262584c64a83734c8b46d0b2c323`,
`receipts/parity_r1.json`, `receipts/parity_m0.json`; base `b96f0223`, guard file SHA-256 `a5f05c9f…0d50360`,
`candidates.py` SHA-256 `9448681205c3cb210b582f602b67efe07c7e3dd70a3d0f49c49169d6b3272067`.
Reproduce (in a detached worktree of the base):
`uv run python <harness>/bench.py parity --root . --candidate r1_one_walk` (and `--mutant m0_direct_children_only`,
expected exit 1), `BLENDER_GUARD_CANDIDATE=r1_one_walk PYTHONPATH=<harness> uv run pytest -q -p pytest_candidate
tests/test_blender_exit_code_guard.py`, then `bench.py run --root . --candidate r1_one_walk --out <new path>` (~4 min).

## What adoption would change (proposal, not applied)

One PR on `tests/test_blender_exit_code_guard.py`: `_scan_py_source` written as one BFS in `ast.walk` order that
collects import bindings, `List`/`Tuple` and `Call` nodes, and ORs `--background` / `--python-exit-code` bits from
string constants up the parent chain (stops when the bit is already set, so O(nodes)); violations sorted back into
BFS order; exec calls decided after the walk with the same file-global bindings. Plus a regression test: a nested
literal (`[["blender", "--background"], "x"]` and a flag only in the inner list) must keep its current verdicts -
the mutant above passes all 37 existing tests. Parity proof: this bench (checks 1-4, mutant must fail).
Expected effect: the guard's real-repo test ~19 s -> ~13 s under `-n 4`; it is one of the longest calls of
`repo_guards.sh`, whose wall is set by the slowest xdist worker, so the e2e gain must be measured after adoption.

## Side finding (not fixed here)

`tests/test_blender_exit_code_guard.py` has no test that a `--background` string nested inside an inner literal
is attributed to every enclosing literal; a walk that looks only at direct children passes all 37 tests.
