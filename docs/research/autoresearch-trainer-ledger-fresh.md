# Autoresearch #111 — fresh trainer ledger at one head (OBSERVE)

Card t_cd81155d, branch `research/autoresearch-standing-111`. Contract frozen BEFORE any measurement.

## Кратко (по-русски)

Ledger тренера (`docs/trainer/ledger.json`) — вход для фокуса стоящей карточки («шаг, который падает чаще всего»).
В нём 4 строки от 24-25.11 (artifact 3/4, sources-dwg 1/4), снятые на старых головах main. С тех пор в main
слились #1863/#1865/#1880/#1887/#1927/#1939, а карточки #95-#110 мерили только сохранённые выходы или 63B bounds.
Гипотеза H111: на текущей голове свежие холодные прогоны на трёх practice-ready эталонах падают первыми уже
не на `artifact`. Это измерение (OBSERVE), продуктовый код не меняется; если подтвердится — PR только с новыми
строками ledger, чтобы следующая карточка выбирала цель по свежим данным.

## Why this target

- Card focus: most frequent first failing step in the trainer ledger. Ledger @7762dcfe: `artifact` 3/4,
  `sources-dwg` 1/4, all rows from heads of 2026-11-24/25.
- #100 cleared `artifact` only on STORED outputs; #99 fresh runs were KPP1-only (6/6 stop at `bounds`).
  #100 next 1 / #110 next 1 asked for a fresh, comparable first-failure distribution at ONE head — not done yet.
- Not duplicated: #1917 (KPP1 FBX-first sentence), #1928 (G22 adapter), #1924/#1927 (A/B harness — reused,
  not changed), #1866 (DWG integrity), bank scope decisions (#1855/#1861), 63B bounds chain (#104-#110, stopped).
  Form research closed; atlas fallback inactive (ledger rows exist).

## Metric

- M111 = number of fresh runs whose `first_failing_step == "artifact"`, out of N = 9
  (3 practice-ready etalons x 3 repeats). Secondary (reported, not a keep criterion): full first-failure
  distribution, per-etalon mode, wall_s, input tokens, questions.
- Baseline (ledger): artifact share 3/4 = 0.75 (3/3 on these three etalons in the 2026-11-24 rows).
- Command per run (unchanged harness, codex lane, default model `gpt-6.1-terra`, `--timeout-s 1800`):
  `uv run agr trainer run <etalon> --out C:/x/trainer/runs/<etalon>-codex-r111-<k>`
  then `uv run agr trainer score <etalon> --built <run>/built --out <run>/score.json`.
- Fixture: practice-ready etalons in `docs/trainer/etalons.json` @7762dcfe: `kpp1-v004`, `g22-k2-stage1`,
  `63a-stage1` (sources and keys hash-checked by `trainer run`/`score`; per-input SHA-256 published in receipt).
- Order: round-robin k=1..3 over the three etalons (KPP1, G22, 63A), sequential (one codex at a time).

## Hypothesis and keep rule

- H111 confirmed if M111 <= 3/9 AND the mode of the fresh distribution is not `artifact`.
- Refuted if M111 >= 5/9 (artifact still the most frequent fresh stop).
- Otherwise (4/9, or fewer than 9 scored runs) inconclusive.
- Per-etalon: a step counts as the etalon's fresh first stop only if >= 2/3 repeats agree.
- Kept change if confirmed: append the 9 fresh rows to `docs/trainer/ledger.json` through
  `agr trainer ledger --add` (data only, via PR + review). No product code, harness text or tolerance change.

## Checks (frozen)

- Positive trigger witness (injected): score an EMPTY built folder for `kpp1-v004` -> expect
  `first_failing_step == "artifact"`.
- Accepted control: score the stored #100 KPP1 FBX (`C:/x/trainer/runs/kpp1-v004-codex-r99-C1/built`) -> expect
  `artifact` pass (first stop later than artifact). If that path is gone: `not_measured`.
- Calibration (rejected worse than accepted) is the scorer's own `trainer calibrate` from #1859; not re-run here,
  reported as `not measured in #111`.
- Invariance: harness unchanged (no overlay); the same head for all 9 runs (`origin_main` in run.json must be
  identical, else the run is excluded and the series is inconclusive).

## Budget and stop rule

- Measured pair (#99/#100 history): one run 160-330 s + score 30-90 s. Budget: 9 runs, hard stop at 150 min wall
  for the whole series. A budget stop or a timeout/non-zero exit leaves that run `not_scored`; the series is then
  inconclusive, not shortened. Next command for a resumed series: the same `run`/`score` pair for missing k.
- No repeat of a run that already finished (no cherry-picking).

## Forbidden shortcuts

Deselecting etalons/runs, overlays or prompt edits, editing tolerances, scoring with `--allow-key`, editing
delivered packages or bank keys, touching other cards' files (#1917/#1928 branches), Max (Blender only).

## Replay

Runs under `C:/x/trainer/runs/*-r111-*` (local; replay limited); hashes of `run.json`, `score.json` and built FBX
in `docs/research/trainer_ledger_fresh_r111/receipt.json`.
