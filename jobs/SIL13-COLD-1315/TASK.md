# SIL13 cold reproduction — issue #1315

## Requirement

Artem: «библиотеки уже есть эталонные на диске по флоре и МАФ, из них брать».
Gate 1 replies: «принимаю рекомендации» and «свежий» (relayed by the orchestrator).
Scope decision: [D272] in `docs/decisions.md`; cells `ground-npm` and `ground-vpm`.

- Whole projected Silikatny site, not KPP1; one new Ground master for NPM and VPM.
- Ground coverings/materials from the current PZU, relief from authoritative design marks.
- VPM Ground UCX only: closed convex pieces, gap 2–10 mm, model-to-UCX deviation <=100 mm,
  triangle budget D012. No MAF/Flora/lighting collision and no NPM UCX.
- Place matching MAF from `G:/Мой диск/AGR-assets/maf`, by article/dimensions and source plan.
  [D284] permits type/size CANDIDATES where article identity is unconfirmed; never label
  them matched, list every choice for the full-site picture and preserve the libraries.
- Place Flora from `G:/Мой диск/AGR-assets/flora`, by source schedule/planting symbols and legend.
  Missing library types/species are listed, never invented, substituted or modelled.
- NPM Ground+MAF+Flora <=180,000 triangles. If exceeded, bring distribution options;
  delete nothing. Do not smooth disputed small relief steps (C37).
- Read back exports, run area validators, report per-area reproduction and historical comparison.
  No passed=true with an incomplete mandatory/manual gate.

## Gate 1 / scope authority

- Question/candidates/composition: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6848979701
- Site/scope approval: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6850169203
- Fresh PZU / planting-search instruction: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6851013290

Source-content decision [D275]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6852165269
approves boundary 33FBCEF, the planting plan/table and the named VP definition. Those questions are closed.
The delegated zero and exact pilot plan are answered [D282]: 142.10 m from VP_5 floor-mark
pair 33F8EC4/33F8EC5; 5.6 m maple nominal. `parts-pilot-confirmed.json` records the issue answer,
while `parts-pilot-draft.json` preserves the exact accepted draft. The plan proposes the
source window XY [820,11024]–[850,11046] clipped to 33FBCEF and the six position-3 maples.
The source-only DXF contains one boundary polyline and 52 POINTs, not constructed delivery geometry.

## Inputs and cold-context boundary

`sources.json` pins preserved copies of the fresh Telegram PZU and MAF DOCX. Original and copy hashes
were checked before/after copying. AutoCAD runs only on a disposable third copy. No earlier Silikatny
build scripts, meshes, transforms or reports are used. Shared procedures and library catalogues only.
The historical #906/#969/#1178 comparison is reserved for the reproduction report, not build hints.

## Не трогать

Original sources, accepted models, library geometry/material IDs, main, other agents' scenes/worktrees.
No PDF-to-MAF modelling (#425), no KPP1, no library edits, no source purging or saving over originals.

## Pilot and acceptance

One small source-resolved plot portion through Ground/UCX/library placements/export/readback;
show an image and wait for Artem's acceptance before the rest. The present `source-boundary-question.png`
is a source-contour question diagram, NOT that pilot or its acceptance.

## Current state

Gate 1 site/scope and source-content authority answered [D272, D275]. Boundary and all 52 source planting
symbols extracted, 52/52 inside the approved boundary and preserved by DXF readback. Numbered callouts
match all five point-plant schedule quantities (1, 4, 6, 17, 24). A linden-named CAD symbol is position 2/4,
not authority to substitute linden for Red Sunset. Flora candidates remain subject to identity/size checks.
MAF: all 32 DOCX rows accounted for; no certified SKU-to-model match yet (not proof of disk-wide absence).
Current continuation is [CONTINUATION-v007.md](CONTINUATION-v007.md). [D281] answers
G1–G3; [D284] supplies the standing sliver/TIN/draw-order rule without repeated small
questions. First pilot geometry remains [D283]; zero/5.6 m plan remain [D282].
[D287] closes the v006/r5 picture choice: all 38 MAF kept as accepted-by-picture,
not article-matched; 4,582 plants and composition accepted as visual direction.
A101 Royal Red maps allowed as 'interim - green A. platanoides missing in the library';
this is not final texture or technical acceptance. Do not reopen these closed gates.

Actual v007/r1 retains 58,896 Ground triangles each, 38 MAF across 10 rows and 4,582
plants; 600 VPM-only UCX /6,876 triangles. Native Max verifies 172,437 /806,914 render
triangles; raw-export controls 4,620/4,620 each, UnitScaleFactor=100. VPM hedge sheet
spacing repaired on copies; no instances dropped. Ground-only xView is 0/0/0;
whole-file xView remains FAIL (NPM3,386 /VPM47,072 overlapping faces).

Independent double-precision UCX audit corrects the earlier float32 normal false
positive at427: all600 convex. Sampled coverage175,688 points <=79.836mm; no continuous
maximum claim, wide-neighbour set remains open. NPM native public validator FAIL;
VPM default600s timeout and unchanged-reader topology crash, not importer failure.

New decision boundary: C44 intended cross-card Flora intersections versus the
<=100 per-mesh regulatory count in the required single Flora object. One actual
NPM library Physocarpus already has111 self-intersections and no duplicates;
11 explicitly synthetic non-overlapping maple stars have297. No waiver, per-plant
reinterpretation or silhouette-changing route is silently applied. Other xView,
skirt/details/material/atlas/UDIM/gap/native-validator repairs remain worker-owned.
Abies1 /Red Sunset4 /22MAFrows /133m2 flowerbed-rate gaps remain listed, not invented.
Eight original non-Acer maps are absent; actual A101 candidates and ambiguous Syringa
labels are pinned, not silently bound. Technical QA, final user acceptance, SINTEZ
and publication remain incomplete; no readiness increase.
