# Autoresearch #85: trainer stop census (OBSERVE)

Card t_9aa9bbc1, branch `research/autoresearch-standing-85`, base `origin/main@86852f3789f5c9f747db21314dddebe350986129`.

## Русское резюме

**Гипотеза H85 подтверждена, но на пороге.** Запись `artifact` в ledger сводит разные причины остановки в одну
корзину. Автоматическая «перепись остановки» (`census.py`, без LLM, 0,11–0,21 с на 17 прогонов) восстанавливает
по папке прогона 7 признаков: есть ли FBX, просьба о Gate 1, BM-12, источник отделки, геопривязка, геометрия
и вопрос об открытии сцены.

- Отложенная выборка (G22 ×9 + 63A ×1): micro-F1 **0,90**, ровно на пороге keep (≥ 0,90). TP 36, FP 0, FN 8.
  Gate 1 — 10/10. Нынешний ledger (только `artifact`) даёт 0,0.
- Настроечная выборка (KPP1 ×7): 0,9688. Возмущения 4/4 в ожидаемую сторону. Три свежих запуска дали
  одинаковый результат (preds `87e167c9b033`).
- Главный вывод для решения по #81: 16 из 17 прогонов, кроме Gate 1, просят ещё и исходные данные. Отделка нужна
  в 13 из 17, геопривязка — в 12 из 16, геометрия — в 13 из 16; это ручная разметка. Если разрешить только
  самоподтверждение Gate 1, вопросы к источникам почти везде останутся. Блокируют ли они сборку на самом деле,
  здесь не измерялось.
- Побочные находки:
  - в g22 r83-C3 `QUESTIONS.md` потерял кириллицу: 75 % символов — `?`;
  - почти в каждом прогоне `uv run agr --help` создаёт `.venv` в практическом дереве.
- Боевой код не менялся (OBSERVE). Предложение (would-change): поле `stop_census` в строке ledger рядом с
  `first_failing_step`. Делать его — задача владельца тренажёра, через обычный PR.

## Why this target

Focus override (#1855 trainer): pick the most frequent first failing step. Ledger on main: 3/3 `artifact`
(KPP1 v004, G22 K2, 63A); PR #1875 adds a 2nd `sources-dwg` row (owned by #1874 / PR #1880).
`artifact` = "no FBX", which #81 traced to the Gate 1 stop; passing it needs Artem's decision on #81
(practice self-confirmation of Gate 1/BM-12, still blocked). #82-#84 measured the Gate 1 *handoff*.
Both #80 and #81 listed as a next target "record the actual stop reason separately from `artifact`", nobody did.
The ledger only says `artifact`, so the focus rule reads one undifferentiated bucket. This card measures whether the
stop reasons can be recovered automatically from the run folder, with no LLM and no new practice runs.

Skipped (owners): Gate 1 self-confirmation (#81, Artem), DWG stall (#1874/PR #1880), bank durability (#1861),
trainer launch guard (#1877), form (closed), texture fallback (superseded by the ledger).

## Contract (frozen before any classifier code)

- **Labels:** `docs/research/trainer-stop-census-r85/labels.json`, 7 binary labels per run
  (`fbx, gate1, bm12, finish_src, geo_src, geom_src, open_scene`), hand-read from `built/QUESTIONS.md`,
  committed before `census.py` existed (see git history). `null` = unreadable text, not measured.
- **Fixture:** all 17 run folders in `C:/x/trainer/runs` (exit 0 everywhere, no FBX anywhere).
  Tuning = KPP1 v004 (7 runs). Held-out = G22 K2 (9) + 63A (1), never used to write or edit the rules (texts were read for labelling; see Round log).
  Per-input SHA-256 of `QUESTIONS.md` and `run.json` pinned in `labels.json`; `census.py` refuses to score
  on any hash mismatch (full-manifest preflight).
- **Metric M85:** held-out micro-F1 over all measured (run, label) cells; second number: `gate1` held-out exact
  agreement. Baseline = what the ledger records today (`artifact` only, every other label 0) -> positives found 0.
- **Keep (H85 confirmed):** held-out micro-F1 >= 0.90 AND `gate1` held-out 9/10 or better AND every perturbation
  moves in the expected direction. Otherwise refuted (rules do not transfer) or inconclusive (preflight/fixture gaps).
- **Repeats:** the census is deterministic; 3 fresh runs must give identical output (stability = identical
  JSON hash), wall time reported per run.
- **Perturbations (scratch copies under `$TMPDIR`, originals untouched), expected direction:**
  P1 add `built/x.fbx` -> `fbx` 0->1, others unchanged; P2 delete `QUESTIONS.md` -> all question labels 0 and
  `handoff=missing`; P3 `run.json` exit `timeout` -> `exit_stop=timeout`; P4 replace the Gate 1 request by
  "Gate 1 approved" statement -> `gate1` 1->0 (positive trigger witness = kpp1 r83-C1, an accepted-control
  equivalent = held-out g22 r83-B2 where `gate1` must NOT fire).
- **Stop rule:** max 3 rule-revision rounds, tuning-only; held-out scored once per round and never used to edit.
  Budget: 60 min of card time.
- **Forbidden:** editing run folders, labels after the freeze commit, `tools/trainer/trainer.py`, ledger.json,
  other cards' branches; LLM judging; tuning on held-out.
- **OBSERVE:** the proposed ledger field (`stop_census`) is recorded as a would-change; no production change.

## Replay

`uv run --frozen python docs/research/trainer-stop-census-r85/census.py --labels docs/research/trainer-stop-census-r85/labels.json --out <NEW>.json`
(replay limited: run folders live only on this PC in `C:/x/trainer/runs`; hashes pinned.)

## Round log

Disclosure: the held-out texts WERE read by the author to write the frozen labels (one person labels and
classifies). Rules were written from KPP1 texts only and never edited after a held-out score was seen;
held-out mismatches printed in round 1 were not used for any edit.

| Round | Change (tuning-driven) | Tuning F1 (tp/fp/fn) | Held-out F1 (tp/fp/fn) | gate1 held | Perturbations |
|---|---|---|---|---|---|
| r1 | rules v1 | 0.9355 (29/0/4) | 0.9000 (36/0/8) | 10/10 | 3/4: P4 harness bug (also blanked q2) |
| r2 | "Recommend X: confirm Y" counts the part after the colon (kpp1 r83-C2); P4 harness fixed to touch q5 only | 0.9688 (31/0/2) | 0.9000 (36/0/8) | 10/10 | 4/4 |
| final ×3 | none (determinism) | 0.9688 | 0.9000 | 10/10 | 4/4, preds `87e167c9b033` identical, wall 0.211/0.114/0.110 s |

Stopped after r2: the 2 remaining tuning FN (kpp1 r83-C1 `bm12`, r83-C3 `finish_src`) come from sentences that open
with "Recommended:" and which the labeller marked as requests. That breaks the frozen label rule. Tuning towards
them would mean fitting label noise.

Held-out per label (agree/measured): fbx 10/10, gate1 10/10, geo_src 9/9, open_scene 8/9, bm12 7/9, finish_src 7/10,
geom_src 7/9. One real classifier defect is known and was deliberately not fixed, because it showed up on held-out:
`open_scene` expects "open" before "scene", so it misses 63A's "should the new review scene be opened
automatically?". It is left for a new round with fresh held-out runs. Unreadable g22 r83-C3 (75 % `?`) has only
`gate1`/`finish_src` labels; the census still finds `gate1`.

Not measured: runs with an FBX, non-zero exit or missing handoff exist only as perturbations (P1-P3). No real run
in the bank has them. `sources-dwg` rows (#1608, Drive evidence) were not exercised (not a `C:/x/trainer/runs` folder).

## Result

H85 **confirmed (at threshold, narrow)**: held-out micro-F1 0.90 >= 0.90, gate1 10/10, perturbations 4/4,
deterministic over 3 runs. Baseline ledger: 0.0. Receipt `docs/research/trainer-stop-census-r85/receipt.json`
(census.py SHA-256 `94f557cecaf5a3501104626cf89577069d0c5da8574d814f1467453ecb16efe1`, labels.json
`57d10f02ee517e1cf17fbc6cdf4e6a3f052b174dbe389d6b3ec3ededdc8fcf5f`). Review readiness is separate (see card).

Hand-label tally (17 runs): gate1 16/17, open_scene 14/16, finish_src 13/17, geom_src 13/16, geo_src 12/16,
bm12 9/16, fbx 0/17. At least one source request beyond Gate 1 (finish|geo|geom): 16/17 (all but 63A).
