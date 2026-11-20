# Body mesh quality — standing #14 (OBSERVE)

**Кратко.** Проверяем, улучшает ли локальный штраф калибровку оценки, прежде чем пробовать менять построитель бадика. Модели остаются неизменными.

## Frozen contract

Continue #13, merged #1724 at `82875426d52dadd63b59814d97e46d44570806e2`. Fixture and labels: all 13 unchanged hash-pinned inputs and all 9 same-building pairs from that revision's `autoresearch-body-mesh-quality-harness/calibrate.py` (stage-1 63B and 63C, KPP1 quad-v003 split by the original zones, G22 k1 native-derived polygon dumps). Neither stage 2 (#1722/#1726) nor atlas (#1649) nor corner edits (#1609) are in scope. 63A and G22 k2/k3 lack matched rejections and are not measured. No tuning against absolute etalon distance, which inverted k1 in #12.

One metric: minimum over the nine (accepted minus rejected) differences of median-of-three scores, in points. Confirm budget: one unchanged triplicate series across 13 fixtures, require exact baseline score payloads across repeats and #13 pair margins. New candidate budget: one triplicate series on the same 13, no follow-up candidate. Report max-minus-min of the three aligned accepted/rejected differences for each variant and of the paired R1−R0 differences. Stop after the candidate, or 8 minutes of measurement, or invalid evidence. Recommend further independent calibration only if each candidate margin is ≥0.500 points, every repeat deterministic and parity holds; no production adoption on these in-sample labels. No body core trials under an uncalibrated default.

Exact candidate R1: inside existing per-object in-zone face loop, group measured faces by `floor(centroid / 4 m)` in world XYZ. Compute max over cells and objects of `irregular_area / max(measured_area, 4 m²)`; replace only the irregular-area **penalty** by the mean of global and max(global, local). Same angular predicate, zones, weights and all other penalties. The area floor is one quarter of a 4×4 m cell face and prevents a tiny single trim face from incurring a full penalty. No target/building-specific constants. Fixed-grid sensitivity and held-out verdicts are not established.

Replay from the card branch: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-local-harness/replay.py NEW_DIR`. Reuse #13's pinned harness via `git show` and its original hash-checked native and JSON inputs; only R1 runs with a process-local core overlay, never changes the production source. Pairwise parity: remove score and the single intended penalty (and added diagnostic); require exact remaining payloads, including raw components, totals, topology findings and all guard parameters. Require exact digest identity before/after. Run one synthetic clean rectangular face control and one geometry-only skewed quad injection with a separate clean panel in another cell, plus reset; injected must incur a higher R1 penalty than R0, raw evidence must still match. Synthetic probe is not native acceptance. No edits to delivered packages, source evidence, models, other cards' files; no removed tests or weakened tolerance. Publish replay and receipt even on discard.

## Result — one R1 trial, OBSERVE only

**Кратко.** Локальный штраф поднял минимальный отрыв с **0,427 до 0,611** при пороге **0,500**: прошли все 9 пар. Для 63C отрыв вырос с 0,427 до 2,698; для КПП1, наоборот, снизился с 0,718 до 0,611 и стал минимальным. Вариант годится для независимой проверки, но не для внедрения: порог пройден лишь на известном наборе. Модели, построители и штатную оценку не меняли.

| Accepted − rejected | R0 points | R1 points |
|---|---:|---:|
| 63B v007 − v001 | 1.964 | 3.157 |
| 63B v007 − v002 | 1.978 | 3.171 |
| 63B v007 − v003 | 1.969 | 3.162 |
| 63B v007 − v004 | 1.962 | 3.155 |
| 63B v007 − v005 | 2.088 | 3.184 |
| 63B v007 − v006 | 0.947 | 2.294 |
| 63C v002 − v001 | 0.427 | 2.698 |
| KPP1 v003 rest − corners | 0.718 | 0.611 |
| G22 k1 v003 − v002 | 1.028 | 1.028 |

- **Measured, original inputs:** 13 × 3 per variant; R0 reproduced all #13 margins exactly. All within-variant repeats were identical (excluding input provenance); every R0, R1 and R1−R0 paired spread was 0.000. Full reports matched in 39/39 paired comparisons after removing only score, irregular-area penalty and its new diagnostic. Input digests unchanged. Blender 5.1.2 for native inputs; G22 k1 used recorded dumps. The maximum local ratio for accepted KPP1 rest was already 0.876 (corners 0.925), so R1 penalized both heavily and narrowed their separation. G22 k1 had no irregular faces in either version: this signal does not detect the inward-face defect.
- **Synthetic, injected separately:** rectangular panels and clean reset unchanged. Skewing one panel raised the penalty from 0.357143 to 0.678571 without changing other report fields relative to R0 on that same geometry. Initial replay preflight caught a nonunique source anchor; the anchor was narrowed before any corpus measurement, with no change to the formula.
- **Not measured:** held-out accept/reject pairs, sensitivity to grid origin or orientation, 63A and G22 k2/k3 rejection controls, and any geometry rebuild, package or delivery check. No full suite.

Measured revision `cf67f52aef61250701ec0e19581040cc6000c738`, worktree base `1ffdcb760a0c1099c8da627d3650ea8fc207788e`. Replay uses the #13 fixture at the pinned main revision above; the scorer, native reader and runner were identical at those bases. Per-input hashes, scores and spreads: [comparison.json](autoresearch-body-mesh-local-harness/comparison.json), SHA-256 `a52fca97ce6e917e4480984a669d28844606c55fad0e671285eed2385cd86c72` on the measured Windows receipt (CRLF). Replay command above; use `PYTHONUTF8=1` for Unicode native paths. Affected: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL ../../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=C:/x/ar14-pytest tests/qa/test_mesh_quality_score_1616.py` → 291 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` → 542 passed, 1 warning; `repo_guards: GREEN`.

Next: freeze a held-out same-stage accepted/rejected pair and a known clean oblique/rounded facade; verify whether the fixed-grid ranking survives a translated grid before adopting it. Keep G22's inward-face failure as a separate geometry control; a skew penalty cannot stand in for that check.
