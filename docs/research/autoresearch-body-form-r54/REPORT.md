# Standing #54 — Candidate-relative reveal depth, round 1

**Кратко. H54 подтверждена на двух контрольных проёмах, не для внедрения.** При сдвиге линии фасада на 0,100 м от задней петли глубина откоса выросла на 0,100 м на G22 и 63B во всех трёх повторах. Метод #53, считавший от линии ключа, показал 0. При совместном сдвиге фасада и петли глубина не изменилась; сдвиг только одного сечения дал «не измерено». Производственный код, модели и пороги не менялись; PR нет.

## Clean readback and calibration

[Contract](../autoresearch-body-form-r54.md) frozen at `8df33f8c`; candidate and pins at `7d8d9e04`. Run01 stopped before extraction (GNU `sha256sum` read a CR as part of two 63B manifest filenames); `b78b2a48` uses line-ending-independent manifest verification against the same pinned bytes. Run02 `complete`, 30 fresh Blender 5.1 imports, 35.485 s wall incl. pre/postflight (timed v007/v002 pair 2.265 s; 180 s cap); complete original report parity modulo candidate path on all 30. Labels/bytes in contract and [receipt](receipt.json). C_none passed all 29 original group-A items; stale-key rerun was not part of this round (prior controls unchanged).

| Exact variant | Frozen TP / FP_extra / FN | Candidate depth unmeasured | Depth failures vs source-wall 0.50 m / attribute |
|---|---:|---:|---:|
| 63B v007 accepted | 5 / 2 / 0 | 0/5 | 0 / 5 |
| 63B v002–v006 rejected (each) | 5 / 0 / 0 | 0/5 each | 5 / 0 each |
| G22 A v002r1 accepted | 6 / 0 / 0 | 0/6 | n/a / 0 |
| G22 R v001 rejected for stage 1 | 0 / 0 / 6 | 6/6 (absent apertures) | n/a / not measured |

No clean depth that #53 measured became unmeasured; maximum absolute difference among comparable depths was 0.000100 m (rounded up). G22's original scene rubric still ranks A over R (29 passes vs 1; 18 original items unmeasured on R); historical mesh proxy still ranks R over A (90.830 vs 83.693, broader scope, not recomputed). 63B depth calibration is **conditional**: the source-wall reference gives 0 vs 5 depth failures per variant; the attribute gives the opposite ordering. Neither was selected as design authority. The original 63B contour/gap report is unchanged, including its reversed ranking and two flagged extra gaps on accepted v007 (see #51–52); this experiment does not fix it.

## Injected controls and unmeasured scope

| Fixture and target | Flank-only (m) | Flank + rim | Lower slice only | Segment edits, lower/upper; all reps |
|---|---|---|---|---|
| G22 C_none `4259581` | 0.150040 → 0.250040 | depth Δ < 0.001 m | noncoplanar, no depth | 2/2, 2/2, 2/0 respectively |
| 63B v007 `…194b464` | 0.499999 → 0.599999 | depth Δ < 0.001 m | noncoplanar, no depth | 2/2, 2/2, 2/0 respectively |

Primary: worst median absolute response error `4.783e-14 m` (essentially zero, max paired spread 0); target exercised in all six accepted-fixture repetitions, zero off-target changes above 0.001 m or status flips. The old key-relative depth stayed unchanged on the flank-only witness. Section-layer perturbations on new readbacks, **not mutated FBX**: the candidate and generator use the same flank selector, so this measures arithmetic response/locality, not independent correctness of wall ownership. Native G22 C_shift_wall produced 2 frozen contour failures and the same six relative depths (`0/6` changed at 0.001 m in each repetition); not an exercised local depth-change witness. R has no rim to exercise depth. KPP1 NW and Sokolniki exact model-side pairs, render/scene judge agreement there, independent ownership/transfer, and geometry proxy on this crop are not measured. The #40 rubrics and #41 judge evidence remain separate.

## Decision and replay

**Hypothesis:** `confirmed`, limited to the frozen experiment. **Review readiness:** ready as OBSERVE evidence; neither a validated general form metric nor a proposed enforcing gate. Next: qualify flank ownership against a neighbouring/rear wall independently of the selector; then resolve the 63B 0.50/0.71 m source decision before any depth gate or transfer.

`python -X utf8 docs/research/autoresearch-body-form-r54/replay.py C:/x/t_15bdb840-r54/replay-new` — new directory, pinned PC-local inputs as described in the contract. Compact receipt records raw-result path and SHA-256, paired observations and fixture hashes; raw evidence and replay are limited to the fixture-equipped PC. No hidden key was copied to Git.

Affected tests: `uv run --offline pytest -q tests/test_body_contours.py tests/test_blender_exit_code_guard.py --basetemp C:/x/t_15bdb840-pytest` — 41 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 542 passed, 1 warning; `repo_guards: GREEN`. Full suite not run (rule 68).
