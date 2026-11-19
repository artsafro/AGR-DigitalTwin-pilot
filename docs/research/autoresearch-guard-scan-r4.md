# Autoresearch: duplicate_guard scan time on top of R1 (standing card #3, t_b1bb763f)

## Кратко для Артёма

Продолжение standing #1: время полного скана `duplicate_guard` поверх R1. Режим OBSERVE, `duplicate_guard.py`
не правился (им заняты #1486/PR #1684 и #1688). R3 отброшен по замеру (разбор файлов — всего 6,9 из 53 с).
R4 и R4+R5 ускоряют скан на 11-13 % при полном паритете, порог 20 % не взят — ничего не принято.
Оба приёма можно бесплатно добавить в будущую карточку внедрения R1.

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

| Round | Candidate (on top of R1) | median B, s | median C, s | C/B (wall) | C/B (CPU) | parity | verdict |
|---|---|---|---|---|---|---|---|
| guard check | `m1_scope_module` (mutation: every scope = `<module>`) | 23.23 (1 run) | 22.54 | 0.97 | - | **False** (rc 0 -> 1) | parity guard catches it |
| 1 | `r4_lazy_scopes` | 27.94 (24.77 / 27.94 / 28.72) | 22.30 (21.94 / 24.92 / 22.30) | 0.798 | 0.806 | True (6/6 + 757 `tests/*.py`) | formally <= 0.80, but borderline -> confirm |
| 2 | `r4_lazy_scopes` (confirmation, same command) | 29.11 (29.71 / 27.42 / 29.11) | 25.77 (25.77 / 30.33 / 19.99) | 0.885 | 0.882 | True | **not kept** (round 1 was load noise) |
| 3 | `r4_lazy_scopes,r5_lazy_int_names` | 23.32 (24.48 / 23.32 / 22.78) | 20.34 (20.81 / 19.74 / 20.34) | 0.873 | 0.870 | True | **not kept** (< 20 %) |

Injected guard tests (B+C = `r1_walk_memo,r4_lazy_scopes`, `-p ar_dg_inject -n 4`):
`tests/test_architecture_map_1359.py tests/test_duplicate_status_1424.py` **287 passed** (145.6 s).
PC load: other workers ran during all rounds (B ranged 22.8-29.7 s); B/C alternate in one process, so the
ratio is fair, absolute seconds are not idle numbers. Stop reason: 3 candidate rounds.

Not kept, recorded for the follow-up R1 card (they are free and exact, but each alone is ~11-13 %):
- R4: `_findings` builds `_scopes(tree)` lazily, on the first hit's lookup (most files have no hit).
- R5: `_udim_hits` builds `_int_names(tree)` lazily, on the first `consts.get` (a Name term in an addition).

## Итог

Цель — время полного скана `duplicate_guard` поверх R1 (мемоизация `ast.walk`, standing #1). R3 (общий
разбор файлов) отброшен по замеру: весь `ast.parse` = 6,9 из 53 с. R4 (ленивые области видимости) и R4+R5
(+ ленивые целочисленные имена) дают устойчиво 11-13 % (C/B 0,885 и 0,873 по стене, 0,88/0,87 по CPU),
вывод совпадает байт-в-байт, мутация паритета ловится, 287 guard-тестов зелёные с подменой. Порог 20 % не
достигнут: код не принят. Первый замер R4 (0,798) — шум нагрузки, повтор его не подтвердил.
Остаток скана после R1: `_udim_hits` и `call_chains.edges`; это следующие цели (бэклог).
