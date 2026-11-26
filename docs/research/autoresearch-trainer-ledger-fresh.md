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

## Round log (after the frozen contract 8beb3c80)

### Итог по-русски

H111 **опровергнута**. На голове 7762dcfe свежие холодные прогоны (codex, harness без изменений) по-прежнему
чаще всего падают первыми на `artifact`: 7 из 8 оценённых прогонов (8/9 по соглашению #95, где отказ скорера
«несколько FBX» считается непройденным artifact). Единственный прошедший artifact прогон (63A k=1, все
геометрические шаги pass, отклонение 0.0 м) **загрязнён**: агент прочитал папку принятой версии
`AGR-evidence/1619-body-training/tower-A/v005` (5 команд) — фактически копия ответа. Чистых прохождений artifact: 0/9.
Причина остановок одна и та же во всех прогонах: агент ставит вопросы в QUESTIONS.md и останавливается до
первого модуля («Первый модуль не построен, BM-12 не отмечен») — правило «первый кусок принят, потом остальное».
Ledger прав: цель для следующей карточки остаётся `artifact`, механизм — остановка на Gate 1, а не bounds.
Продуктовых изменений и строк ledger нет (по контракту строки добавляются только при подтверждении).

### Numbers

| etalon | k | first stop | artifact | escaped | wall s | input tokens | questions |
|---|---|---|---|---|---|---|---|
| kpp1-v004 | 1 | artifact | fail (no FBX) | no | 203.0 | 1 896 474 | 4 |
| g22-k2-stage1 | 1 | not_scored (scorer: several FBX `body.fbx` x2) | - | no | 192.9 | 1 305 819 | 3 |
| 63a-stage1 | 1 | vlm (not run; geometry all pass, dev 0.0) | pass | **yes (5 cmds, 1619 evidence)** | 244.3 | 1 797 436 | 4 |
| kpp1-v004 | 2 | artifact | fail | no | 228.8 | 1 858 122 | 5 |
| g22-k2-stage1 | 2 | artifact | fail | no | 122.1 | 765 865 | 2 |
| 63a-stage1 | 2 | artifact | fail | no | 323.2 | 2 920 992 | 4 |
| kpp1-v004 | 3 | artifact | fail | no | 176.5 | 1 018 087 | 3 |
| g22-k2-stage1 | 3 | artifact | fail | no | 116.9 | 746 124 | 3 |
| 63a-stage1 | 3 | artifact | fail | no | 248.2 | 2 511 765 | 3 |

- M111 = 7/8 scored (8/9 by the #95 convention). Refuted is robust to the unscored run: even if it were a
  non-artifact stop, M111 >= 7 >= 5. Per-etalon fresh first stop (>= 2/3 agree): artifact on all three.
- All 9 runs: exit 0, `origin_main` 7762dcfe (invariance held), no overlay. Series wall 2039.7 s (budget 9000 s).
- Checks: witness (empty built, KPP1) -> `artifact` fail as expected; accepted control (stored #99 C1 FBX)
  -> artifact pass, first stop `bounds` as expected. Calibration: not measured in #111.
- Escape tagging (added after the contract, reporting only, does not change M111): command text matching
  `AGR-evidence/1619-`, `1855-trainer-v0/bank`, `C:/x/review-`, main-checkout `jobs|docs/trainer`.
  Known class (#87/#1859 escape guard); 63A `hidden_repo_paths` hides jobs/POLY63-A but not the Drive evidence path.
- Receipt: `docs/research/trainer_ledger_fresh_r111/receipt.json`; evidence
  `G:/Мой диск/AGR-evidence/1855-r111-ledger-fresh/SHA256SUMS.txt` sha256
  7c8be76ce4a2ac22e59fbc1c3f8a7a7279b37fdee868ced7dd22c6f4a1b792ce (50 files: run.json, score.json, last.txt,
  prompt.txt, QUESTIONS.md per run + series/witness/control JSON + the two scripts).

### Next targets

1. Gate-1 stop is the artifact mechanism on fresh runs: A/B (`agr trainer ab`, #1927) of the #95 FBX-first
   practice sentence (PR #1917) on a clean, NOT-tuned etalon (63A or G22 with #1928 adapter); count artifact passes /3.
2. Escape guard: 63A practice can read `AGR-evidence/1619-body-training` (answer); add the Drive evidence
   path of each etalon's accepted lineage to the scrub/hide list and count escaped runs (owner: trainer #1855/#1859).
3. Scorer: G22 several-FBX refusal still loses runs (1/3 here) — single deliverable rule (#95/#98) remains open.
