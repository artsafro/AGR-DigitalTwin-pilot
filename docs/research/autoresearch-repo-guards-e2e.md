# Autoresearch: end-to-end `repo_guards.sh` wall time (standing #7, t_559cc438)

## Кратко для Артёма

Проверка `repo_guards.sh`, которую каждая карточка запускает дважды, ускорилась бы почти вдвое:
медиана **186,1 → 98,4 с (C/B 0,529, −47 %)**. Для этого нужно внедрить уже доказанные приёмы R1+R4+R5
в `duplicate_guard.py`. Все 8 прогонов GREEN, во всех 542 passed, вывод сканера совпадает байт-в-байт.
Мутация проверку паритета ломает, то есть проверка работает. Режим OBSERVE: в `tools/` ничего не изменено.
Внедрение — отдельный PR с ревью; это моё предложение, решение за вами.

## Why this target

`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` runs on EVERY card twice (implementer +
reviewer, rule 68 addendum). Observed on this PC at `b9a3cbbf`: 182 s = duplicate_guard CLI scan 52 s +
7 guard test files under `-n 4` 130 s, where five tests each run a full real-repo scan (85 / 52 / 50 / 49 / 48 s).
Standing #1 (R1 walk memo, scan C/B 0.449) and #3 (R4 / R5 lazy scopes / int names, ~11-13 % on top) proved
scan-level keepers in-process, but nobody measured what they do to the number every card pays, and the
fresh-process CLI tests were never covered (they spawn an unpatched interpreter). No open card or issue owns
this (kanban board: no non-done task on guard / duplicate / suite / autoresearch; #1486, #1688 closed;
`tools/architecture/` free).

Considered and dropped (backlog): `get_cdrawings` in `album.reader._primitives` (standing #6 next target) -
unprofiled `_primitives` is 0.97 s total on the three #1321 sheets and `get_drawings` -> `get_cdrawings` saves
<= 0.15 s of a ~6.8 s baseline, so the 0.80 bar is unreachable by construction. Suite wall (#1615), cold-run
tokens (#1608 / #1315), floors quality (#1619), G22 atlas (#1649), DCC stage times (#1105, heavy runs paused),
verifier #768 (no independent accept/reject calibration set): owned or not measurable now.

## Frozen contract (written before any candidate run)

- Base: `origin/main` `b9a3cbbf`. Two scratch detached worktrees of that commit outside this branch:
  `C:/x/ar_t_559cc438/wtB` (unchanged) and `C:/x/ar_t_559cc438/wtC` (candidate). Harness copied to
  `C:/x/ar_t_559cc438/harness/` (`candidates.py` from `autoresearch-repo-guards-harness/`, unchanged).
- Candidate injection (wtC only): the blank line directly above `if __name__ == "__main__":` in
  `tools/architecture/duplicate_guard.py` is replaced by ONE line that applies the named harness candidates
  to `sys.modules[__name__]`. No line numbers shift; the CLI run as `__main__`, in-process imports and the
  fresh-process CLI tests all get the candidate. Nothing in `src/`, `tools/` or tests of this branch changes.
- Metric: wall seconds of `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` started in the
  worktree (whole script: CLI scan + guard tests, `uv run` start-up included - that is what a card pays).
  Driver: `docs/research/autoresearch-repo-guards-e2e-harness/e2e_bench.py`.
- Samples: one untimed warm-up per worktree (venv creation), then 3 pairs B,C / C,B / B,C; median of 3 per
  variant. Report all six times; loaded workstation, not an idle slot.
- Keep threshold: median C <= 0.80 x median B, every pair faster, every run `repo_guards: GREEN` with the
  same pytest pass count (no skips/deselects added).
- Parity (untimed, once per round): `uv run python tools/architecture/duplicate_guard.py --json --table`
  stdout byte-identical between wtB and wtC; mutation witness: the same comparison with harness candidate
  `m0_drop_calls` injected must differ. In-process JSON parity of R1 / R4 / R5 is already in #1 / #3.
- Rounds: R1 = `r1_walk_memo,r4_lazy_scopes,r5_lazy_int_names` (the bundle the adoption card would land).
  Optional R2 only if R1 is recorded and time remains: declared here, not invented after seeing R1 -
  none. Stop: R1 recorded, or first parity failure, or 75 min of measurement.
- Forbidden: deselecting / skipping tests, changing `-n`, editing `repo_guards.sh`, weakening any guard,
  touching delivered packages, other cards' files, or this branch's production code. Calibration (card rule 3)
  does not apply: wall time with exact output parity, not a quality score.
- OBSERVE: a keeper is a proposal for a separate production PR on `duplicate_guard.py` (R1 + R4 + R5 as real
  code, this bench + `bench.py --baseline` as parity proof), never auto-applied.

## Round log

Attempt 0 (invalid, not a measurement): Python's `bash` resolved to WSL (`System32\bash.exe`), every run
exited 1 in ~0.1 s. The driver now resolves git-bash from the git install and refuses to time a non-GREEN
warm-up (commits after the contract; metric, threshold and samples unchanged). Receipt kept as
`C:/x/ar_t_559cc438/r1_invalid_wsl_bash.json`.

Parity (untimed, before timing): `duplicate_guard.py --json --table` stdout wtB == wtC (rc 0/0, SHA-256
`f256cf73…effe94` both). Mutation witness `m0_drop_calls` in wtC: rc 1, SHA `ba2d6324…`, differs -> the
comparison catches a broken walk. wtC re-injected with R1 afterwards (`git diff --stat`: 1 line in 1 file).

### R1 = r1_walk_memo + r4_lazy_scopes + r5_lazy_int_names — KEEP (OBSERVE proposal)

| Run (execution order) | B, s | C, s | GREEN / passed |
|---|---:|---:|---|
| warm-up (untimed for the metric) | 174.304 | 83.358 | yes / 542 both |
| pair 1 B,C | 174.841 | 92.834 | yes / 542 |
| pair 2 C,B | 186.090 | 98.443 | yes / 542 |
| pair 3 B,C | 196.344 | 103.635 | yes / 542 |
| **median** | **186.090** | **98.443** | ratio **0.529** -> keep |

Every pair faster, every run `repo_guards: GREEN` with 542 passed, no problem lines. In wtC the five
full-scan tests (in-process AND fresh-process CLI) ran with the candidate, so the 542 green are also a parity
run of the candidate through the real guard tests. Loaded workstation (B drifted 175 -> 196 s across the run),
not an idle slot; the ratio is within-run. Stop rule reached (R1 recorded; no R2 declared).

Receipt: `C:/x/ar_t_559cc438/r1.json` SHA-256 `17125639630e1ce1f2ba2427bd2fe2d8c8d5521e0d5da4b91f9282eb46523702`;
both worktrees at `b9a3cbbff0c855e70cd1ddc13109a191ee2c2513`; `candidates.py` SHA-256 `1324b794…8473`
(= `autoresearch-repo-guards-harness/candidates.py`). Reproduce: `python
docs/research/autoresearch-repo-guards-e2e-harness/e2e_bench.py setup --base <sha> --candidate
r1_walk_memo,r4_lazy_scopes,r5_lazy_int_names`, then `parity`, `parity --mutant m0_drop_calls`, `setup` again,
`run --out <new path>` (~25 min on this PC).

## What adoption would change (proposal, not applied)

One production PR on `tools/architecture/duplicate_guard.py`, written as real code, not the monkeypatch:
- R1: a per-file memo of `ast.walk` (BFS order identical to `ast.walk`, keyed by node identity, cleared after
  each file's `_findings`);
- R4: `_scopes(tree)` built on the first scope lookup of a hit;
- R5: `_int_names(tree)` built on the first `consts.get`.
Parity proof for that PR: `autoresearch-repo-guards-harness/bench.py --baseline` (in-process JSON) + this
bench with an empty candidate list against the patched tree (expected C/B ~0.53) + the 7 guard test files.
Expected effect: every card's `repo_guards.sh` ~3 min -> ~1.6 min, twice per card.
