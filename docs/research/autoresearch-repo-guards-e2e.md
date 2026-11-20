# Autoresearch: end-to-end `repo_guards.sh` wall time (standing #7, t_559cc438)

## Кратко для Артёма

(заполняется после замера — см. «Round log» ниже)

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

(filled after measurement)
