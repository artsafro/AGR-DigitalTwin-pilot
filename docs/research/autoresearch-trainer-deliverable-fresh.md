# Autoresearch #99 — trainer: fresh agents and a named `deliverable.fbx` on KPP1 (OBSERVE)

**Кратко (RU).** Самый частый первый провал в ledger тренажёра — `artifact` (3 из 4 строк). #95 показал: с
предложением «сначала FBX» агенты на KPP1 строят FBX 3/3, но в зачёт идёт 1/3 — оценщик отказывает, когда в папке
несколько FBX. #98 подтвердил на уже построенных файлах G22, что явное имя `deliverable.fbx` снимает отказ (1/3 → 3/3),
но не проверял, выполнит ли свежий агент такое указание. Здесь: 3 + 3 свежих прогона KPP1 (KPP1 не использовался для
правила #98) — рука C = банк #95 как есть, рука D = то же + одна фраза про `deliverable.fbx` и правило выбора файла
оценщиком. Ничего в продукте не меняется. Результат — в разделе «Result».

Status: **contract frozen before any r99 run (9ed39913); series complete.** Hypothesis result: **refuted** (see "Result").

## Target and owners

- Ledger `docs/trainer/ledger.json` @ `c42d7fbc`: `artifact` 3/4, `sources-dwg` 1/4 (owned by #1874/#1880, merged).
  Rows exist, so the texture/atlas fallback is inactive; form research is closed.
- Not owned elsewhere: #95/PR #1917 owns the FBX-first sentence (reused as the baseline arm, not changed); #96 KPP1
  bounds; #97/PR #1928 G22 adapter; #98 named handoff on existing files (this card is its next target 1);
  #1924/PR #1927 A/B harness (not merged; this card reuses the #95 `--bank` pattern instead).

## Hypothesis H99

A fresh codex agent told to save the final model as `deliverable.fbx` in the output folder does so, and the scorer
rule "score `built/deliverable.fbx` when it exists" turns the #95 several-FBX refusals into counted artifact passes.

## Arms (one variant, frozen)

- **C (baseline)** = `uv run agr trainer --bank BANK_C run kpp1-v004 ...`, BANK_C = #95 `bank_r95_C.json`
  (SHA-256 `51c6e51e98cc5152f5f4873f948523c9f6e07981088d57bf616b13b04a5ced3a`; made from the git bank
  `016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635`, unchanged at `c42d7fbc`). Scored on `built/`.
- **D (candidate)** = BANK_D from `make_bank.py` (BANK_C + the `CANDIDATE` sentence on kpp1-v004 only), SHA-256
  `cc904f8001ec780ec7b96a1a8bba394dab39c26640e0e858f526410694853a18` (`C:/x/ev_t_bda45f44/bank_r99_D.json`). Scored with `pick.built_arg(run, "D")`: `built/deliverable.fbx`
  if that exact root file exists, else `built/`.
- Practice tree = `origin/main` at launch (`run.json:origin_main`), `tools/trainer/trainer.py` SHA-256
  `b48f86ecd8f5626a6d39fdcee13bedd0574a29d7738561e48f695d55b95aad0e`.

## Metric

- **M99 (primary)** = per arm, runs with `artifact = pass` AND `readback = pass` AND zero E93 escapes
  (`C:/x/ev_t_04777f53/audit_e93.py`, SHA-256 `e78e4927…6ec3`, = #93 `trainer-escape-r93/audit.py`) / 3.
  A run that reads the key counts as fail. Runs are never re-run or dropped; crash/timeout = fail with reason.
- Secondary (recorded, not gating): compliance = `built/deliverable.fbx` exists (D; also checked on C),
  FBX count in `built/`, `first_failing_step`, bounds, wall s, input tokens, exit.
- Paired spread: lift_i = M(D_i) − M(C_i), i = 1..3 (pairs run back to back).

## Thresholds and stop rule

- **CONFIRMED:** D ≥ 2/3 AND D − C ≥ 1 AND D compliance ≥ 2/3 AND D escapes ≤ C escapes.
- **REFUTED:** D ≤ C, or D compliance ≤ 1/3.
- Anything else = **inconclusive**.
- Series: C1 D1 C2 D2 C3 D3, one run at a time (one accoreconsole at a time), `--timeout-s 1800`.
  Stop: 6 runs, or no new launch later than 3.5 h after the first launch (`series.py STOP_S`); a budget stop =
  inconclusive for this run with the exact `--only` command for the rest. Confirm-vs-new-candidate budget: one
  candidate, zero new candidates, no re-wording between runs.

## Control (scorer rule, before the series)

`control.py`: accepted KPP1 v004 key vs Artem-rejected step 3 (110 mm NW step, [D380]), each staged as
`built/deliverable.fbx`, clean and with the other one injected as `built/decoy.fbx`. Expected per variant:
C refuses both injected dirs (rule fires = positive trigger witness); D score of `*_inj` == `*_clean` exactly
(invariance, changed files +1 per injected case); accepted score > rejected score (calibration; if equal, the
calibration is recorded as **not measured** for this scorer and the primary metric is unaffected).

## Forbidden shortcuts

No edits to `docs/trainer/etalons.json`, `tools/trainer/*`, the key, delivered packages or other cards' files; no
re-running or dropping runs; no scoring of the key as a run output; no rewording of the sentence after the first run;
no changes to timeout or scorer steps. OBSERVE: adoption of the sentence/rule into `trainer.py` goes to the #1855
owner via a normal PR.

## Replay

```
uv run --frozen python docs/research/trainer_deliverable_fresh_r99/make_bank.py C:/x/ev_t_04777f53/bank_r95_C.json NEW_D.json
uv run --frozen python docs/research/trainer_deliverable_fresh_r99/control.py NEW_DIR
uv run --frozen python docs/research/trainer_deliverable_fresh_r99/series.py C:/x/ev_t_04777f53/bank_r95_C.json NEW_D.json
```

Replay limited: BANK_C and the runs are local (`C:/x/`); evidence copy goes to
`G:/Мой диск/AGR-evidence/1855-r99-deliverable-fresh/` + `SHA256SUMS.txt`.

## Round log

- 21:5x control (`control.py`, 17 s): rule fires — arm C refuses both injected dirs (rc 2, several FBX); arm D
  score `*_inj` == `*_clean` exactly (accepted 0.0 / 0.0, rejected 0.4286 / 0.4286; +1 file per injected case,
  0 changed original bytes). Calibration **not measured**: the accepted v004 file IS the key, so `artifact` fails
  by the key-copy guard ("built result IS the key"); the rejected step 3 fails `bounds` (3.80 m). See `control.json`.
- 21:55:41–22:21:42 series C1 D1 C2 D2 C3 D3 (`series.log`), all exit 0, practice tree `c42d7fbc`, no budget stop
  (26 min of the 3.5 h cap). One candidate, no re-wording.

## Result

**Кратко (RU).** Гипотеза H99 **опровергнута** по замороженному правилу (D ≤ C): обе руки дали зачётный FBX 3/3
(artifact + readback, без побегов), прирост по парам [0, 0, 0]. Причина — базовая рука C на текущем `main`
(`c42d7fbc`) больше не оставляет несколько FBX (0/3; у #95 на `afc930ea` было 2/3), то есть триггер «несколько FBX»
в C не воспроизвёлся. Агенты выполняют указание: `deliverable.fbx` создан в 3/3 прогонов D. Но та же фраза
**порождает** несколько FBX в `built/` (D 3/3: промежуточные `body.fbx`, `combined_candidate.fbx`), поэтому
без правила выбора файла оценщиком текущий `trainer.py` отказал бы всем трём D. Вывод: фразу саму по себе в
задание не добавлять; если её принимать — только вместе с правилом выбора `deliverable.fbx` в оценщике.
Следующая остановка у всех 6 прогонов — `bounds` (отклонение углов 4.0–4.06 м, у C2 40.7 м).

| Arm | M99 counted | `deliverable.fbx` | several FBX in `built/` | escapes | first_failing_step | wall s | input tokens M |
|---|---|---|---|---|---|---|---|
| C (bank #95) | **3/3** | 0/3 | 0/3 | 0/3 | bounds ×3 (4.06, 40.74, 4.06 m) | 228–250 | 2.14–2.86 |
| D (+H99) | **3/3** | 3/3 | 3/3 (2, 4, 2 FBX) | 0/3 | bounds ×3 (4.06, 4.00, 4.06 m) | 214–252 | 2.01–2.73 |

- Hypothesis: **refuted** (frozen rule: D ≤ C). Review readiness is separate (below).
- Positive trigger witness in C: **not exercised** (0/3 several-FBX runs). The rule's trigger was exercised only by
  the control injections and by the D runs themselves.
- Clean / injected / not measured: clean D runs 3/3 scored on the named file; injected control 2/2 refused by C and
  invariant under D; not measured — calibration accepted > rejected on KPP1 (key-copy guard), held-out G22/63A/63B
  fresh runs, package step, compliance under a scorer that ignores the name.
- Counterfactual (by the deterministic refusal shown in the control, not rescored): D runs scored by directory → 0/3.
- Run status: complete, 26 min wall, no budget stop.

Receipt `trainer_deliverable_fresh_r99/receipt.json` (runs, per-run hashes of events/score), `control.json`,
`series.log`. Evidence: `G:/Мой диск/AGR-evidence/1855-r99-deliverable-fresh/` + `SHA256SUMS.txt`
(SHA-256 `3cd239a315cc0876ba0dc4a99b0772382981003f76e9d242c3457dbe78dc1ad8`, 263 files: run.json, score.json,
prompt, last, events, built/, both banks, control.json). Replay of the table:
`uv run --frozen python docs/research/trainer_deliverable_fresh_r99/analyze.py C:/x/ev_t_04777f53/audit_e93.py NEW.json`
(replay limited: run folders `C:/x/trainer/runs/kpp1-v004-codex-r99-*` are local; Drive copy holds the inputs).

**Kept changes:** none (OBSERVE). Proposal for the #1855 owner, not applied: if a named deliverable is adopted, ship
the sentence and the `pick.built_arg` rule together in one `trainer.py` change (the sentence alone makes the current
scorer refuse every run). The KPP1 next stop is `bounds` (owned by #96 next target: L01 levels + east extent).
