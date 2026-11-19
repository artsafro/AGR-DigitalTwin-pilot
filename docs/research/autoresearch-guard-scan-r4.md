# Autoresearch: duplicate_guard scan time on top of R1 (standing card #3, t_b1bb763f)

## Кратко для Артёма

(заполняется после замеров, см. «Итог»)

## Why this target

Continues `docs/research/autoresearch-repo-guards.md` (standing #1, same harness). The full `duplicate_guard`
scan runs about six times per `repo_guards.sh` (CLI + in-process and fresh-process guard tests), on every card,
twice (implementer + reviewer). R1 (memoised `ast.walk`, 0.449) is proposed but not applied; the scan is still
the largest single item of `repo_guards.sh`.

Segment probe at `fa6330a3` (2026-11-19 07:00, one process, no profiler): `main` 53.1 s wall / 52.3 s CPU;
`scan_for` 45.1 s, of which `_findings` 39.9 s; `call_chains.load_live` 6.5 s; `ast.parse` 1 603 calls on
927 files = 6.9 s in total.

- **R3 (one parse shared by scan and call_chains) is dropped without a run**: all parsing costs 6.9 s of
  53.1 s; even removing every second parse saves <= ~3 s (< 6 %), far below the 20 % keep threshold.
- cProfile of `main` WITH R1 applied (58 s under the profiler): `_findings` 35.4 s, of which
  `_scopes` 10.0 s (a full recursive `iter_fields` visit of every tree), `_udim_hits` 14.7 s (incl.
  `_int_names` 8.7 s), the memoised walk 9.7 s; `call_chains.load_live` 14.4 s.
- `_scopes` is only read when a file has a hit, and almost no file has one (findings are a few dozen
  over 927 files).

Ownership: `tools/architecture/duplicate_guard.py` is owned by #1486 (PR #1684, open) and #1688 (open);
#1615 / t_82b1bc95 owns full-suite wall time; #1608 cold entry tokens; #1649 G22 atlas; #1619 floor quality.
So this card is **OBSERVE**: it never edits `duplicate_guard.py`; candidates are applied in-process by the
harness and recorded as a proposal.

## Frozen contract (written before any candidate code)

- Base: `origin/main` `fa6330a3`. Harness: `docs/research/autoresearch-repo-guards-harness/bench.py`
  (extended with `--baseline`: the names applied to BOTH variants).
- Metric (one number): wall seconds of one in-process `duplicate_guard.main(["--root", <repo>, "--json",
  "--table"])`, interpreter start excluded. CPU seconds (`time.process_time`) recorded next to it as a load
  check. Command: `uv run python docs/research/autoresearch-repo-guards-harness/bench.py --rounds 3
  --baseline r1_walk_memo --candidate <name> --out C:/x/ar_t_b1bb763f/<name>.json`.
- B = main + R1, C = main + R1 + candidate: the number measures the gain ON TOP of R1, so it is not
  double-counted with standing #1. Median of 3, B and C alternate in ONE process (B, C, B, C, B, C).
- Keep threshold: median C <= 0.80 x median B, with parity.
- Parity (fail-closed, every run): identical exit code and stdout of `main` vs the first run (findings,
  stale rows, #1424 status problems, Russian table); identical `scan_text` result on every `tests/**/*.py`
  (B-set vs C-set); guard tests green with B+C injected (`-p ar_dg_inject`, `AR_DG_CANDIDATE=<names>`):
  `tests/test_architecture_map_1359.py tests/test_duplicate_status_1424.py`.
- Stop rule: 3 candidate rounds, or 2 h of card time, or C/B <= 0.60 - whichever first.
- Forbidden: deselecting / skipping guard tests, removing a rule, scope or check, changing allowlist rows,
  `contexts.yaml` or any context map, caching across processes or commits, editing `duplicate_guard.py`,
  `call_chains.py` or other cards' files, editing delivered packages. Calibration (card rule 3) does not
  apply - a time metric, parity replaces it.
- OBSERVE: the harness records what it would change; a retained candidate becomes a proposal for a
  follow-up card on `duplicate_guard.py` after #1486 / #1688 merge (normal PR + review, this bench as parity).

## Rounds

(round log below; receipts outside git: `C:/x/ar_t_b1bb763f/`)

| Round | Candidate (on top of R1) | median B, s | median C, s | C/B | parity | verdict |
|---|---|---|---|---|---|---|

## Итог
