# Autoresearch: Blender exit-code guard full-repo scan time (standing #11, t_95ce9e1f)

## Кратко для Артёма

(заполняется после замера)

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

(filled after runs)
