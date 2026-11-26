# Autoresearch #107 — railings out of the stated-band selector vs the trainer bounds gate (OBSERVE)

**Кратко.** #106 показал: явная полоса этажей убирает ошибку по Z на 63B, но в плане остаётся 2,2348 м, и все четыре
XY-экстремума дают строки `Ограждение Стеклянное …`. Проверяем ровно один вариант: тот же селектор #106 без строк
ограждений. Это ретроспективная проверка механизма на готовом импорте, не новая попытка агента и не правка банка.

## Frozen contract (before any variant code or measurement)

- **Ledger / focus.** `7762dcfe2e78219155461bb633faaca2015e259b:docs/trainer/ledger.json` (= origin/main at card start):
  historical first failure `artifact` 3/4, `sources-dwg` 1/4. #100 cleared `artifact` on stored outputs; fresh runs stop at
  `bounds` (#99 KPP1 6/6, #105/#106 63B). Continue #106 next target 1. Not duplicated: KPP1 source scope (bank owner #1855/#1861),
  #1866 DWG integrity, #1928 G22 adapter, #1917 prompts, #1924/#1927 A/B harness; form research closed; atlas fallback inactive.
- **Variant S107, exactly one:** S106 (`origin/research/autoresearch-standing-106@821492c4`, `stated()`): stated floor band, same
  approved tower box (`contained`), `z0` in `[lo-1e-6, hi-1e-6)`, non-Floor (`Перекрытие` prefix) filter, union of XY bounds,
  Z = stated endpoints — **plus** drop rows whose name starts with `Ограждение` (Revit railing family prefix).
  Rationale fixed before measuring: the 63A bank task scopes the body as "the outer facade envelope with the openings only (no
  windows, glass, capsules or AC boxes)"; a railing is not envelope, and [D087] models terrace glass railings as a separate
  20 mm plate pattern. Prefix match only, no other tokens, no key/scorer input to row selection, no guessed offsets.
  Synthetic boxes go to the unchanged score step; no FBX is rebuilt.
- **Scope inputs (unchanged from #106):** 63A 10.15…47.95 m (`docs/trainer/etalons.json`), 63B 4.65…51.90 m (v002 historical
  witness, `jobs/POLY63-B/REPORT.md`), both read at the immutable revision above.
- **Tuning disclosure.** The railing hypothesis comes from the #106 63B readback, so **63B is tuning-contaminated** for this
  rule, not held-out. 63A is a same-site control (the rule must not break its pass). No independent project/etalon exists in
  the bank for this step: **transfer to an independent etalon is not measured**.
- **Metric M107:** unchanged `tools.trainer.trainer.bounds_step(...).max_corner_dev_m` (lower better), native pass <= 0.10 m.
  Per tower and pair compare S106 vs S107 on the same fresh source import: median of 3, min/max paired gain, signed six-face
  deltas vs key, names of the rows that set each S107 XY extremum. Retained product changes: none (OBSERVE).
- **Verdict:** confirmed only if 63A passes 3/3 and 63B passes 3/3 with every control green; refuted only if 63A passes 3/3
  and 63B fails 3/3 with every control green; otherwise inconclusive. Expected direction: 63B S107 <= S106 (railings only
  shrink the union); 63A |change| <= 0.05 m and still pass.
- **Calibration first in every pair (reused runner):** v007 accepted vs itself = 0 / pass; rejected v004 vs v007 fails and is
  worse. S106 parity: 63A pass, 63B fail (as in #106).
- **Paired controls per tower (all must be exercised for a verdict):**
  1. Row order reversed: identical S107 selection (0 changed IDs).
  2. Rule fires (positive trigger witness on real data): removed IDs = S106 ids − S107 ids, all names start with
     `Ограждение`, S107 ⊆ S106. Count per tower; a tower with 0 removed rows is reported `not_exercised` (63A collateral then
     not measured), not as a pass.
  3. Headroom preflight + in-box witness: for the S107 selection compute outward headroom to the tower box for faces in fixed
     order xmax, xmin, ymax, ymin; pick the first with headroom >= 0.60 m. Inject one synthetic non-Floor non-railing row in
     the band that extends that face outward by 0.50 m: exactly one ID added, only that face moves by 0.50 m (1e-9), native
     fails at >= 0.40 m. No face with headroom -> `not_exercised` -> inconclusive (no post-hoc substitution).
  4. Railing relabel of the same row (`Ограждение SYNTHETIC`): not selected, selection equals clean S107 exactly.
  5. Shift band +0.25 m: both Z faces move exactly +0.25 m, native fails at >= 0.24 m; record changed IDs.
  6. Absent band: no selection, never fall back to S105/S106.
- **Budget:** exactly three fresh sequential import/readback pairs with the reused #105 runner (420 s series cap, 140 s per
  pair, first pair x3 check), no new candidate rounds. Incomplete pair or budget stop -> inconclusive; wall time and run
  status recorded separately. No Max, no rendering, no edits to trainer, scorer, bank tasks, accepted/rejected files or other
  cards' files. Forbidden: weakening the 0.10 m threshold, deselecting tests, editing delivered packages.
- **Replay:** `uv run python docs/research/trainer_railing_r107/replay.py tmp/r107-NEW <full variant commit>` (new output
  path). The runner is read as exact Git blobs from `95ae5adb1bf907e927b994296c51ad321edd18b7`
  (`docs/research/trainer_storey_band_r105/replay.py` + its manifest, on `origin/research/autoresearch-standing-105`): it
  pre/post-checks the eight pinned input SHA-256 (Drive fixtures + Blender 4.4), pins imported code against `e1f3f168`, stages
  copies and runs registered native readbacks. The wrapper refuses to run if its own file differs from the passed commit or if
  ledger/bank/report differ from `7762dcfe`. Replay limited to runners with the pinned Drive fixtures and Blender 4.4.

## Result

**Итог.** Исключение ограждений сократило ошибку 63B с **2,2348 м до 0,2002 м** (3/3 одинаково), но `bounds` по-прежнему
не пройден при допуске 0,10 м. Остаток — одна грань: Xmax +0,2002 м, её задают стены `Базовая стена Вентфасад 250 250 к…`;
остальные пять граней в пределах 0,05 м. На 63A в полосе нет ни одной строки `Ограждение`, правило там не срабатывает, и
побочный эффект на принятой башне **не измерен** — по замороженному правилу итог H107 **inconclusive** (63B: fail 3/3, но
контроль 63A `not_exercised`). KEEP и PR с изменением продукта нет; модели, банк, скорер и пороги не тронуты.

| Tower | S106 median, m | S107 median, m | Paired gain min–max, m | S107 signed face deltas vs key (xmin, ymin, zmin, xmax, ymax, zmax), m |
| --- | ---: | ---: | ---: | --- |
| 63A same-site control | 0.0514 | 0.0514 | 0.0000–0.0000 | −0.0514, +0.0438, 0.0000, +0.0267, −0.0009, 0.0000 |
| 63B tuning-contaminated | 2.2348 | 0.2002 | 2.0346–2.0346 | −0.0342, −0.0499, 0.0000, +0.2002, −0.0416, 0.0000 |

- **Run status `complete`:** three fresh paired imports (72.74 / 73.83 / 72.01 s; 218.90 s series wall, cap 420 s). Hash and
  code-parity preflight/postflight passed. Contract frozen at `7718f667`, variant at `4795d109` before measurement.
  The reused runner prints a legacy `m105_*` summary (= S107 values); the sealed `summary` uses S106/S107 names.
- **Clean:** accepted 63B v007 0.0000 m, rejected v004 0.1993 m, 3/3. S106 parity 63A pass / 63B fail 3/3. Row reversal
  0 changed IDs; absent band refuses on both towers. Selected IDs 63A 4,702 (= S106), 63B 4,178 (S106 4,241).
- **Injected, exercised (both towers, 3/3):** headroom preflight picked `xmax` (63A 2.011 m, 63B 2.044 m); the in-box witness
  was added once and moved only Xmax by +0.50 m, native fail; relabelled `Ограждение SYNTHETIC` it was dropped and the clean
  selection restored exactly (positive trigger witness of the rule). +0.25 m band shift moved both Z faces by exactly 0.25 m
  (222 / 262 changed IDs), native fail.
- **Rule on real data:** 63B 63 removed rows, all `Ограждение Стеклянное огражд_*`. 63A 0 removed rows → **not measured**
  (no accepted control on which the rule fires); this is the only control that blocks a formal verdict.
- **Not measured:** fresh agent builds, an independent project/etalon, topology/form, package acceptance. 63B was the source
  of the hypothesis, so its gain is not transfer evidence.

[Native receipt](trainer_railing_r107/receipt.json), Git-LF SHA-256 `759e94aea0ab11b56894ea8d41242aa5bd1fcd6266ad3096a3687adb68362f85`.
Readback JSON/logs: `G:/Мой диск/AGR-evidence/1855-r107-railing/` (`SHA256SUMS.txt` sha256
`4caefa0aec146af207c441252dc36cfb0aa46b366a748c1bded007e20c24dd0d`, 37 files). No binaries committed. Replay limited to
runners with the pinned Drive fixtures and Blender 4.4. Review readiness is independent of H107.

Affected tests: `uv run pytest -q tests/research/test_trainer_railing_r107.py tests/tools/test_trainer.py tests/test_trainer_inspect.py -p no:cacheprovider` — 107 passed, 1 warning. Pre-implementation run failed at collection (module absent), then 2/2 new tests passed.

Repo guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN, 563 passed, 1 warning.

Full suite: deferred to merge batch (rule 68)
