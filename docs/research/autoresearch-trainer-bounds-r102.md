# Autoresearch #102 — source-only AIA layer filter at the trainer bounds gate

**Кратко.** Проверяем E1b из #101: убираем аннотации из габарита, но сохраняем лестницу и физический верх фасада. Проверка в OBSERVE, без пересборки объектов, изменения допусков или публикации пакетов.

## Frozen contract

- Base `d9af400c08852308f5f618c9bfc0547e067d82ce`: `docs/trainer/ledger.json` has `artifact` 3/4, `sources-dwg` 1/4. #1855/#1608 comments also identify an earlier `sources-dwg` stop (outside that denominator). #100 gets 3/3 artifact passes on stored outputs; subsequent stops tie across its direct cohort. Fresh KPP1 #99 stops at `bounds` 6/6, and held-out 63B has a separate `bounds` stop in #100. No claim that `bounds` is modal across fresh runs on all objects. Work on that KPP1 failure, not closed form research, inactive atlas fallback, #1917 prompts, #1924/#1927 A/B infrastructure, #1928 adapter, or #1866 DXF conversion.
- One candidate E1b, already disclosed as post-hoc in #101. Three new paired repeats, no candidate search. Each pair opens L03 and L01 anew, runs E1 and E1b, and makes fresh Blender readbacks of the accepted KPP1 v004 key and Artem-rejected D380 lattice. E1b filters only suffixes `-IDEN`, `-TEXT`, `-NOTE`, `-DIMS` before the unchanged r101 plan/facade extraction (including the wall window); Z floor/plan frame unchanged. The candidate computes the envelope without access to either mesh readback. Metric `M102`: native trainer `max_corner_dev_m`, median of three paired runs; report min/max paired gain. This is an envelope diagnostic, not a generated candidate FBX or a packaging pass.
- H102: E1b must pass the unchanged native 0.10 m bound on all three KPP1 repeats, with improvement >= 0.30 m over E1, and transfer to an eligible held-out building with max axis span delta <= 0.10 m (only when XY axes, parts and Z scope match). Any complete numerical miss at KPP1 refutes H102; otherwise absent transfer or calibration is inconclusive. No KEEP without active held-out transfer, distinct accepted/rejected calibration, and parity. The disclosed tuning expectation from #101 is 0.11 m, so the series can distinguish improvement from an actual pass.
- Native calibration: accepted key centroid/frame unchanged, key-vs-itself zero (identity control only, not submission); the separately read rejected FBX must score strictly worse and fail. Clean perturbation control: after applying E1b once, reapply it to both already filtered native streams; exact envelope equality and zero further removals per stream. Witness: removal is active on the real L03 and cannot leave its west error unchanged (expected absolute reduction >= 0.30 m). Native annotation geometry is preserved in E1. Injected synthetic witness: copy one `A-WALL` DXF entity with a supported bbox, shift it 2 m west of the base west extent, relabel `A-WALL-TEST-IDEN`; E1 x_min must shift >= 1.9 m; E1b bounds must be exactly invariant and removal count rise by one. Native stair ablation on E1b: east error >= 3.9 m. Log changed counts separately for L03 and L01, per variant, marking no-op inputs `not_exercised` for perturbation coverage.
- Held-out eligibility census (not used for layer tuning): independent TEC26 AC05 `gate1-v004/AC05-readback-v002.dxf`, SHA-256 `84486940c29c1bbb288486f2b62f4fb9d3d7b8addf002e3f1e0b8be846461a73`. Strict read failed (`missing ENDSEC`); recover is permitted for inventory only, not scoring. The preliminary layer-only census showed SPDS/PDF layers and no physical AIA prefix. Freeze this fixture as a negative eligibility control; no substitution after freeze, no acceptance/transfer claim. AC08 was already ruled out at #101; do not reuse it as held-out evidence. The independent eligible AIA plan+facades+accepted FBX trio was not located in the checked Drive project sources. No transfer run is budgeted on ineligible input.
- Budget: 3 confirmation pairs, 0 new candidates, 180 s start-to-finish including pre/post hashes, no new pair if less than 35 s remain; record actual wall and status independently. #101's measured pair (eight readbacks + DXFs) was 20.8 s at worst; this pair uses two readbacks and the same DXFs. If time or tools interrupt the three-pair series, report run inconclusive; the replay command has the same conditional stop and requires a fresh output folder. No editing delivered files, key geometry in the rule, test deselection, weakened tolerances, other cards' changes, or scene GUI.
- Full-manifest parity before/after: r101 `measure.py` and `manifest.json` at `d51167a2acdeda51429a3580eb9dda50cf6990ed` (Git bytes verified in replay), its five used KPP1 inputs (`l03_dxf`, `l01_dxf`, `frame`, `key`, `rejected`), pinned AC05 bytes, Blender exe SHA-256 `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5`, unchanged trainer/readback/runner and lockfile at base (Git checkout line endings normalized for code). Use Python 3.14.7, ezdxf 1.4.3, headless Blender 5.1. No readback cache is shared between pairs. Store exact variant and hashes with the receipt.

## Replay

From the published branch, with the prior #101 ref available (if necessary `git fetch origin research/autoresearch-standing-101`):

```bash
uv run --frozen python docs/research/trainer_bounds_r102/measure.py --out .r102-replay
```

The output directory must not exist. Replay is limited to hosts with the pinned Drive inputs and Blender installation. The command never writes into those fixtures. Full suite: deferred to merge batch (rule 68).

Affected tests: `uv run --frozen pytest -q --basetemp=.venv/pytest-r102 tests/tools/test_trainer.py tests/test_trainer_inspect.py` — 105 passed, 1 pytest temporary-directory warning, 0 failed.

## Result — OBSERVE, no KEEP

**Гипотеза H102 опровергнута.** Фильтр аннотаций дал стабильное улучшение, но не прошёл штатный `bounds`: осталось 110 мм на западной грани при допуске 100 мм. На другом объекте перенос не измерен: AC05 не прошёл проверку пригодности. Пакеты, валидатор и правила производства не менялись; PR нет.

Three complete pairs, wall 82.848 s (26.395 / 25.707 / 23.990 s per pair), no budget stop. All pairs agree; input SHA-256 pre/post parity passed. Exact driver committed before the series at `bb50475c`; contract at `c5af20e1`. Git-LF SHA-256 of [`receipt.json`](trainer_bounds_r102/receipt.json): `78616501557735a0fffd90b5eb342fbf1cae4a333a00d2fb1c3bbeb3066cb09f`.

| Native KPP1 `bounds` | Median deviation | Passes at 0.10 m |
| --- | ---: | ---: |
| E1 | 0.5396 m | 0/3 |
| E1b | 0.1100 m | 0/3 |
| Accepted key vs itself (identity only) | 0.0000 m | 3/3 |
| Artem-rejected D380 lattice vs key | 3.8005 m | 0/3 |

Paired gain: median 0.4296 m, range [0.4296, 0.4296]. Signed west error moved from −0.5396 m to +0.1100 m. Native layer trigger: 806 removals on L03 and 660 on L01; L03 removed 54 `A-WALL-____-IDEN` from the 394 entities with boxable wall bounds in E1's envelope. The clean reapplication produced identical envelopes but removed zero entities on either sheet: active collateral change on the clean streams **not measured**. With one synthetic plan annotation, E1 moved west by 2.0000 m, E1b stayed exactly invariant and its L03 removal count rose by one; L01 unchanged, **not measured** for injection. Removing stairs excluded 79 L03 plan members and yielded an east error of −4.0005 m, with no L01 change.

Held-out eligibility: AC05 had 25 recovered layers, zero physical AIA prefix matches and one DXF recovery fix after strict `missing ENDSEC` refusal. No AC05 FBX comparison, no second independently accepted KPP1 submission, no fresh-agent behaviour, no full package validation: **not measured**. Evidence is the branch receipt plus prior external fixture hashes, not copied customer sources or replacement packages.

Next: (1) get an independent paired plan/facade AIA export and an accepted same-scope FBX; run strict source eligibility before comparing envelopes, (2) test a source-bound west facade post projection on KPP1, then check it on that independently held-out building, with no key-derived offset or relaxed tolerance.
