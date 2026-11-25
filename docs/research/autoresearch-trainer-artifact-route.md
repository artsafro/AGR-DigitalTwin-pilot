# Standing #91 — trainer `artifact` through the Revit route (OBSERVE)

## Кратко (по-русски)

Заполняется после замеров (см. «Result»).

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
