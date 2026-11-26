# Autoresearch #105 — key-free typical-storey band from the Revit source (OBSERVE)

**Кратко.** Проверяем одно правило: можно ли по одному исходному Revit FBX площадки 63, без ключа, найти
диапазон типовых этажей башни (повторяющиеся одинаковые этажи) и габарит фасада, и попасть во все шесть граней
принятого BODY с допуском `bounds` 0,10 м. Правило подобрано на 63A (там диапазон дан в задаче), проверяется на 63B
(там диапазона в задаче нет; #91 остановился на `bounds` 27,67 м). Это наблюдение; модели, банк, оценщик и задачи не меняются.

## Frozen contract (committed before the held-out 63B measurement)

- Ledger `e1f3f168d7139b290871e5e49a0f3b84ff0ca668:docs/trainer/ledger.json` (Git blob SHA-256
  `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7`): `artifact` 3/4, `sources-dwg` 1/4. `artifact` is
  cleared on stored outputs (#100) and fresh KPP1 runs stop at `bounds` (#99); KPP1 `bounds` waits for the bank owner (#103),
  63B `bounds` is the open source-reachable part (#104: top face reachable, no key-free selector). This card takes #104 next
  target 1. Not doing: #1924/#1927 A/B, #1928 adapter, #1917 prompts, #1866 DWG truncation, closed form topic, fallback atlas.
- **Selector S105 (one variant, frozen in `trainer_storey_band_r105/replay.py::select`).** Rows = readable source objects of the
  existing native dump (`revit_fbx_dump_blender.py`) strictly contained in the approved tower box (`boxes63.json`, as #104).
  Level = `z0` rounded to 0.01 m with >= 20 rows starting at it. Storey signature = multiset of rows at the level keyed by
  XY bbox rounded to 0.1 m and height rounded to 0.01 m. Chain = levels `z, z+p, z+2p, ...` with consecutive multiset Jaccard
  >= 0.9, length >= 3. Pick the longest chains, then the smallest pitch, then the highest phase (first level). Band
  `Z = [first level, last level + p]`; XY = union of band rows (z0 in `[Zlo, Zhi)`) whose name does not start with
  `Перекрытие` (Revit Floors category; slab edges overhang the facade). No key, no task range, no learned offset.
- **Tuning disclosure.** Designed on 63A only (the 63A task text gives `+10.15 .. +47.95`, 12 x 3.15 m). Exploration on 63A:
  slabs/walls repeat at `9.45 + 3.15k`, windows at `+0.70` phase; the window phase matches the 63A key; slab-inclusive XY was
  0.112 m out, floor-category exclusion 0.051 m. Thresholds 20 / 0.9 / rounding were chosen once and not tuned against 63B.
  63B source histogram was not inspected before this commit; 63B key bounds were already published by #104 (not used here).
- **Metric `M105`** = native `trainer.bounds_step` `max_corner_dev_m` of the selector box (one synthetic mesh with
  `bounds_m` = S105 box) against the accepted key readback, per tower. Pass `<= 0.10` (unchanged `TOL`). Baseline = the #91
  submission (`63B`: fail 27.67 m; `63A`: pass 0.0442 m). Report all six signed face deltas, pitch, storeys, chain count.
- **H105 confirmed** iff 63B (held-out) passes in 3/3 repeats and 63A (tuning) passes in 3/3; **refuted** iff 63B fails in
  3/3 with all controls green; otherwise inconclusive. A deviation within +/-0.0001 m of 0.10 is inconclusive.
  Confirmation = reachability of a key-free bounds for this site/export only, not transfer to another project, not an
  agent's behaviour, not BODY form, openings, materials or package acceptance.
- **Calibration first (native, unchanged):** 63B accepted v007 vs itself pass/0, rejected v004 strictly worse and fail, every
  repeat. Calibration failure stops the series (inconclusive).
- **Controls per tower and repeat.** Clean: reversed source row order gives an identical selection. Injected positive
  trigger: one synthetic facade row at the first band level spanning the selected XY with `Xmax + 0.5 m` -> same levels,
  band rows +1, selected `Xmax` +0.5 m exactly (expected: M105 >= 0.5 on that tower). Injected negatives: the same row named
  as a Floor (`Перекрытие SYNTHETIC`) -> levels, bounds and band rows unchanged (floor exclusion fires); the same row shifted
  outside the tower box in X -> selection identical. Any failed control makes that tower/repeat inconclusive.
- **Budget (frozen).** 3 sequential repeats, each a fresh Blender 4.4 import of a staged, hash-checked copy of the source +
  native readbacks of 63A v005, 63B v007, 63B v004, #91 63A and 63B bodies. Cap 420 s for the series, first complete pair
  <= 140 s and continue only if `3 x pair` fits the cap. Zero new variants; no retries; budget stop or incomplete pair =
  inconclusive with partial receipt. Wall time reported separately.
- **Forbidden:** changing `TOL`, the trainer, the scorer, the bank, the task text, the box file or any model; tuning on 63B;
  key-derived offsets; post-hoc filters. KEEP is impossible here (no product change; an agent-facing rule is a separate PR).
- **Replay:** `uv run python docs/research/trainer_storey_band_r105/replay.py NEW_DIR` (`NEW_DIR` inside the worktree, must not
  exist). The driver verifies every hash below before and after the series, and byte-parity of the code inputs to `e1f3f168`.

### Full input preflight

| Input (relative to `G:/Мой диск/AGR-evidence/` except Blender) | SHA-256 |
| --- | --- |
| `1855-trainer-v0/bank/63a-stage1/STLB-04_RR_AR.fbx` | `2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7` |
| `1619-body-training/gate1/boxes63.json` | `e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7` |
| `1855-trainer-v0/bank/63a-stage1/63A_Stage1_v005.fbx` | `f3769c62a7e9fdbfcf7a59624269bcd0374ca494f593e2e85c08474a0007798a` |
| `1855-trainer-v0/bank/63b-stage1/v007.fbx` | `53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7` |
| `1855-trainer-v0/bank/63b-stage1/v004.fbx` | `6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae` |
| `1855-r91-artifact-route/63A-1-aligned/body.fbx` | `6b5e5ec58f6210bba4667f215740fca654cc6ea44dc0bc3fad3baae6e025e250` |
| `1855-r91-artifact-route/63B-1-aligned/body.fbx` | `aa6820088d16b5d3847b2b1ecdeab65d0b9375d07b875caf9b2e4127f299fa8e` |
| `C:/Program Files/Blender Foundation/Blender 4.4/blender.exe` | `fd21f4b9f9e7ae317d5bb7f27eada83aab3952cb27e245d0e3f8ab810eb277b5` |

## Result — H105 refuted (frozen S105), no KEEP

**Итог.** Правило «самая длинная серия одинаковых этажей» без ключа на 63A проходит `bounds` (0,0514 м), но на
отложенной 63B даёт **27,65 м** во всех трёх повторах — почти ровно то же, что построил агент #91 (27,67 м): шесть этажей
5,35…24,25 м против принятых 4,65…51,90 м. Значит, остановка 63B на `bounds` — не ошибка агента и не «нечитаемый
источник»: по одному источнику однозначно не выводится, какие этажи входят в «этап 1». Нужен диапазон этажей в тексте
задачи 63B (как у 63A) — это решение владельца банка, не исследование.

| Tower | Role | Selected band (pitch, storeys) | Signed face deltas vs key (xmin, ymin, zmin, xmax, ymax, zmax), m | M105 (3/3 same) | #91 baseline |
| --- | --- | --- | --- | ---: | ---: |
| 63A | tuning | 10.14…47.94 (3.15, 12) | −0.051, +0.044, −0.010, +0.027, −0.001, −0.010 | pass 0.0514 | pass 0.0442 |
| 63B | held out | 5.35…24.25 (3.15, 6) | −0.034, −0.050, +0.700, +0.200, −0.042, −27.650 | fail 27.65 | fail 27.67 |

- **Clean:** commit `41d0b413` froze contract and driver before any 63B inspection; three sequential fresh Blender 4.4
  imports + 15 native readbacks, series 238.5 s (pairs 79.3 / 80.1 / 78.8 s), status `complete`, no budget stop. Hash
  preflight/postflight and code parity to `e1f3f168` passed. Calibration 3/3: v007 pass 0.0000, v004 fail 0.1993. Row-order
  reversal gave the identical selection on both towers, 3/3.
- **Injected (6/6 each):** +0.5 m facade witness -> +1 band row, `Xmax` +0.5 m, native 0.5267 m on 63A (63B stays at its
  27.65 m maximum - the witness moves `Xmax`, not the maximum face); Floor-named witness -> selection unchanged (floor
  exclusion fires); outside-box witness -> identical selection. Synthetic rows only in memory; no model written.
- **Not measured:** an agent with a stated 63B range, any other project, BODY form/openings/package acceptance, a 63C/63D tower.
- **Post-hoc diagnosis (after the series; not a result, not used to change S105).** 63B source levels: storeys at
  `4.65 + 3.15k` (153 rows each), with two different storeys at 23.55 and 39.30 (55/54 rows), plus window rows at the +0.70
  phase. The accepted 63B range bridges those two storeys (similarity ~0.36), while the accepted 63A range stops at 47.25
  where similarity is ~0.78 and identical storeys continue to 69.3 m. The datum also differs: 63A key starts at the
  window phase (10.15, slabs at 9.45), 63B key at the slab phase (4.65, windows at 5.35). No single repetition threshold or
  phase rule reproduces both accepted ranges, so the stage-1 storey scope is a task specification, not source geometry.
- **Would change next (OBSERVE, not applied):** bank owner (#1855/#1861) adds the explicit typical-storey range and Z datum
  to the 63B task, as the 63A task has (`+4.65 .. +51.90 m` per the accepted v007 readback) — user decision because it is
  key-derived scope. Then re-run 63B practice and count the `bounds` step. Remaining XY/phase residuals after a stated
  range: S105 63B `xmax` +0.200 m with the stated band not measured.

Receipt: [`trainer_storey_band_r105/receipt.json`](trainer_storey_band_r105/receipt.json), SHA-256
`75fbddb1b0d782a14000270e8c87ed0e6e05489ab0c7073263eb623d98f6d30c`; driver Git-LF SHA-256
`1c074b42a5d90b2c42fb2d67219274d84c8d95591dabd33998a1f04f89bf1b0a`. Evidence (readbacks, dumps, logs, tuning scratch):
`G:/Мой диск/AGR-evidence/1855-r105-storey-band/SHA256SUMS.txt` (41 files, list SHA-256
`21b8412d32f9f2c7af9278ec37a5af0a9ff61e060000bf61392ae49eb89d6bfe`). Replay limited to runners with the hash-pinned Drive
inputs and Blender 4.4. Branch-only OBSERVE; no production change. Hypothesis result (refuted) is separate from review readiness.

Affected tests: `uv run pytest -q tests/tools/test_trainer.py tests/test_trainer_inspect.py -p no:cacheprovider` — 105 passed, 1 warning (no product code changed; driver imports `trainer.bounds_step` unchanged).

Repo guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 563 passed, 1 warning.

Full suite: deferred to merge batch (rule 68)
