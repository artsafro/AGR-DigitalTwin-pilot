# H164 — require an eligible wall competitor (OBSERVE)

## Кратко для Артёма

**H164 подтверждена только на Силикатном.** Если подходящая по ширине стена одна, отказ вместо ответа убрал ложное назначение К–А → W19, но снял и верное А′–К → W19. Верный ответ по реальному фрагменту 1 сохранился: там было 11 подходящих стен. На пяти исходных контрольных видах: **2 верных / 0 неверных / 3 отказа → 1 / 0 / 4**. К–А — отдельная проверка ложного назначения, его правильную стену не определяли.

Для карты «вид ↔ грань» не считать единственную подходящую стену доказательством. Если нет соперника, нужен независимый признак (оси на плане или разрез); иначе — вопрос. Это предохранитель, а не решение для внутренних углов. Сокольники не открывал; код рабочего маршрута не менял.

## Frozen contract

Standing #164, `t_1efe82f1`. Continue the #163 Silikatny wall-segment benchmark, not the finish-partition work (#2073/#2074) or wall-exercise scorer repair (#2075). Readiness 2026-11-28_0836 leaves the cold OKS result open. #2001 is OPEN: no Sokolniki inputs or key opened. Atlas, form and trainer targets remain parked.

**Hypothesis:** requiring a second distinct eligible physical wall removes one known false assertion without erasing the correct native answer already backed by a competitor. This is a safety ablation, not a wall-recognition improvement. A is exact #163. B only vetoes a non-null A answer when fewer than two distinct eligible candidate IDs exist. No reranking, no retuning, no curved candidates, no changed overlap, width, tau or delta. Compare against the same live wall masks, PDF registration, scores and offsets, not a replay of published scores.

**Fixture:** all seven fixed #163 views on Silikatny (real PDF + Revit OBJ as pinned by #161; Blender 4.4 hash pinned by #163). Use #163 `56f608b577090a8f82cf4e2df2c722879199e378`, #162 `238e576d177d656df079e5992175ea5b646da297`, #161 `f4a7f22b107826d5e054f11a5e336c63aed81667`. #163 native baseline body SHA-256 `5cedce6e622d06b092a0b7be146623feee51a23a83b2ea0a6d79d03849709aca`. Reuse wall identity and five scored labels as frozen there. Additionally score K-A *only* as a W19 exclusion witness (p15, separate nine-column facade without the seven glazed projections; no positive physical wall ID). A-G remains diagnostic only. Do not count the K-A witness as full assignment truth or reclassify unsupported subjects as solved.

**Metric and threshold:** correct, wrong, abstain on the five original scored rows, with answered accuracy and abstain rate. The keep predicate for a *follow-up recommendation only* is zero wrong assertions including the separate K-A exclusion, with all bounds below in all three pairs. Publish correct coverage because B necessarily trades coverage for refusal. K-A should change from W19 to abstain, A'-K should lose its correct singleton W19 answer, fragment 1 should retain W19, and all three original native abstentions should stay abstentions. No positive claim for curved/developed walls, bays/intervals, finish transfer, held-out albums, or user-rejected deliveries (not measured).

| Acceptance point | Concrete input | Expected | Check |
|---|---|---|---|
| Null competitor negative and collateral | Native K-A and A'-K, A answers both with singleton W19 | B refuses both; count the lost correct assignment | replay + `test_singleton_is_not_a_competitor` |
| Active content control | Native fragment 1, A answers W19 with at least two eligible IDs | B retains W19; same A scores/geometry | replay + `test_real_competitor_preserves_answer` |
| No invented answers | No candidates or pre-existing abstention; 7 exercised native blank masks | Remain abstentions | replay + `test_preexisting_abstention` |
| Injected boundary | On clean fragment 1, remove all eligible competitors except A's winner, without changing score or winner; then reverse/reset original list | B refuses singleton, restores W19 when reset; actual removed IDs counted | replay + `test_real_competitor_preserves_answer`, `test_singleton_is_not_a_competitor` |
| Stable evidence | Three fresh shared-input A/B pairs, publish original #163 states / perturbation counts and proposal delta | Exact baseline body hash per pair; exact B parity; native unchanged rows not counted as veto activations | replay |

**Budget and stop:** three confirmation pairs, no alternative candidates or threshold sweep. One pair is a fresh Blender wall extraction/render + PDF read (shared by A and B; no duplicate renders). Hard budget 10 minutes; after pair 1, run the remaining two only if twice the first wall time fits the remaining budget. No incomplete series can confirm: elapsed/deadline or parity failure is `inconclusive`; a completed series missing the verdict bounds is `refuted`. Report median and spread of measured pair wall time. No edit to production code, delivered models, drawings, locked standards or other cards' files. No test/fixture deselection, no loosening the matcher and no using protected holdout data.

**Replay** (fresh worktree-local output on pilot host with original pinned Weltbau inputs and Blender):

```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-competitor/run.py tmp/ar164-replay
```

## Round log

**Hypothesis: confirmed. Run status: finished. Adoption readiness: no.** Three fresh paired Blender + PDF runs took 15.687 / 15.925 / 16.699 s including hash checks (median 15.925 s; spread 1.012 s). Original #163 wall table, masks' scoring output and all state decisions matched the pinned baseline digest in every pair. B's result digest matched across all pairs. The fixture is the original Silikatny render context, not a sample of adjudicated accepted/rejected delivery packages.

| Real view | Eligible walls | A | B | Interpretation |
|---|---:|---|---|---|
| p15 K-A | 1 | W19 | abstain | Exclusion witness: W19 is wrong; true wall not graded |
| p15 A'-K | 1 | W19 | abstain | One correct singleton lost |
| p16 fragment 1 | 11 | W19 | W19 | Correct competing-wall match retained |
| p14 4'-1; p14 1-4'; p17 fragment 2 | 0 / 0 / 11 | abstain | abstain | No new native inner-view match |
| p15 A-G | 5 | abstain | abstain | Diagnostic only |

Answered accuracy on the five originally graded views: 2/2 → 1/1; abstention: 3/5 → 4/5; correct coverage: 2/5 → 1/5. The K-A exclusion has one false assertion in A and none in B; it is not included in those denominators.

- **Injected:** seven blank masks changed 2,067–9,924 cells and already abstained in A; not veto activations. Mirror and shuffle changed pixels on all seven views (1,770–10,190 and 1,928–12,007 changes respectively); on those states B vetoed A'-K only, while retaining fragment 1. Removing all ten alternative eligible IDs on the clean fragment 1 made B abstain; reversing/restoring the full set recovered W19. This is a policy injection, not modified native geometry. Per-input counts and state decisions are in the receipt.
- **Not measured:** physical wall of K-A, face interval for fragment 1, curved and multi-wall candidates, accepted/rejected delivery calibration, other projects, finished-material transfer or removal of STOP 04. A competing wall is necessary for this score-only rule, not sufficient for production use. In particular, the shuffle retaining fragment 1 does not demonstrate bay-order or finish localisation.

Receipt: [receipt.json](autoresearch-view-face-competitor/receipt.json), SHA-256 `68e6cb2b02f1703140a706c6e1c22c37f8b522c2bf40006eef45178a2114e144`. Complete pair readbacks and 60 derived wall renders: `G:/Мой диск/AGR-evidence/164-view-face-competitor/` (76 entries verified, `SHA256SUMS.txt` SHA-256 `e232e199fadc153e45d93bc2517e3d54b5d9d99614ef742792813a089402db9a`). Replay limited to a host with the exact owner folder inputs and Blender executable (the derived evidence folder does not hold the original OBJ/PDF). The prior A is regenerated, not taken from the evidence folder.

Regression RED on the legacy pass-through: 1 failed, 2 passed (singleton wrongly returned W19). The research variant is branch-only; no PR or production changes. Full suite: deferred to merge batch (rule 68).
