# H164 — require an eligible wall competitor (OBSERVE)

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
