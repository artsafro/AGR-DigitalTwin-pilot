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

_Not measured yet._
