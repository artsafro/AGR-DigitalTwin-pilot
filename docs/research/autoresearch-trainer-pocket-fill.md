# Autoresearch #117 — source-only D341 pocket fill vs the G22 `form_v2` stop (OBSERVE)

Кратко (RU): после `artifact` (его ведут #1917/#1928/#115) каждый G22-прогон с FBX останавливается на
`form_v2`: 7/7 сохранённых FBX-прогонов дают одни и те же 4 провала, 0,0999 м в точке (538,359; 1038,763) —
это впадина 0,10 м у лестничного окна, которую принятый ремонт k2 (D341, `fill_k2_a.json`) закрывает.
Инструмент без эталона (`jobs/POLY63-A/hooks/pockets_self.py`, настроен на 63A) есть, но в учебном дереве G22
не запускается (`ModuleNotFoundError: envelope_check`, папка хуков G22 скрыта). Проверяем: добавление этого
шага к собственному рецепту агента переводит `form_v2` в pass на G22 (эталон, на котором правило не настраивали).

Card t_fa3712bf, branch `research/autoresearch-standing-117`, base `origin/main@8a2fa635`. Contract frozen
before any measurement (this commit). Mode OBSERVE: no product change, no delivered package touched.

## Target and why

- Ledger `docs/trainer/ledger.json` @8a2fa635: first failing step `artifact` 3/4, `sources-dwg` 1/4. `artifact`
  levers are owned (PR #1917 FBX-first, PR #1928 G22 adapter, #115 deliverable naming, several-FBX rule = user
  decision). The next stop on the only etalon that scores `form_v2` (G22 k2) is `form_v2`.
- Stored census (frozen observation, read before this contract): runs r97-B1, r97-C2, r115-C1, C2, D1, D2, D3
  = 7/7 FBX-scored G22 runs `form_v2 defect`, summary pass 25 / fail 4, failing items `contour@16.85`,
  `contour@19.8`, `band_contour@17.8`, `band_contour@18.2`, each `dev_m 0.0999` at `[538.359, 1038.763]`
  (candidate->key). The accepted k2 repair list `C:/x/ev_1619/r4/env_k2_a.json` pocket 1: centre
  `[538.656, 1038.941]`, depth 0.10 m, `fill` (D341 texture rule). All agents build the plan with
  `tools/methods/body/floor_from_dump.py ... --seal windows --openings` (no `--fill`).

## Hypothesis H117

Adding the existing source-only D341 pocket fill (`pockets_self.py` -> `floor_from_dump --fill`) to the agent's own
recipe turns the trainer `form_v2` step on G22 from `defect` (4 fails) into `pass`, and its fill list matches the
accepted k2 repair list (3 pockets, depth 0.10 m) — with no etalon input.

## Metric

- **M117** = number of G22 replay builds (out of 3) whose `agr trainer score g22-k2-stage1` report has
  `steps.form_v2.status == "pass"`. Arm A = agent recipe (D1 command verbatim), arm B = A + pocket fill.
- Secondary (reported, not keep criteria): `first_failing_step`, `score`, `form_p95_m`, form_v2 fail item names
  and max `dev_m`; fill-list match to `fill_k2_a.json` (pocket centroid distance <= 0.15 m, count).
- Command (replay): `uv run python docs/research/trainer_pockets_r117/run.py --out C:/x/ev_t_fa3712bf/series`
  (3 reps x 2 arms, fresh out dirs, pinned inputs below; refuses on any hash mismatch).

## Pinned inputs (SHA-256)

| input | path | sha256 |
|---|---|---|
| G22 k2 source NPZ (practice input) | `C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1/inputs/g22_k2_src.npz` | `5eee4ac6911acb6c79e4d9d9871136d2eeb482fb5f8848f11ca179b397fc4622` |
| floor_from_dump (agent copy, #1928 overlay) | `C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1/wt/tools/methods/body/floor_from_dump.py` | `c2eb4f8542c8401e36e4cf8509c836b1cc1045655a0ca74448bcf01022f2fbd1` (byte-equal to `jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py` @8a2fa635) |
| pockets_self | `jobs/POLY63-A/hooks/pockets_self.py` @8a2fa635 | `282af95c7e68a9fa208194b00b44f03aeab80c541443ebba62d44fbb6e6c059b` |
| envelope_check (pockets_of) | `jobs/garibaldi22/body-training-1619/hooks/envelope_check.py` @8a2fa635 | `b67452ffb212ef904ba5089c0e2f95778da2dc7822522c96fb3879ced2f5e5d6` |
| D1 stored plan (parity) | `C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1/built/plan.json` | `5cf2bdbb51178900ef22362126fccb15df43a4637f8c23632e6f6747d1f25895` |
| accepted k2 repair list | `C:/x/ev_1619/r4/fill_k2_a.json` | `b8c0a4efcdb646f933c19d9974a1e52ac0d09806c133888d9df5a5d3d9759401` |
| G22 key (bank) | `G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/g22-k2-stage1/k2_v002r1_body_quad.fbx` | `5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200` |
| 63A unfilled floor (control) | `C:/x/ev_1619/r6/floor_63A_a.json` | `a6e92c8564427d1f1dcca998d425db31e07aa78efa689d98200aae6e3fdfb890` |
| 63A accepted-lineage pocket report | `C:/x/ev_1619/r6/env_63A_a.json` | `ae18326d66f9beb194a411b4986b8748100ab963856602594718a5f8c0d0bb6b` |

Builder/scorer: `agr body --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --max-side 3.6`
(as D1) and `agr trainer score` from this worktree @8a2fa635. Replay is limited to this PC (C:/x and the Drive bank).

## Fixtures, witnesses, controls (frozen)

- Representative fixture: G22 k2 practice input (the one every G22 run uses). G22 was NOT used to tune
  `pockets_self` (written for site 63 tower A, b0fe3b50); the texture depth 0.4 m / pocket-close 3.0 m are D341 /
  hook defaults, not changed here.
- Parity proof (arm A): A's plan rings equal D1's stored `plan.json` rings (vertex-exact); A's score reproduces D1:
  form_v2 `defect`, same 4 items, `dev_m 0.0999`, score 0.7143. If A does not reproduce D1 the series is invalid.
- Positive trigger witness: the D1 plan pocket at ~`[538.66, 1038.94]` (depth 0.10) must be in B's fill list.
- Accepted control where the rule fires (collateral): 63A accepted lineage — `pockets_self` on `floor_63A_a.json`
  must give exactly the texture decisions of `env_63A_a.json`: 14 fill (depth <= 0.4) and 6 keep (deep niches).
- Perturbations (synthetic 20 x 10 m rectangle, one 1.5 m-wide notch, expected direction):
  P0 no notch -> 0 pockets; P1 depth 0.10 -> 1 fill; P2 depth 0.39 -> 1 fill; P3 depth 0.41 -> 0 fill, 1 keep;
  P4 depth 0.10 but contour in another frame (+1000 m x/y shift) -> 1 fill (frame-independent).
- Invariance: in B vs A, count ring vertices farther than 0.05 m from every fill polygon that moved (> 1 mm);
  expected 0. Per-input changed counts reported; an input with no fill is `not_exercised`.

## Keep / stop rule, budget

- Hypothesis `confirmed` iff M117 A = 0/3 and B = 3/3, parity holds, the witness is filled, the 63A control is
  14/6 exact and the perturbations all match. `refuted` iff parity holds and B < 3/3 with the witness filled
  (or B shows a new failing item). Anything else `inconclusive`.
- OBSERVE: no KEEP into delivered work; the would-change (promote the source-only pocket census next to
  `tools/methods/body/floor_from_dump.py` so the practice tree can run it, and name it in the body trail) goes
  to its owner (#1928 / trainer owner) as a proposal, not applied here.
- Budget: one measured pair first (wall time recorded); 3 reps x 2 arms if the pair fits in 45 min; otherwise
  publish `inconclusive` with the exact next command. Max 1 confirm series; no new candidate variants.
- Deterministic pipeline: reps test replay stability (paired spread of form_v2 fail count and max dev), not noise.

## Amendment 1 (before the series; nothing of arm B measured yet)

The first measured pair (`C:/x/ev_t_fa3712bf/pair1`, arm A only, 10 s) showed `agr trainer score` now returns
`form_v2: error` — `FileNotFoundError: C:/x/t_563a40f7/key/heldout-key-v001.json`. The pinned G22 form-check key
and sections (sha `843197137db10cdc` / `270e83dedbbae380`) are gone from this PC and are not on Drive (searched
`AGR-evidence` depth 5: only the 63B copies in standing51/57, other hashes). The frozen M117 (trainer form_v2
status) is therefore unmeasurable. Arm A's other parity held: plan rings equal D1's, `form` p95 0.0128 as D1.

M117 is measured with a **parity-proved substitute** (`docs/research/trainer_pockets_r117/substitute.py`): the key
dict = D1's stored `key_used.json` (sha `4cb3cbfcfa3d4472d7f85b84d166f4a48fa4ea25592a631fd82c0022f00af5b9`,
written by pairs.py as `json.dump(key)`), the key sections re-extracted by the same `blender_scene.py extract` and
zmap from the bank key FBX (sha `5b1e8d76…`, = the key's `accepted_bytes.fbx`); segment counts in box 30/36/36/30
equal the key's `section_segments_in_box`. Parity: `detector.score` with the substitute reproduces **15/15** stored
G22 detector rows item-by-item (status and dev_m): 7 practice runs + 8 #115 control cases (2 accepted `ok`,
13 `defect` incl. rejected/module). Receipt `C:/x/ev_t_fa3712bf/parity.json` sha `a639c115…` (repo copy `trainer_pockets_r117/parity.json` Git-LF `6b0b15a1…`).
M117 = substitute form_v2 verdict `ok` (pass); the trainer status (`error`) is recorded alongside. Nothing else in
the contract changes. The missing pinned key is a side finding for the trainer owner (every G22 score on this PC
now stops at `form_v2: error`).

## Forbidden shortcuts

Changing scorer tolerances, the form_v2 detector or `pairs_v1.json`; editing the key, the bank, `etalons.json`,
delivered packages, stored runs; using the etalon/key or `fill_k2_a.json` as an input to arm B (it is only a
comparison target); tuning texture depth / pocket-close; touching files of PR #1917/#1928 or other cards.

## Result (series `C:/x/ev_t_fa3712bf/series`, 3 pairs, 87.5 s wall, run status complete)

**H117 confirmed** (frozen rule): M117 **A 0/3, B 3/3**; parity held 3/3 (A rings == D1 rings, A form_v2 fails =
D1's 4 items at 0.0999 m, `form` p95 0.0128 as D1); witness pocket filled 3/3; 63A accepted control 14 fill /
6 keep exact (depths match); perturbations 5/5 as expected. Paired spread 0 (fail count 4/4/4 vs 0/0/0; FBX bytes
differ per rep, metrics identical). Receipt `docs/research/trainer_pockets_r117/receipt.json` Git-LF SHA-256
`fe3ccc6812b06ef9d248ebee209b64f081c02163f0e98b88b3f0b2b7717821f0` (CRLF copy on C:/x and Drive `b6a20590…`); evidence
`G:/Мой диск/AGR-evidence/1855-r117-pocket-fill/SHA256SUMS.txt` sha `d7c64905117d9fb3ffff0ad9661f666d05768ccc9d71b17e85eb80e00b00bdb3`.

| arm | form_v2 (substitute) | fails | first stop | `form` p95 / max vs key | ring vertices | polygons |
|---|---|---|---|---|---|---|
| A (agent recipe) | fail x3 | 4 (0.0999 m) | form_v2 | 0.0128 / 0.1178 m | 57 | 3987 |
| B (+ pockets_self fill) | pass x3 | 0 | vlm (not run) | 0.0001 / 0.0002 m | 43 | 3717 |

Measured separately:
- Fill list vs Artem-accepted repair list `fill_k2_a.json`: frozen centroid metric matched **1/3** — a harness
  artefact (vertex mean; envelope_check repeats the closing vertex, pockets_self drops it). Unfrozen sensitivity:
  polygon IoU 1.000 / 1.000 / 0.999 for all 3 pockets (same areas 0.125/0.143/0.144 m2).
- Invariance (expected 0 moved vertices): 2 A vertices far from fills have no B twin — both lie on B's ring
  (<= 0.12 mm), i.e. collinear vertices dropped; B-A area outside fills+0.05 m = 0.045 m2 (3 pieces, max 0.042 m2,
  outward). Not a confirm criterion; recorded as a small collateral change of `floor_from_dump --fill` closing.
- Trainer `form_v2` = `error` in every arm (missing pinned key, Amendment 1) — the live trainer cannot score G22
  form_v2 on this PC until the key is restored.
- **Not measured:** live practice runs with the fill step (agents cannot run `pockets_self.py` in the G22 practice
  tree: `ModuleNotFoundError: envelope_check`; 0/30 stored G22 runs executed it, 3 only read about it), `vlm`,
  any etalon other than G22 for form_v2 (only G22 has a form-check key), deep pockets (> 0.4 m, need a reference).

Would-change (OBSERVE, not applied): make the source-only D341 census runnable from the practice tree — move
`pockets_of` + `census` next to `tools/methods/body/floor_from_dump.py` (the #1928 promotion) with a regression test
on a synthetic notch, and name `pockets_self -> floor_from_dump --fill` in the body trail after `--seal windows`.
Owner: #1928 / trainer owner. Then measure live: 3 fresh G22 practice pairs, count runs reaching `vlm`.

Replay: `uv run python docs/research/trainer_pockets_r117/run.py --out <NEW_DIR> --reps 3` (hash preflight of all
pinned inputs, ~90 s; limited to this PC: C:/x stored run D1 + ev_1619 + Drive bank). Substitute parity:
`uv run python docs/research/trainer_pockets_r117/substitute.py parity <NEW.json>`.
Affected tests: `uv run pytest -q tests/test_search_noise_1614.py tests/test_trainer_inspect.py tests/tools/test_trainer.py`
-> 211 passed, 2 failed = `test_form_v2_step_real_g22_accepted_pass_rejected_fail[v002r1-pass|v001-fail]`, both
`FileNotFoundError C:/x/t_563a40f7/key/heldout-key-v001.json` (environment, Amendment 1; no code changed here).
Full suite: deferred to merge batch (rule 68).
