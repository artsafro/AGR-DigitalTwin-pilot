# Standing #92 — transfer the Revit artifact route to 63C (OBSERVE)

**Кратко.** Перенос офлайн-маршрута на отложенную башню 63C подтверждён: свежий FBX собрался и прочитался 3/3 как с выравниванием косяков, так и без него. На 63C правило ни разу не сработало, поэтому прирост и влияние активной правки на 63C не измерены. На 63A результат вырос с 0/3 до 3/3: по 15 срабатываний на прогон. Холодный запуск агента и готовность модели к сдаче не проверялись. Код продукта и банк не менялись, PR нет.

## Frozen contract

Ledger at `cf4efcbba169541d7163a83f7b28d054f0649db1:docs/trainer/ledger.json` has four Codex rows: `artifact` 3/4, `sources-dwg` 1/4. This counts scoring/ledger labels, not four runs stopped at the same execution stage. #1880 owns DWG, #1901 tower-map discovery, #1859 the live-practice isolation gap. Atlas fallback is inactive and form research stays closed. #91 proved the offline `artifact` route on 63A/63B; this experiment tests transfer, not a fresh-agent run.

**H92.** The exact #90 frozen keys and alignment rule, followed by the unchanged #91 builder/scorer interfaces, produce a non-key binary FBX that reads back from each of three new Revit crops of 63C (held out from route tuning, same site). 63A is the known positive alignment witness and existing control. 63C's stage-1 v002 is accepted per D355/D356; the main bank entry is incomplete, so the archived v002 is bound for evaluation only, not added to the bank or passed to the builder.

**M92.** Per paired fresh crop, 1 iff `agr body` emits the FBX and unchanged `tools.trainer.trainer.score` reports both `artifact` and `readback` pass; 0 for deterministic plan/build refusal or measured artifact/readback fail; runtime/scorer error, missing key or absent measurement is not measured. Baseline = exact same crop/keys without alignment. Candidate = #90 aligned arm unchanged. Require candidate 3/3 on both, 63A baseline 0/3 with positive alignment in all repetitions, and no negative paired deltas on 63C. Median of three paired deltas per tower with min/max. Report any 63C 3/3 tie as transfer feasibility, not an alignment gain; zero changed counts are `not_exercised`. Record each arm's changed count and hashes. Score diagnostics after readback are evaluation only, not a new form experiment.

**Bounded controls.** Run the accepted 63C v002 against itself with scorer `allow_key` (readback/calibration control only, excluded from M92); rejected 63B v004 against accepted 63B v007 must score strictly below the accepted control (prior observed bounds fail); identical-key submission without `allow_key` must fail `artifact`; fresh output truncated to its 23-byte binary header must not pass `readback` even if `artifact` passes. No real rejected file is assumed to lack an FBX header. Input parity via full native SHA-256 pre/post; no changing sources, records, thresholds, other cards' files or delivered assets, no live Max, no test deselection. An evaluation control is not evidence of collateral invariance unless the candidate rule runs on it.

**Budget.** One confirmation series, zero new candidates; 3 paired crops on each tower, fresh build/readback for each arm, four controls. #91 measured a 7 s build/score probe and 302.6 s for this scale of series. On first two-tower pair, bound total run to five times elapsed, 480 s hard cap; no shortening series or keeping based on partial results. Timed-out replay requires a new output path and authorized time. Transfer only, not delivery, source isolation, blind practice, independent-site generalization, or package acceptance. Refuted on repeated deterministic candidate failure; incomplete measurement otherwise inconclusive. No product KEEP or PR on this OBSERVE lane.

**Replay.** `uv run --frozen python docs/research/trainer-artifact-transfer-r92/replay.py tmp/r92-NEW` from this branch, new dir. Main builder/scorer code and bank pinned at `cf4efcbb`; crop/align code pinned through `171a77a29938b688def45cfb71633c433f0580c0`, its #89 and #88 inputs, and the exact harness revision. Native inputs are fully listed in `replay.py`: site FBX, tower box, Blender 5.1.2 (`1e6624af…58fa5`), G22 plan for the nested #90 control, 63A v005 and 63C v002 keys, 63B v004/v007. 63C key is `G:/Мой диск/AGR-evidence/1619-body-training/tower-C/v002/63C_stage1_v002_QUAD.fbx`, SHA-256 `462ba61b2c379de53a72667635fd0714703764b2409407cc67ff28d8684de1da`. Replay limited to hosts with these pinned assets and offline Blender.

## Result — H92 confirmed for offline artifact transfer; no production KEEP

Status `finished`, 255.235 s wall, first two-tower crop/plan pair 57.273 s (derived cap 286.365 s). Driver ran with base `cf4efcbb` before the freeze commit was created; the measured driver bytes match `1ad21b43` (SHA-256 `23c7c9d119c5159dbc0744922600e98f8025c8105224273be7d9f5f1550493f4`). The #89 invocation substitutes only the A/B tower loop for A/C; the aligned variant is the byte-identical #90 `candidate.py`. Native input hashes matched 8/8 before and after; raw plan bytes matched across arms for each crop before alignment (6/6).

| Fixture | Baseline M92 | Aligned M92 | Paired gain median [min, max] | Jamb changes, baseline → aligned |
| --- | ---: | ---: | --- | --- |
| 63A, route witness | 0/3 | 3/3 | +1 [+1, +1] | 0 → 15 each; exercised |
| 63C, held out from route tuning | 3/3 | 3/3 | 0 [0, 0] | 0 → 0 each; `not_exercised` |

The 63A baseline fails at `artifact` (the builder prints `ring not closed`); the aligned 63A and both 63C arms stop at `form`. This is only a downstream scorer status, not a new form study. 63A and 63C have distinct mesh bounds and polygon counts (5940 vs 4246), with matching built/key vertical extents per tower. Fresh crop hashes differ across repetitions; this was not rescoring frozen files.

- **Native calibration:** evaluation-only 63C v002 self-score 0.8333 (readback passes; VLM not run); rejected 63B v004 0.3333 against its own v007 key (`bounds` fails). Both real fixtures pass the artifact/readback metric alone. The scorer output as a whole distinguishes them; M92 is not a quality rank.
- **Injected controls:** exact key submitted as a build is refused at `artifact`; 23-byte truncated binary passes the header-based `artifact` step but fails `readback`. Both are excluded from M92.
- **Not measured:** an active alignment on 63C, independent-site transfer, live cold agent artifact rate, VLM and delivery acceptance. The 63C v002 key matches the archive manifest; it was read only by evaluation, not by the cropper, adapter or builder.

Would-change: hand the owner of #1855 the source-to-FBX route and make the near-corner alignment conditional on measured triggers; use fresh practice only after verifying filesystem isolation (#1859). Separately locate a natural near-corner trigger on another Revit site before claiming active-rule transfer.

Receipt: [`trainer-artifact-transfer-r92/receipt.json`](trainer-artifact-transfer-r92/receipt.json), SHA-256 `f0b2025be8e3a391cae81b193c5e82c95dccd6c8292e098e9e9aa1e9fd17cdf1`. Generated plans, FBXs and readbacks: `G:/Мой диск/AGR-evidence/1855-r92-artifact-transfer/`; 85 entries verified against `SHA256SUMS.txt`, SHA-256 `372d3b60944cb7fcd6d5b6787a2b5f5595c0251e550f7cc74af9efe3666d3f30`. Large crop arrays stay uncommitted and can be regenerated from the pinned inputs.

Affected tests: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL -u PYTEST_ADDOPTS uv run --frozen pytest -q tests/tools/test_trainer.py tests/test_body_lattice_1736.py tests/test_trainer_inspect.py tests/test_agr_cli.py` — 278 passed. Initial default guard run hit Windows shared basetemp `WinError 183`; `PYTEST_ADDOPTS='--basetemp=C:/x/agr-r92-4084bc30-guards' bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 559 passed, `repo_guards: GREEN`.

Full suite: deferred to merge batch (rule 68).
