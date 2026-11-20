# Autoresearch: adopt R1+R4+R5 in `duplicate_guard.py`, measured on `repo_guards.sh` (standing #9, t_a334c185)

## Кратко для Артёма

(заполняется после замера)

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

(filled after measurement)
