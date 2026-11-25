# Standing #91 — trainer `artifact` through the Revit route (OBSERVE)

## Кратко (по-русски)

Гипотеза H91 **подтверждена для офлайн-маршрута** (не для свежего агента). Маршрут #90 (кроп Revit + ключи окон +
выравнивание косяка по углу) через неизменённый `agr body` даёт FBX, который проходит шаг тренажёра `файл`:
63A 3/3, отложенная 63B 3/3; без выравнивания 0/3 и 0/3 (builder отказывает: «ring not closed»). Следующий провал:
63A — `форма` (p95 0,217 м, max 1,38 м при допуске 0,05/0,30), 63B — `габариты` (27,67 м: построено 6 этажей
5,33…24,23 м, у ключа v007 4,65…51,90 м). Контроль: принятый план 63A v005 через тот же `agr body` воспроизводит
ключ точно (форма 0,0 м), G22 принятый — тоже (0,0002 м); отклонённая 63B v004 по-прежнему проваливает `габариты`.
Значит, разрыв после `файла` — в содержании плана из Revit (контур 63A, высота/этажность 63B), а не в builder или
оценщике. Изменений кода нет, PR не нужен для продукта; предложение — владельцу #1855.

## Frozen contract (written before the series; probe pair only)

Focus override (#1855): ledger `46e9b5d8:docs/trainer/ledger.json` has 4 rows, first failing step `artifact` 3/4
(KPP1, G22, 63A), `sources-dwg` 1/4 (owned by #1874/#1880). Owners skipped: Gate 1 practice #81/#1889 (merged),
tower map #1901, isolation #1859/#1877, bank #1861; form research closed; atlas fallback inactive (ledger rows
exist). #87-#90 removed the route stops one by one up to a valid BodyPlan (#90, branch-only,
`research/autoresearch-standing-90@171a77a29938b688def45cfb71633c433f0580c0`); #90 left `artifact` (FBX) **not measured**.

**Question.** Does the #90 route (pinned Revit crop + `keys63.json` + jamb/corner alignment) feed the unchanged
production builder `agr body` to an FBX that passes the trainer scorer's `artifact` step against Artem's key — on 63A
(tuning) and on held-out 63B — and which step fails first after it?

**M91** = per tower, number of 3 fresh runs whose plan -> `uv run --frozen agr body PLAN NEW` -> `uv run --frozen agr trainer score
<etalon> --built body.fbx --out NEW.json` reports `steps.artifact.status == pass`. Secondary, recorded per run, never tuned:
`first_failing_step`, `score`, `bounds.max_corner_dev_m`, `form.p95_m`/`max_m`, polygon counts.

**Arms** (same fresh crop per repetition, produced by the pinned #90 replay
`171a77a2:docs/research/trainer-revit-jamb-r90/replay.py`, executed from an extracted copy, new output dir):
- `baseline` = #90 `baseline.json` (explicit keys, no alignment) — expected 0/3 (ring closure refuses, no FBX);
- `aligned` = #90 `aligned.json` — sole variant, no new candidate, no adaptive tuning.

**Fixtures.** 63A `63a-stage1` (tuning for #87-#90 rules), 63B `63b-stage1` (`split: held_out` in the bank; same site,
not blind - the #90 rule was frozen on 63A). Builder/scorer code = this branch head = `origin/main 46e9b5d8` (unchanged).
Blender 5.1.2 (`TWINQA_BLENDER`, exe SHA-256 `1e6624af…58fa5`, checked by the #90 replay).

**Calibration (requirement 3).** The scorer is already calibrated 5/5 (`docs/trainer/ETALONS.md`, r2): rejected
63B v004/v005/v006 fail at `bounds`. Re-run here once: rejected `63b-stage1/v004.fbx`
(SHA-256 `6d22c572…f26ae`) must fail before `form`; accepted key scored as built is not repeated (tautological).

**Controls (read-only, hash-pinned, evaluation only - never inputs to a rule):**
- `ceiling-63A`: Artem's accepted plan `G:/Мой диск/AGR-evidence/1619-body-training/tower-A/v005/floor_v005.json`
  (SHA-256 `6f9c6d143d18febc7033f848505859bd2f50bd611c12f1f8147d1822eb6a7d66`) -> `agr body` -> score vs 63A key. Tells
  whether the route builder can reproduce the key at all (the next-step gap is then the plan, not the builder).
- `g22-accepted`: `floor_k2_v002.json` (SHA-256 `6a659916…a833f9`) -> `agr body` -> score vs `g22-k2-stage1` key
  (collateral control: accepted plan of another site through the same builder/scorer).
- Positive trigger witness: the #90 aligned plans (15/7 changed jambs per run). Perturbation = `baseline` arm
  (ring break at 0.1 mm); expected direction artifact pass -> fail.
- 63B ceiling: accepted 63B plan not located -> **not measured**.

**Keep threshold (hypothesis H91).** `aligned` 3/3 and `baseline` 0/3 on both towers, all input hashes unchanged
pre/post, calibration rejected v004 still fails. Then H91 confirmed for the offline route; else refuted. Missing
measurements -> inconclusive. Even when confirmed this is NOT fresh-agent `artifact` passage (no practice run),
not architectural acceptance and not a production change; would-change goes to the #1855 owner as a PR.

**Budget / stop.** Probe pair (63A-1 aligned from #90 scratch, not part of the series): `agr body` 2 s + score 5 s.
#90 series 244 s. Core series = 1 crop replay + 12 builds + 12 scores + 3 controls; stop at 1800 s wall
(budget stop -> inconclusive, exact next command published). One confirmation series, zero additional candidates.

**Forbidden.** Editing `tools/`, `TOL`, etalons/keys/ledger, delivered packages or other cards' files; deselecting
tests; rescoring frozen #90 plans as the series (the probe is labelled probe).

**Replay.** `uv run --frozen python docs/research/trainer-artifact-r91/replay.py C:/x/<NEW>` (new dir; needs the pinned
bank keys, source FBX and Blender 5.1.2 on this PC - replay limited). Receipt: `docs/research/trainer-artifact-r91/receipt.json`.

## Result — H91 CONFIRMED for the offline route; no production KEEP

Series `C:/x/ev_t29/r91-series`, status `finished`, wall 302.6 s (pinned #90 crop replay 207.9 s), harness revision
`85cbb881303171341a082ce6fe3ff96d9e1a4c80`, all 6 pinned inputs unchanged pre/post.

| Tower | Arm | artifact pass | first failing step (3 runs) | score | bounds dev, m | form p95 / max, m | polygons (key) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 63A (tuning) | baseline | 0/3 | artifact ×3 (`ring not closed` s=44.565) | 0.0 | — | — | — |
| 63A (tuning) | aligned | **3/3** | form ×3 | 0.6667 | 0.0442 | 0.217 / 1.381 | 5940 (4560) |
| 63B (held out) | baseline | 0/3 | artifact ×3 (`ring not closed` s=17.554) | 0.0 | — | — | — |
| 63B (held out) | aligned | **3/3** | bounds ×3 | 0.5 | 27.67 | 24.99 / 27.68 | 3504 (13644) |

Paired gain (aligned − baseline, artifact) median 1 (range 1–1) on each tower. Per-run plan/FBX SHA-256 differ
(fresh crops, FBX timestamps); all metric values are identical across the 3 repetitions.

Controls: `ceiling-63A` (Artem's accepted plan v005 -> `agr body`) first non-pass `vlm` (not run), form p95 0.0 m,
bounds 0.0 m — the builder reproduces the key; `g22-accepted` same, form p95 0.0001 m. Calibration: rejected 63B v004
still fails at `bounds` (score 0.3333) — the 63B cold route (0.5) scores between rejected (0.333) and accepted (0.833).

Diagnosis of the next stop (observed, not tuned): 63B built z 5.33–24.23 m (6 floors, step 3.15), key v007 z 4.65–51.90 m;
the 63B bank task text gives no floor range while 63A's does (+10.15..+47.95, 12 floors), and the #89 adapter takes the
floor count from the crop. 63A bounds pass (0.044 m); its form gap is plan content (built 5940 vs key 4560 faces,
max 1.38 m) since the accepted plan rebuilds exactly.

Not measured: fresh-agent `artifact` passage (no practice run), `vlm`, opening fidelity per window, 63B ceiling
(accepted 63B plan not located). This is not a delivery or a production change.

Would-change (OBSERVE, to the #1855 owner): carry the #90 alignment (or an equivalent adapter fix) into the Revit route
so a cold run can reach `artifact`; for 63B give the floor range in the bank task text or derive it from the source
levels before claiming `bounds`.

Evidence: `G:/Мой диск/AGR-evidence/1855-r91-artifact-route/` (FBX, scores, receipts), `SHA256SUMS.txt` SHA-256
`7e35e3a3d6a2cd09fe89ef5cc918090392c5cd2c4e832d532ab06bcd6ad019cb`. Receipt in git:
[`trainer-artifact-r91/receipt.json`](trainer-artifact-r91/receipt.json). Replay limited (pinned bank keys, source FBX,
Blender 5.1.2 on this PC): `uv run --frozen python docs/research/trainer-artifact-r91/replay.py C:/x/<NEW>`.
Receipt SHA-256 `ede3569747c661c07bb6c73a633ffcf8fb8031f00efca83484e22b2f5f9485f3`.

Affected tests: `uv run --frozen pytest -q tests/tools/test_trainer.py` — 73 passed (scorer used, unchanged).
`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 559 passed, `repo_guards: GREEN`.

Full suite: deferred to merge batch (rule 68).
