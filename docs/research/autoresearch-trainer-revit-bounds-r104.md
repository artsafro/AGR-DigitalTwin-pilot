# Autoresearch #104 — source upper-face reach in the Revit route (OBSERVE)

**Кратко.** Проверяем, есть ли в Revit FBX площадки 63 верхняя отметка элемента, которая могла бы объяснить верхнюю грань принятого BODY. Это проверка одного способа выбрать отметку, не новый BODY и не изменение банка.

## Frozen contract (before driver and measurements)

- Ledger at `1140d9b417462ac4190e791b8c66b6970415d4ad:docs/trainer/ledger.json` (Git blob bytes SHA-256 `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7`): `artifact` 3/4, `sources-dwg` 1/4. #1855/#1608 comments and merged #1859/#1860 inspected; the named research heads are no longer advertised. #100 cleared `artifact` on stored output, not on fresh runs. #91/100: 63B first native failure `bounds`, 27.67 m, built six floors to 24.23 m vs accepted top 51.90 m. 63A passes `bounds` but lacks transfer to B. Continue the #103 per-face reachability idea using the existing Revit dump and native trainer bounds check, not a new geometry/checking harness. Not doing #1924/#1927 A/B, #1928 adapter, #1866 DWG, the closed form topic, or fallback atlas.
- **H104**: for both towers a readable source object fully contained by the already approved `boxes63.json` has an upper Z within 0.10 m of that tower's accepted upper face, without a learned offset. Metric `M104` = minimum absolute top-Z delta, in metres, among such objects. One variant only: strict containment in all three axes, object top `z[1]` from the existing native dump. Whole-object AABB only, not roof classification, no arbitrary interior cut/vertex, no tolerance on containment. Report the nearest source row/name, count and six native coordinate deltas of the existing #91 submission. Baseline = #91 top delta (built vs accepted); candidate is an **oracle** allowing any eligible top, not a key-free selector. `M104 > 0.10` refutes only this variant; `M104 <= 0.10` confirms reachability, not that the object belongs to the architectural scope or that the agent could select it without the key. Report dump precision (0.0001 m); +/-0.0001 m around 0.10 is inconclusive for the decision.
- Fixtures: tuning 63A (positive native passage control; explicit source-world task and typical floor range), held-out 63B (never used to choose H104's rule; same site/export, not independent project). Use 63B accepted v007 and rejected v004 to calibrate **unchanged native bounds** first: v007 relative to itself must score 0/pass, v004 must be strictly worse and fail. Not a validation of any wider quality or form metric. The approved coarse tower boxes give XY and Z in source-world metres; compare only Z in that datum. Calibration does not infer floor scope. Native transforms/units recorded as read back; if accepted XY centroid falls outside the approved XY tower box or impossible bounds are reported, mark the oracle inconclusive, do not fit anything. Key is evaluated only by the diagnostic, not supplied to an agent or applied to the source.
- Positive injected control per fixture: append one explicitly synthetic eligible AABB centred in the tower box in XY, with its top exactly at the key Z (lower 0.01 m); reach becomes 0. Same witness with XY shifted outside the box must not affect reach. Count added and selected rows; do not count a pre-existing equal top as a changed score. Clean idempotence: reverse source row order (retain stable row identities) and require identical count, nearest row and score; separately report when the original #91 baseline already passes (not an effect of H104). No writes to input models.
- 3 sequential fresh headless source imports and native readbacks; median and min/max paired delta, wall time separately. Confirm budget 3 repeats, zero new variants, 360 s measurement cap (max 120 s for the first complete pair; proceed only if its time * 3 fits the cap, and only if remaining owner time fits). Record failed/incomplete pair and no retries as evidence for the series; budget stop is inconclusive, not no-reach. KEEP requires a key-free source selector measured on both eligible fixtures, new native BODY parity, and no relaxed tolerance; this oracle cannot KEEP. No model/DCC live edits, no modification to trainer, production sources, approved packages, thresholds, scoring rule, work of other cards, or post-hoc filter/fixture changes.
- Replay from the published branch: `uv run python docs/research/trainer_revit_bounds_r104/replay.py NEW_WORKSPACE_OUTPUT`; `NEW_WORKSPACE_OUTPUT` must not exist. Blender 4.4 CLI via a read-only staged copy in a new worktree subdirectory per repeat (no live Max). Side products ignored/untracked; only contract, driver, small receipt committed.

### Full input preflight

SHA-256 verified on each original before and after the series and on each staged copy before each import. Repo scorer/importer inputs pinned byte-for-byte to the contract base above (`tools/trainer/trainer.py`, `tools/blender/fbx_readback.py`, `tools/methods/body/revit_fbx_dump_blender.py`, `src/dt_ai/core/blender_runner.py`, and any direct scorer dependencies). On Windows normalize only Git text for this parity check. Candidate/replay source is pinned by the published commit.

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

## Result — H104 confirmed for upper-face reach only; no KEEP

**Итог.** В исходном Revit FBX есть верхняя отметка **+51,90 м** внутри бокса 63B (элемент `21997400`),
во всех трёх свежих чтениях. Прошлая сборка остановилась на +24,23 м. Но выбор ближайшей отметки сравнивался
с ключом; он не доказывает, что агент выберет правильные этажи без ключа. Даже идеальная правка только верхней
грани оставила бы у 63B ошибки **0,680 м по низу и 0,121 м по Xmax**, обе выше допуска 0,10 м. `bounds` не пройден;
ничего не меняли в банке, валидаторе и моделях.

| Fixture | Eligible rows | Nearest source top | Baseline top delta | M104 median (min–max) | Paired gain median (min–max) | Native #91 bounds |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 63A, tuning | 9497 | 47.9500 m, row 8561 `5600629` | 0 m | ≤0.0001 m (same all three) | −0.0000107 m (same all three; dump precision) | pass, 0.0442 m |
| 63B, held out | 5166 | 51.9000 m, row 22079 `21997400` | 27.670002 m | ≤0.0001 m (same all three) | +27.6700005 m (same all three) | fail, 27.6700 m |

- **Clean:** three sequential Blender 4.4.0 imports of the source FBX (27,629 readable mesh rows in each, source-world metres) and 15 native model readbacks. Complete wall 267.63 s, pairs 92.50 / 92.62 / 82.19 s, no budget stop. Input and code hash preflight passed; staged hash parity and original postflight passed. Ordered vs reversed source census gave the same nearest row and count (6/6). Native accepted v007 pass/0.0000 m vs rejected v004 fail/0.1993 m in 3/3. v004 shares v007's top Z: **upper Z alone does not separate accepted/rejected versions**.
- **Injected:** eligible synthetic witness: +1 selected row and delta 0 in 6/6; outside-box witness: +1 input but 0 selected change and unchanged score in 6/6. This exercises containment, not architectural membership. 63A was already passing native bounds before the experiment.
- **Not measured:** key-free choice of floor range, transfer to an independent project, native passage for a rebuilt 63B, or any shape/material/package acceptance. The largest unchanged face delta (0.6800 m) is an arithmetic counterfactual, not a candidate readback. On another host a slow import may hit the frozen cap; preserve partial evidence and report the run inconclusive rather than shortening the series.
- **Would change next:** test a key-free typical-storey band proposal from named Revit source levels/objects (measure both Z boundaries and all six native faces); hand any task-scope/approval question to the bank owner. Do not use the published accepted floor range as a tuning input. Then test on an independent source/export pair.

Receipt: [`trainer_revit_bounds_r104/receipt.json`](trainer_revit_bounds_r104/receipt.json), Git-LF SHA-256 `302a6c0b198e5e3d172515225d12ae232a546178fd409a15136243806c1ccfce`; driver Git-LF SHA-256 `711f09fc6c719b3d9bdae51634b1f853acd50b8065454936fcacbbf01ef8752a`. Replay limited to runners with access to the hash-pinned Drive paths and the pinned Blender installation. Branch-only OBSERVE; no production change or PR. Review readiness is separate from the confirmed narrow hypothesis.

Affected tests: `uv run pytest -q tests/tools/test_trainer.py tests/test_trainer_inspect.py tests/test_openings_from_revit_fbx_1784.py tests/qa/test_blender_runner.py tests/qa/test_topology.py` — 351 passed, 1 deselected (configured), 1 warning.

Repo guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 563 passed, 1 warning.

Full suite: deferred to merge batch (rule 68)
