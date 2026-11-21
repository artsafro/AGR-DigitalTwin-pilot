# Body mesh quality — standing #18, R3 held-out accepted controls (OBSERVE)

**Кратко.** R3 не снизил балл ни одному из двух принятых корпусов вне калибровки #17: максимальное падение **0,000** при пороге **0,500**. Оба корпуса не содержат граней, которые R3 считает косыми. Поэтому результат не объясняет штраф **4,29** на принятом 63B v007 и не даёт основания внедрять R3. Модели и рабочие проверки не изменены.

## Frozen contract (before measurements)

One metric: maximum over the two accepted controls of median(R0 − R3) in score points, with three paired evaluations per input. Keep threshold ≤ 0.5 points (same scale as the #13 calibration margin; a larger shift on an accepted control is material). Passing is necessary, not sufficient for rollout. Require score triples and complete canonical report parity outside score, local share and the named irregular-area penalty. Report max−min of the paired deltas per input. Deadline: one confirmation round, ≤ 5 minutes measurement; zero new candidates and zero retries on a valid negative result. Confirm #17's existing calibration by checking its pinned receipt (not a fresh nine-pair rerun); hash the R0 and R3 code and verify they match that receipt. Reuse `candidate` and `pinned` from the immutable #1759 harness at `6ae13568ca85bb3880e84f4f1a30f22f6c23a96d`, plus its existing clean/skew/reset witness. No refit, score-parameter changes, source/output edits, delivery changes, test deselection, weakened QA, shared-core changes or writes to other cards' files.

Frozen held-out scope (both [accepted at stage 1](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1619#issuecomment-6972338279), no stage-2 attachments):

- 63A v005 full stage-1 typical body with reveals and niches, QUAD FBX `G:/Мой диск/AGR-evidence/1619-body-training/tower-A/v005/63A_Stage1_v005.fbx`, SHA-256 `f3769c62a7e9fdbfcf7a59624269bcd0374ca494f593e2e85c08474a0007798a`. Read-only Blender dump from a verified private copy; repeat scoring on that fixed dump, not three native imports.
- G22 k2 v002r1 accepted stage-1 typical band retained in #12: `C:/x/ev_1619/r7/k2_v002r1.mq.json`, SHA-256 `2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b`. No fresh native readback here. Do not compare the absolute scores across buildings.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-holdout-harness/holdout.py NEW_DIR`. Python/Blender read-only, metres from the existing dump owner, unchanged defaults, no zone filters. A real rejected holdout with a comparable mesh scope and a verified clean rounded/oblique envelope remain unmeasured; the synthetic skew witness is not either of these. Calibration is not approval: G22 k1 distance-to-etalon still rewards the rejection (#12), and changing body construction is owned by #1736/#1742. No overlap with #1759 (its in-sample run), #1739/#1751 (skeleton integration), #1722 (63B stage 2), #1649 (atlas), #1609 (KPP1), or #1315/#1622 (cold runs). No switch to speed work while this quality check is available.

## Result — OBSERVE, no adoption

| Accepted control | Scope | R0 median | R3 median | Median drop | Paired spread |
| --- | --- | ---: | ---: | ---: | ---: |
| 63A v005 | Fresh Blender 5.1.2 readback, 4,560 quads | 83.941 | 83.941 | 0.000 | 0.000 |
| G22 k2 v002r1 | Retained dump, 3,933 quads | 83.693 | 83.693 | 0.000 | 0.000 |

Receipt: [`holdout.json`](autoresearch-body-mesh-holdout-harness/holdout.json), SHA-256 `4cd18c20f819cd22caf68c9dc905de474515dd791b86cb073594bcdf58235ae3`. Clean: both input hashes unchanged, score reports equal modulo the named fields, clean/reset witness passed. Injected: pinned synthetic skew witness passed. Not measured: a separate labelled rejection pair, verified clean rounded/oblique envelope, fresh G22 k2 import, geometry candidate and delivery QA. Prior same-building calibration (minimum 0.718) is pinned evidence, not a new measurement.

Would change (not applied): identify the specific R3 seed faces responsible for the penalty on accepted 63B v007 and check whether they are legitimate reveals, curved transitions or defects. Only then test an explicitly scoped rule on an independent labelled pair and a clean curved/oblique control; neither production scoring nor the shared body core should change on this result.
