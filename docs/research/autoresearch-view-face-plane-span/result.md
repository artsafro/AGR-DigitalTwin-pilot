# #148 — Round log: visible plane span veto

**Для Артёма:** максимальная ширина одной видимой плоскости не годится как фильтр для привязки фасада. На ТЦ «Среда» она убрала одну из двух уверенных ошибок, но также все 5 верных полных видов и 8 из 14 верных обрезок. Короткая ошибочная обрезка по-прежнему подходит по ширине. Для шага OKS предлагаю сначала опираться на оси/ключевой план, а по неподписанным фрагментам без уникальной геометрической привязки показывать варианты и спрашивать, не переносить отделку автоматически. Сокольники не открывал.

**Hypothesis: refuted. Run: finished. Review readiness is separate.** [Frozen contract](../autoresearch-view-face-plane-span.md), frozen before scoring at `31af41a1`; measurement at `4cb21a81c7a284aae44de8ee5149878bd4506b82`. No production change retained.

| ELV scope | C correct / wrong / abstain | D correct / wrong / abstain |
|---|---:|---:|
| Real full (7) | 5 / 0 / 2 | 0 / 0 / 7 |
| Real fragments (2) | 1 / 0 / 1 | 1 / 0 / 1 |
| Real top-cut (1) | 0 / 0 / 1 | 0 / 0 / 1 |
| Injected synthetic crops (63) | 14 / 1 / 48 | 6 / 1 / 56 |
| Injected mirror (7) | 2 / 1 / 4 | 0 / 0 / 7 |

- Real native views combined: answered accuracy C 6/6, D 1/1; abstention C 4/10, D 9/10. No real-view answer improved. The same `p23 frag D-G` (20.2 m, az 0) is the only real fragment answered correctly. This verifies side/azimuth, not the bay or exact face interval used for finishes.
- Injected synthetic partials: exact answered accuracy C 14/15, D 6/7, abstention C 48/63, D 56/63. Mirror: C 2/3 answered accuracy, D undefined (no answers); abstention C 4/7, D 7/7. All 7 mirror inputs changed pixels; native full tests use no injected pixels. Per-input counts and changed answers are in the receipt.
- Visible spans (m), in azimuth order 0/90/180/270: 20.5, 33.5, 30.5, 75.3. The wrong `p19 A-I partial25@1.0` is only 13.7 m, so it passes az 0's bound. A stricter upper bound would also remove longer C-correct az 0 views; circularly tuning this single number cannot retain all C-correct assignments. `p19 10-1 mirror` and C-correct `p18 1-10 full` have the same 88.6 m width and the same C pick (270); any width-only policy on those inputs treats them identically. Removing that mirror mistake by refusing both is not real-view improvement.
- Exact C parity 80/80 in each of three fresh native pairs; identical candidate JSON SHA-256 across pairs. Pair wall seconds 123.913, 119.482, 117.405; median 119.482, min/max 117.405/123.913, spread 6.508; total wall 360.853 vs 840 s. First attempt stopped before D (`ValueError` formatting float azimuth as `d`); reproduced test red, then normalized only validated exact azimuth IDs. First attempt is sealed but not counted.
- Not measured: full-corpus calibration, customer-rejected packages, G22/KPP1/AC08/OBR22/Vatutino transfer, uncalibrated-scale input, real unlabeled inner-corner transfer and within-face localization. Texture/form/trainer tracks not reopened; readiness 2026-11-27_2033 reviewed, #147 covers the prior agreement veto, #2001 exclusion preserved.

**Replay:** use the contract command on the pilot host at the measured commit with a fresh output, pinned #139/#140/#145/#146/#147 objects and the #145 fixture's named source paths. PDF and FBX stock evidence copies were independently verified under `G:/Мой диск/AGR-evidence/145-view-face-elv/run1/`; the replay runner still uses the original fixture paths, so portable replay is limited. The 15-member readback seal is `G:/Мой диск/AGR-evidence/148-view-face-plane-span/` (`SHA256SUMS.txt` SHA-256 `9b2c9ea75c08f12de99a61b9002f062547b9ed694b2fc1650666ef60175a9641`); receipt `9d85cfd2dae40730106d72357f43d8d3b77c93fea8f50a7a81de3d18f1dc2d5d`. Remote sync is not asserted.

**Next targets (not implemented):** (1) Register the plan footprint in the model frame and compare ordered left/right return-wall context for the two actual unresolved ELV partials; score face identity and within-face span separately. Retain `p23 D-G` as an active positive and wrong-facing mirrored/short views as negatives. (2) After #2001 closes, freeze both actual Sokolniki ROIs and physical inner-face intervals independently, then run a blind transfer without retuning; preserve STOP 04 for any unresolved view.
