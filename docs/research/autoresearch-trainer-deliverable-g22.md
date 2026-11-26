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
