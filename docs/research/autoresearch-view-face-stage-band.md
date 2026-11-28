# H156 — Stage-band clipping before roofline corroboration (OBSERVE)

## Кратко для Артёма

Нижняя отсечка по границе соседнего этапа не помогла: на четырёх фасадах ФОК «Олимпийский» до и после —
**2 верных ответа, 0 ошибок, 2 отказа**. Клиппинг реально изменил три чертежа, но не разрешил ни лист 7, ни лист 8.
Горизонтальную отсечку в общий шаг OKS не переносим. Если оси или ключевой план дают только одну подсказку,
а геометрия её не подтверждает, карта должна показать кандидатов и причину отказа, а не переносить отделку.
Полноценную маску этапа, реальные безымянные фрагменты и внутренние углы этот опыт не проверял.

## Frozen contract

Continue #154 on Olimpijsky, not #2075 (wall-level accounting). Readiness 2026-11-28_0034 ties cold OKS readiness to #2001 (OPEN); its Sokolniki inputs and answers remain held out. Do not reopen atlas/form/trainer. No production route, model or packaged files may change. This is calibration on the known failure, not transfer validation.

**Hypothesis:** excluding the lower drawing band at a visually traced stage-5 overlap boundary can restore one of two previously unresolved sides without losing the active p6 control. Compare A = complete #154 rows, B = same roofline and keyplan conjunction and thresholds using only linework above the stage-band top. Manually supplied boundaries, not automatic parsing. Pin #154 (`1369c97893e4d38c5e6b2c96f1a070bbc969b0e7`) runner and published receipt via Git blobs. Reuse its pinned PDF, ray archive and dependency blobs, and check their hashes before and after; check current lock against the #154 lock. No new native render is claimed.

**Frozen representative fixture and intervention:** p5–p8 as in #154, no omissions. p5 boiler overlap is not a lower stage-5 band, so p5 is an unchanged control. At p6, p7, p8 retain the original box and linework at or above the upper pink stage-5 band edge (respectively 820.5, 983.3, 967.2 PDF pt, top-left origin, read from the boundary fill on the source/elevation), extended horizontally across the original crop. Corresponding PDF path sequence numbers 66512, 13184, 31586. Clip crossing segments without adding an edge at the cut. This excludes some main-stage lower detail and does not remove the separately drawn boiler region p7; neither is a full stage polygon mask. In particular, this is a test of the simple *band* approximation, not a claim that a stage is always rectangular. No width, threshold, labels, crop or hypotheses may be revised after scoring.

**Metric:** correct / answered (null for no answers), plus abstain / total, on the four real full views; all precision gains must preserve coverage. Expected bound for B: 0 confident wrong; >=3/4 correct; p5 and p6 still correct, with p6 an actively clipped accepted control; at least one of p7/p8 newly correct. Both p7 and p8 must have nonzero clipped linework for a valid test of the failure. Existing injected keyplan states (masked/interior/ambiguous/opposite_only) must all abstain in B, without changing the #154 mark or perturbation accounting. A must reproduce every #154 row; p5 B equals A exactly. Count per-view dropped/trimmed segments and inherited per-state mark mutations; p5 clipping is `not_exercised`. Wrong opposite marks are rejected assignment controls, not rejected deliveries.

**Budget and parity:** one unchanged baseline and exactly one candidate, three fresh paired #154-style PDF extractions against pinned native ray readback, no frozen-row rescoring. 120 s core-series cap; after pair 1, stop if elapsed + 1.2 x pair 1 duration x remaining pairs exceeds cap. Required byte-identical rows, input hash parity and exact A row parity. Any coverage/parity or budget failure is inconclusive; otherwise violating the B bound refutes H156. Report wall duration, median/spread, run status and hypothesis separately. No tests deselected/threshold weakening. No synthetic partials, bay/physical wall scoring, DWG, finish transfer or STOP 04 claims.

**Replay (pilot host, mounted #151 evidence):** `git fetch origin research/autoresearch-standing-151 research/autoresearch-standing-152 research/autoresearch-standing-154`, then `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-stage-band/run.py tmp/ar156-NEW`. The run stages Git blobs, checks external input hashes and refuses an occupied output root. Replay limited to hosts with the pinned evidence or verified copies.

## Round log

**Hypothesis: refuted. Run status: complete.** Contract `fd80fb22`; measured driver head
`f831baf08df3e4fea3b612d289c7203581a0776a`. Run 1 refused before scoring B: comparing the re-encoded decoded
receipt to the live rows sorted integer azimuth keys differently from JSON string keys. Repair 1 compared all
decoded values without depending on key order, with a changed-cost negative test (1 failed / 2 passed before,
3 passed after). No scoring code, cutoff, bounds or fixture changed.

Run 2: fresh PDF read and keyplan replay in both arms of each pair. 13.93830 / 13.22937 / 12.97264 s,
median 13.22937 s, spread 0.96566 s, core series 40.14033 s. Three byte-identical pair payloads
(`708071005c48a5db7aa98fb7011753fca610578e0e4e0b5059a12879dcff9c5b`); A matches all #154 row values,
inputs unchanged. On clean views A and B both score 2/2 answered accuracy and 2/4 abstentions.

| View | Dropped / trimmed segments in B | Profile width, A → B (0.1 m columns) | Clean A → B |
|---|---:|---:|---|
| p5 | 0 / 0 (`not_exercised`) | 1513 → 1513 | 90 → 90 |
| p6 | 4345 / 124 | 1568 → 1563 | 270 → 270 (active accepted control) |
| p7 | 833 / 123 | 729 → 714 | abstain → abstain; best cost 2.179 m > 2 m ceiling |
| p8 | 1617 / 219 | 699 → 698 | abstain → abstain; 0.2825 m gap < 0.75 m margin |

Injected keyplans (not delivery judgments): all four states on each page changed native mark segments;
A and B each abstained on 4/4 per state. The opposite-only mark alone was wrong on 4/4 in #154 and still is;
only p5/p6 have an independent roof proposal to veto it. Per-input state counts (`added`/`removed`) and costs
are in the sealed pair JSONs. No clean or injected verdict changed. p5 clipping is not measured, and neither
are new native rendering, stage-polygon segmentation, genuine partials, physical wall/bay truth or Sokolniki.

Evidence: `G:/Мой диск/AGR-evidence/156-view-face-stage-band/` + `SHA256SUMS.txt`; compact receipt
`autoresearch-view-face-stage-band/receipt.json` SHA-256 `7e0e36f1fca243aee0e2d9d99ba844e9f6b16887272f609707f7c6955345aee4`.
No product change, no PR; branch-only OBSERVE receipt for independent review.

Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --locked --extra pdf-review pytest -q -p no:cacheprovider --basetemp tmp/ar156/pt-final docs/research/autoresearch-view-face-stage-band/test_run.py` — 3 passed.
Pilot guards: `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 568 passed, 1 warning; `repo_guards: GREEN`.
Full suite: deferred to merge batch (rule 68).
