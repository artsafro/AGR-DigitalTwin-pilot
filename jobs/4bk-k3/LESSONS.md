# 4bk-k3 — retrospective preferences and etalon lessons

Scope: **JOB-LOCAL**, applicable only to 4bk-k3 (VPM-OKS, tower A and stylobate B). These are not D-rows or domain rules. Promotion to shared policy requires Artem's explicit instruction; the 2026-11-15 consolidation instruction supersedes the promotion requests in the source issues: «разбери issues» → «сделай» ([#1459](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1459)). No model, map, validator or delivery acceptance is changed here.

Provenance: dates below are the recorded discussion dates, not issue creation dates. Verbatim excerpts use «…»; the remaining English descriptions are summaries. Where no exact quote survives, `пересказ по <source> (дословная цитата не сохранена)` explicitly identifies a paraphrase, not Artem's words. Such unconfirmed wording is marked `ждут подтверждения Артёма`; recording it does not approve it. Closing the superseded promotion issues means consolidation, not generalisation or resolution of open model questions.

## Earlier preferences — 2026-11-12

Source snapshot: `jobs/4bk-k3/TASK.md` at [fd538338](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/fd538338/jobs/4bk-k3/TASK.md), sections “Part joints” and “Joint UV method”.

- [1367.01] 2026-11-12 — [#1367 item 1](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1367): embed the smaller Lego part into the larger and delete the smaller part's embedded/coplanar face; Artem: «мелкую мы врезаем в большую, и у мелкой полигон, который врезался, мы просто его удаляем».
- [1367.02] 2026-11-12 — [#1367 item 2](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1367): use one texel, straighten and stack panels by the left joint edge on one painted line; Artem: «выбираю, что швы будут идти по левому эджу» and «кладу все полигоны друг по другу левым краем на этот шов»; long faces needing an intermediate joint use another tile: «один тайл, где всё укладывается по нарезке, а длинный полигон, которому нужен шов посередине, — в отдельном тайле».
- [1367.03] 2026-11-12 — пересказ по [#1367 item 3](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1367) (дословная цитата не сохранена): use plain Bitmaps, not MultiTile, for reviewed IDs in the Max viewport so joints remain visible; ждут подтверждения Артёма.
- [1367.04] 2026-11-12 — пересказ по [#1367 item 4](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1367) (дословная цитата не сохранена): name the customer's working DCC folder `build/`, not `work/`; ждут подтверждения Артёма.

## Floor 1 and stylobate preferences — 2026-11-14/15

Source snapshot: `jobs/4bk-k3/TASK.md` at [6aa786d9](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6aa786d9/jobs/4bk-k3/TASK.md), floor-1/stylobate reviews, texture review and “Long walls past the UDIM tile”. An issue-only date range is retained where the precise statement date is not preserved.

- [1451.01] 2026-11-14 — [#1451 item 1](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451): aim for texel ≥ 520 px/m on B UV v002 and A UV; Artem: «512 это слишком низкое значение, надо хотя бы 520»; this job's safety margin does not replace the shared 512 px/m bound [D160] or decide the general metric.
- [1451.02] 2026-11-15 — [#1451 item 2](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451): detach the main window glass from frames into a separate object at final delivery; Artem: «итоговое main глаз всегда detached»; the historical B v007 review still had glass inside `STY_WinB_*`, so this record is not proof that delivery detachment was done.
- [1451.03] 2026-11-15 — пересказ по [#1451 item 3](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): split walls longer than a tile with full-height vertical loops (Connect horizontal edges), at joints or about every 4 m without joints; no partial cuts; ждут подтверждения Артёма.
- [1451.04] 2026-11-14/15 — пересказ по [#1451 item 4](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): freeze accepted geometry; report later defects to Artem as helpers rather than silently repairing it; later A UV used the accepted v004/v003/v003 set, not the rejected QA-round v008e set; ждут подтверждения Артёма.
- [1451.05] 2026-11-14 — [#1451 item 5](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451): Artem: «опуски делаем на несколько метров вниз»; recorded implementation summary: 2 m drop, extend frames less than 10 cm above the facade bottom down to the drop, and move the protruding open polygon down/into its neighbour rather than adding cap faces; these details are the TASK summary, not additional verbatim words.
- [1451.06] 2026-11-14/15 — [#1451 item 6](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451): Artem: «Двойные стёкла слишком буквально»; recorded issue summary: one 20 mm glass slab, posts on its axis, a top handrail, no glass top face and one continuous cap; the dimensions and construction are the issue summary, not additional verbatim words.
- [1451.07] 2026-11-14 — пересказ по [#1451 item 7](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): roof exit boxes take the roof colour/ID6 instead of brick, superseding the earlier v001 brick assignment; ждут подтверждения Артёма.
- [1451.08] 2026-11-14/15 — пересказ по [#1451 item 8](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): one diagonal between opening corners is acceptable instead of dense cuts; ждут подтверждения Артёма.
- [1451.09] 2026-11-14/15 — пересказ по [#1451 item 9](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): no capsule behind a ventilation grille; ждут подтверждения Артёма.
- [1451.10] 2026-11-15 — OPEN, пересказ по [#1451 item 10](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1451) (дословная цитата не сохранена): box projection yields 441 vs 613 px/m on diagonal facades of bldA; a non-metric scale is not approved; Artem's choice remains open here after administrative issue closure.

## Confirmed facade etalon analysis — 2026-11-15

These are summaries of the analysis, not his per-rule wording. Artem's general confirmation at 15:32 was «разбор корпуса, в принципе, верный» ([#1448](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448)); it confirms the comparison, not a project-wide rule or delivery certificate. His 15:10 explanation was «мне пришлось перемоделивать за тебя часть геометрии, разворачивал на первом этаже я кирпич».

Analysis sources (outside git, read-only): customer root `C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/`; relative paths `build/gf_parts/_review/max/artem_final_analysis/ANALYSIS.md` and `build/gf_parts/_review/max/artem_v007_analysis/ANALYSIS.md`. `final` and `v007` below identify these two reports; neither report is a verbatim transcript.

- [1448.01] 2026-11-15 — [#1448 item 1](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: cut facades only at band levels and segment edges; brick/АКП islands are segment × band, left edge on the painted vertical joint and band edges on joint rows.
- [1448.02] 2026-11-15 — [#1448 item 2](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: closed U-profile reveals continue through the plinth.
- [1448.03] 2026-11-15 — [#1448 item 3](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: lamellae and fins have rings at every transom height.
- [1448.04] 2026-11-15 — [#1448 item 4](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: cornices and bands are closed boxes thick enough for frame ends to embed inside them.
- [1448.05] 2026-11-15 — [#1448 item 5](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: railing glass has no top face and one continuous metal cap.
- [1448.06] 2026-11-15 — [#1448 item 6](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: before handover, zero-area UV faces = 0 and every face lies on its assigned ID's tile; B v007's reported 1287 zero-area ID2 faces are historical defects, not accepted exceptions.
- [1448.07] 2026-11-15 — [#1448 item 7](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1448), final + v007 analysis summary, general confirmation above: never repaint a map in place; map edits go to a new versioned folder.

### Existing UV checks and limits

[`src/twinqa/uv.py`](../../src/twinqa/uv.py) provides `face_issue`; [`tests/qa/test_uv.py`](../../tests/qa/test_uv.py) exercises the face checks. [`tests/twinqa/test_uv_features.py`](../../tests/twinqa/test_uv_features.py) exercises zero-area polygon rejection and explicit wrong-tile rejection. Tile-vs-ID verification still requires the job's explicit ID-to-tile assignment: material IDs are not automatically UDIM numbers. These synthetic checks do not re-read or certify Artem's Max etalons, and this documentation does not claim the historical defects are fixed.
