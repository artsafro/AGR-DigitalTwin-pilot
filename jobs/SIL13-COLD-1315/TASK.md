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

These approve the site and proposed scope, not unidentified buried block definitions or a fabricated
confirmed PartsList. `parts.json` is deferred until the source-authority questions in REPORT are answered.
Nothing has been constructed.

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

Read-only intake only. Gate 1 site/scope answered; inputs authority blocked on the unreferenced planting
and vertical-planning definitions, and confirmation of the differently named boundary candidate.
See REPORT.md and job.yaml. Technical QA, user acceptance and publication are all incomplete.
