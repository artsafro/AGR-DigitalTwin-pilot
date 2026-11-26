# Autoresearch #115 — named deliverable on held-out G22 (trainer `artifact`), OBSERVE

**Кратко (RU).** В ledger тренажёра (#1855, `docs/trainer/ledger.json` на main `55b885c1`) чаще всего первым падает
шаг `artifact` (3/4; `sources-dwg` 1/4). Перепись 62 сохранённых прогонов (`C:/x/trainer/runs`): из прогонов G22,
где агент собрал FBX, большая часть не засчитана — скорер отказывается от папки с несколькими FBX
(`module/body.fbx` + `typical/body.fbx`; r97-C1, r97-C3, r95-C3, r111-1). Гипотеза H115: фраза H99 «итог — один
`deliverable.fbx` в корне папки» (заморожена на KPP1 в #99, на G22 не настраивалась) вместе с правилом выбора #99
поднимает засчитанный `artifact` на G22 (с адаптером #97 в обоих плечах). Только наблюдение: банк, скорер и
доставленные пакеты не меняются; итог — предложение владельцу банка.

Status: contract FROZEN before any measurement (this commit). Result section is appended after the series.

## Why this target (step 1 of the card)

- Ledger @55b885c1 unchanged since 7762dcfe: `artifact` x3 (kpp1-v004, g22-k2-stage1, 63a-stage1), `sources-dwg` x1.
  Fresh #111 series: artifact first stop 7/8 scored + 1 unscored (G22 several-FBX refusal).
- Census (target selection, stored runs, no new runs): FBX-producing G22 runs 7, of which 4 refused for several FBX
  (r95-C3, r97-C1, r97-C3, r111-1). The finish-zone question (D341/D344) appears in almost every body run with and
  without FBX, so it does not separate artifact pass from fail (considered, rejected as target).
- Owned elsewhere, not repeated: KPP1 FBX-first sentence (#95, PR #1917), G22 adapter (#97, PR #1928 — reused here as
  the shared base of both arms, not measured), KPP1/63B bounds chains (#96, #101–#109, stopped), lineage escape
  (#113/#114), DWG truncation (#1866), A/B harness (#1924, merged; it overlays repo files only and cannot vary the
  task text, so the #99 bank driver is reused). #98 measured the pick rule on stored files only; #99 measured
  agent compliance on KPP1 where the baseline no longer produced several FBX (no trigger, refuted). The fresh G22
  combination (#97 next 1, #98 next 1) is unmeasured. Form research closed; atlas fallback inactive (ledger rows exist).

## Metric, arms, fixture (frozen)

- **Fixture:** `g22-k2-stage1` (bank `docs/trainer/etalons.json` sha256 `016aab0c…36635`, source NPZ `5eee4ac6…4622`,
  key `5b1e8d76…0f200` read only by the scorer, rejected v001 `8e97a80a…eb519`). Held-out for the candidate: the H99
  sentence and the pick rule were frozen on KPP1 (#98/#99); G22 never tuned them.
- **Practice root (both arms):** `make_roots.py` = `git clone --shared` of main `55b885c1b9ccdbe53df2c0d6ade9d4e5bd8ca364`
  + one commit: `floor_from_dump.py`, `module_build.py` copied from `jobs/garibaldi22/body-training-1619/hooks` to
  `tools/methods/body` (two path lines fixed) and the stage row in `docs/agents/SKELETONS-stages.md` naming the adapter
  by path (adapted copy of #97 `make_candidate.py`, blob `3bfa83dd`; the row moved from SKELETONS.md on main).
  Same root, trainer, scorer, lane (codex default), timeout 1800 s, hidden paths in both arms.
- **Arm C (control):** `bank_C.json` = byte copy of the git bank; scored on `built/`.
- **Arm D (candidate):** `bank_D.json` = git bank + the H99 sentence verbatim appended to the g22 task; scored on
  `built/deliverable.fbx` when that exact root file exists, else `built/` (#99 `pick.py` blob `eccedca4`, inlined).
- **M115 per run** = 1 if the scorer exits 0 and step `artifact` passes, else 0 (refusal, missing FBX, timeout = 0).
  Report per arm the sum over 3 runs; also first failing step, score, form_p95, FBX count, deliverable.fbx present,
  escape commands (paths outside the practice tree under `jobs/garibaldi22` or `AGR-evidence/1619-body-training`).
- **Runs:** 3 pairs (C_i ‖ D_i started together), driver `series.py`; log `C:/x/ev_t_a457c1b6/series.log`.
- **Budget (frozen from #97 pair wall ~3–6 min):** no new pair starts later than 60 min after the series start;
  unstarted runs are `not_run`; a budget stop makes H115 `inconclusive`, never a shortened KEEP.
  Confirm-vs-new-candidate budget: 1 frozen candidate, 0 new candidates (no tuning rounds on G22).

## Decision rule (frozen)

- **H115 confirmed** iff sum D − sum C ≥ +2, D ≥ 2/3, D ≥ C in every pair, every counted D run scored a root
  `deliverable.fbx` (not the folder fallback), and no counted D run is an escape run.
- **refuted** iff sum D ≤ sum C with all 6 runs finished (rc 0, scored or refused by rule).
- **inconclusive** otherwise (incl. budget stop, timeout, lift +1).
- Hypothesis result is published separately from review readiness. No KEEP of product code in this card in any case:
  a confirmed result becomes a would-change for the bank owner (#1855 follow-up): G22 task text + the pick rule.

## Static control (frozen; `control.py`, 3 reps, Blender scorer, no agent)

Inputs pinned by SHA-256: accepted key, rejected v001, r97-C2 `typical/body.fbx` `223f5bf0…ed6be`, r97-C1
`module/body.fbx` `c74148d0…dc4d`. Each case is a new folder; arm C rule = folder, arm D rule = root deliverable.

| case | content | expected C | expected D |
|---|---|---|---|
| W_witness (positive trigger) | deliverable = typical, + module decoy | refused | scored = direct typical (parity) |
| A_accepted (accepted control, rule fires) | deliverable = accepted key, + module decoy | refused | scored = direct accepted |
| R_rejected | deliverable = rejected v001, + decoy | refused | scored = direct rejected; accepted > rejected kept |
| P1_absent | typical + module, no deliverable | refused | refused (fallback, not counted) |
| P2_module_named | deliverable = module, + typical | refused | scored, not better than W (no gaming by a module) |
| P3_nested_only | `typical/deliverable.fbx` + module | refused | refused (root only) |

Parity bound: score and first failing step equal, form_p95 |Δ| ≤ 1e-4 m vs the direct file; spread across reps 0.
Clean = W/A/R; injected = P1–P3; not measured: VLM step (off), package step (not applicable at stage 1).

## Forbidden shortcuts

Editing the git bank, `tools/trainer/*`, scorer tolerances or the key; tuning the sentence on G22; rerunning a pair to
replace a bad result; counting a folder fallback or a run whose FBX was copied from outside the practice tree;
touching other cards' branches or delivered packages; 3ds Max.

## Replay

```
uv run --frozen python docs/research/trainer_deliverable_g22_r115/make_roots.py C:/Users/artsafro/agr-pilot/AGR-DigitalTwin C:/x/r115_roots
uv run --frozen python docs/research/trainer_deliverable_g22_r115/control.py C:/x/r115_roots C:/x/ev_t_a457c1b6/control.json 3
uv run --frozen python docs/research/trainer_deliverable_g22_r115/series.py C:/x/r115_roots
```

Replay is limited: inputs live on the local Drive bank and `C:/x/trainer/runs` (hash-pinned above); fresh agent runs
are not byte-reproducible (model sampling), the series is the evidence.

## Result (appended after the series; contract above unchanged since 5d90b92d)

**Итог (RU).** H115 **inconclusive** по замороженному правилу. Засчитанный `artifact` на G22: C 2/3, D 3/3, прирост
по парам [0, 0, +1]. Но механизм не сработал: ни один из трёх D-агентов не записал `deliverable.fbx` (0/3), все D
засчитаны по папке с единственным FBX; лишний засчёт D3 — случайность (у C3 два FBX `pilot/` + `typical/` -> отказ
скорера). D3 прямо пишет, почему не выдал `deliverable.fbx`: в модели нет первого этажа, верха и окон лестничных
площадок — «не выдаю неполную модель за итог». Все 5 засчитанных прогонов — частичное типовое тело, первый
проваленный шаг `form_v2`, score 0.7143 (как r97-C2). Побегов из практики 0/6. Статический контроль правила выбора
(3 повтора, разброс 0) — всё как ожидалось. Продуктовых изменений нет, KEEP нет.

- Practice root `88ef77fa95b13d5981ef7e6785c2d6ffde39c76b` (tree `2a995050a32db4f96134d60c933ea95320c381b4`) on
  main `55b885c1`; bank_C `016aab0c…36635`, bank_D `f421a570801c46d18fe34e4d9e465dad55ebf96098766bc36d07c5f24f3b8493`.
  Dry-run prompt: `deliverable.fbx` occurs 1x in D, 0x in C (the only difference).
- Series 17:11:17–17:24:55 (13 min 38 s, 3 pairs, budget 60 min not reached, all rc 0). Log `series.log`.

| run | FBX in built/ | root deliverable | M115 | first failing | score | form_p95 m |
|---|---|---|---|---|---|---|
| C1 | typical_partial/body.fbx | no | 1 | form_v2 | 0.7143 | 0.0139 |
| C2 | candidate/body.fbx | no | 1 | form_v2 | 0.7143 | 0.0128 |
| C3 | pilot/body.fbx, typical/body.fbx | no | 0 (several FBX refused) | — | — | — |
| D1 | build01/body.fbx | no | 1 | form_v2 | 0.7143 | 0.0128 |
| D2 | module_build/body.fbx | no | 1 | form_v2 | 0.7143 | 0.0128 |
| D3 | build/body.fbx | no (withheld: incomplete) | 1 | form_v2 | 0.7143 | 0.0139 |

- Decision rule: D−C = +1 (< +2) and counted D runs did not score a root deliverable -> not confirmed; D > C -> not
  refuted -> **inconclusive**. Escape commands (absolute main-checkout `jobs/` or bank evidence reads): 0 in 6 runs
  (relative `jobs/garibaldi22` mentions are hidden-path text inside the practice tree, not reads).
- Static control (`control.json`, 3 reps, spread 0 after dropping per-folder refusal text): W D = direct typical
  (form_v2 0.7143, p95 0.0128); A D = direct accepted (vlm 0.8571, p95 0.0001); R D = direct rejected (form 0.5714,
  p95 0.61), accepted > rejected kept; P1/P3 refused in both rules; P2 module named deliverable scores bounds 0.4286
  (p95 22.75) < W. Arm-C rule refuses all six cases (each holds two FBX). Clean = W/A/R, injected = P1–P3;
  not measured: VLM step, package step, agent compliance with the rule on any other etalon.
- Receipt `docs/research/trainer_deliverable_g22_r115/receipt.json`; evidence (runs, FBX, logs)
  `G:/Мой диск/AGR-evidence/1855-r115-deliverable-g22/SHA256SUMS.txt` (51 files, 2.3 MB). Replay limited (fresh
  agents are not byte-reproducible; inputs pinned by hash on Drive / `C:/x/trainer/runs`).

### What OBSERVE would change (not applied)

Nothing to the bank or scorer from this series: on G22 the H99 sentence is not followed when the agent judges its
model incomplete, so it cannot be the artifact lever there. The measured artifact losses on G22 come from agents
leaving 2 FBX (C3); a scorer-side rule cannot pick the right one without a name. The next stop for every counted G22
run is `form_v2` on a partial typical body (missing ground floor, top and stair-landing openings).
