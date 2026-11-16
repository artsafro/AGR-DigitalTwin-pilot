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

Source-content decision [D290]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6852165269
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

v021 introduces ONE new NPM Ground/profile/budget scope question, NOT another
Table/Bench025/hedge/composition gate: issue comment6922279811. May a derived
NPM Ground differ<=8.2mm vertically from the current master, including base+whole
skirt-2.5mm, while retaining the actual finished5064tri Bench construction in
all7NPMcopies and leaving VPM unchanged? No answer yet. See CONTINUATION-v021.md
and question-receipt-v021.json. All v021 options remain UNADOPTED: the projected
179447NPMbudget is not an exported-site result;5mm local guard fails at8.179619mm,
one inverted triangle and tiny excess domain remain worker-owned. Current resume
artifacts are still v020/site-urn-r3 NPM and v020/site-ucx-r4 VPM. No library edit,
instance deletion, technical waiver, finalvisual request or completed delivery.

Gate 1 site/scope and source-content authority answered [D272, D290]. Boundary and all 52 source planting
symbols extracted, 52/52 inside the approved boundary and preserved by DXF readback. Numbered callouts
match all five point-plant schedule quantities (1, 4, 6, 17, 24). A linden-named CAD symbol is position 2/4,
not authority to substitute linden for Red Sunset. Flora candidates remain subject to identity/size checks.
MAF: all 32 DOCX rows accounted for; no certified SKU-to-model match yet (not proof of disk-wide absence).
Current continuation is [CONTINUATION-v011.md](CONTINUATION-v011.md). [D318] rejects
v010's31–32% crowns and authorizes continuous hedge-run volumes with>=68% retained
constituent crowns and all original IDs/counts/points/heights in the census.
Real v011/r2 candidate exports retain4,582plants/38MAF,162,743/334,928render
triangles; independently measured support minima78.225%/78.655%,0below68%.
All47nonhedge copies and Ground/MAF/600UCX actual arrays remain unchanged.
Individual heights are census facts, not independent bboxes of a merged volume;
envelope top differences up to0.181/0.222m are disclosed. A separate90plant
changed-construction pilot awaits the required [D314] picture choice; this is not
a repeat of [D318], composition or earlier shrub-star approval. Technical FAILs
remain worker-owned. Later r3/r5 topology experiments are rejected, not promoted.
[D294] remains the historical cell-pilot answer, not approval of the rejected
whole-site v010 candidate. [D281] answers
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

[D314] / issue comment 6878796926 authorizes a changed-copy Flora representation,
not a C44 waiver: retain species, all 4,582 instances, planting points and accepted
height/crown ranges; keep NPM <=180,000. Show a separate small construction pilot
and wait for its picture approval before site-wide application. [D291] / issue comment
6880380487 accepts the v008/r2 shrub shape/centre/Hydrangea without edits. This gate
is CLOSED: v009/r1 actually replicates 4,576 shrubs, retaining all 4,582 plants,
38 MAF and planting points; NPM157,141/VPM617,840 render triangles. v009/r2 adds
one interim Flora atlas without changing geometry. No technical/delivery waiver.
Aggregate hedge contacts remain FAIL despite isolated-pilot success; the original
v007/r1 is historical, not the current full-site export.
[D315] / issue comment 6890885700 accepts the v011/r2 90-plant continuous hedge
silhouette and common top envelope without edits for site-wide replication. The
[D314] construction-picture gate is CLOSED. v012/r1 retains the site-wide volumes,
corrects one-based xView witness handling in a bounded numerical edge repair,
and exports actual 162,159 NPM /334,422 VPM render triangles. All 4,582 census
records, 38 MAF and planting points remain; the 68% floor is not reopened.
NPM Flora xView is now 0 faces /0 vertices /0 bowties, but whole-site technical QA
still FAILs. See `CONTINUATION-v012.md` for the new MAF source-construction choice;
this is not another Flora or composition gate.

[D305] / issue comment6892163018 authorizes constructive repair of COPIES of the
seven library MAF types, including real insets/joints and necessary3-5mm details
to6.2mm; retain38IDs/counts/points/rotations and overall dimensions under[D094].
Library originals stay untouched. Separate before/after pilot FIRST, replication
ONLY after Artem accepts it. v013/r2 Bench025 pilot uses measured source frame
holes/slab,116triangles each, exported raw/native xView0/0/0/0area; it is NOT in
the site. See `CONTINUATION-v013.md` for its new construction-picture gate. The
previous copy-repair scope question is CLOSED, not asked again.

[D316] / issue comment6893485374 ACCEPTS Bench025v013/r2 and authorizes the same
constructive approach on the other MAF copies. That pilot gate is CLOSED. v014
actually replicates the exact accepted116triangle bench to2/2existing copies,
162011NPM/334274VPMrender triangles; all38MAF/4582census remain,36otherMAF and
Ground/Flora/600UCX actual arrays exact. Other-type failed attempts are NOT adopted.
A NEW Table016 representation option would merge76real wood planks/physical slots
into a continuous tabletop/four seat sectors, preserving four real access gaps.
This is beyond the earlier small joint/wall repair, not another D316 question.
The actual2108triangle raw/native-clean option remains UNADOPTED until Artem's
one representation choice. See `CONTINUATION-v014.md`; the r1missing-seat option
and old smooth-shaded sheet are superseded. Whole-site technical FAILs remain.

[D319] / issue comment6896446736 ACCEPTS the r4continuous Table016 construction
for12NPMcopies ONLY. v015actually adopts it there:172487NPMrawtriangles; all12
actual Tables raw/native-clean0/0/0/0area,38MAF/4582census retained. VPM334274raw
triangles and EVERY actual mesh array stay exact againstv014; physical slats/gaps
are not replaced by NPM surfaces. Plank divisions on NPM still need texture work.
That representation choice is CLOSED. Three VPM source-profile/joint repair routes
remain rejected (latest bounded cleanup70faces/0vertices). [D321] / issue comment
6901183418 closes the later parametric-pilot scope: ONE VPMcopy with76physical
slats, geometric gaps>=6.2mm, rebuilt rings/frame; show a before/after mesh
screenshot without opening Max for Artem. Replicate12VPMcopies only after explicit
yes. NPM[D319]stays unchanged. Answer6903084291 (2026-11-16, «Принимаю, ок»)
accepts the v016/r3b form/silhouette for technical finishing: this picture gate is
CLOSED and must not be repeated. v017 eliminates actual18face failures without
checker edits;4920triangle pilot passes pre/raw/native xView0/0/0/0,76wood/72slots/
288access controls. Only after this geometry QA,12VPMcopies were replicated:
319154raw/native triangles, all24placed-instance checks clean, no native face loss.
Accepted-form sampled10k+10k deviation2.696/2.583mm, NOT exact Hausdorff.
NPMbyte-unchanged;26otherMAF/Ground/Flora/600UCX actual arrays exact. Whole site
still FAIL. Resume SITE fromv017/site-table-r1/VPM (NPM remainsv015); other-type
isolated candidates are NOT adopted, even when their xView is clean. Surface probes
found lost cavities/slots and a raised low Sand post; retain failed artifacts.
See `CONTINUATION-v017.md`. No new user model question is pending.

Other xView/skirt/details/material/atlas/UDIM/gap/native-validator repairs remain worker-owned.
Abies1 /Red Sunset4 /22MAFrows /133m2 flowerbed-rate gaps remain listed, not invented.
Eight original non-Acer maps are absent; actual A101 candidates and ambiguous Syringa
labels are pinned, not silently bound. Technical QA, final user acceptance, SINTEZ
and publication remain incomplete; no readiness increase.

## v018 historical continuation

[CONTINUATION-v018.md](CONTINUATION-v018.md) supersedes the resume site above.
D305/D316source-bound repair actually adopted16Sand/Bike/Urn copies in EACH profile:
NPM178571raw/178556native, VPM301662/301662; all64actual placed-instance xView
checks clean,22otherMAF/profile and Ground/Flora/600UCX arrays exact.38MAF and
4582plant census retained. Complete actual Ground-to-UCX numerical upper bound
0.08993564479232127m<0.1m covers57226toptriangles,450783partition vertices, no
unassigned region. This does NOT waive213wide-neighbour gaps or final checks.
Only these16paired copies are adopted. Bench013has source-fidelity progress but
actualraw/native1area-onlyFAIL; Canopy union stillFAIL. Wholepublicvalidators
bothFAIL; finalvisual/material/SINTEZ not yet reached. Resume BOTH profiles from
v018/site-three-r1; never promote an isolated partial-pass artifact. No new human
question is pending. All prior model/picture gates, particularlyD321, stay closed.

## v019 current continuation

[CONTINUATION-v019.md](CONTINUATION-v019.md) supersedes the resume locations above:
NPM stays v018/site-three-r1; VPM is v019/site-bench-r1. D305/D316 source-bound
constructive finishing actually repairs7VPMBench013copies after clean isolated
pre/raw/native QA; all14placed raw/native checks clean,311042actual triangles/no
native face loss,31otherMAF/Ground/Flora/600UCX exact. NPM178571/178556unchanged.
All38MAF/4582census retained. Source-filling NPMBench and slope-penetrating Urn
paired trial are REJECTED, never resume fromsite-urn-r1. Render-only VPMxView
3604faces0vertices36bowtiesFAIL; new all601partscope3693/44/36includes unchanged
UCX89faces44nearvertices, not a render regression. Complete89.936mmUCXcoverage
bound remains applicable only by actual-array equality;213widepairs remainopen.
454affected tests pass/5historical deselected; separate4unresolvedtestsFAIL.
No new human/model gate, no readiness/deliveryPASS; technical repairs worker-owned.
Full suite: deferred to merge batch (rule 68).

## v020 current continuation

[CONTINUATION-v020.md](CONTINUATION-v020.md) supersedes ALL resume locations above:
NPMv020/site-urn-r3, VPMv020/site-ucx-r4. FourUrn floor joints are technically
finished with bounds/pivots/sourcecensus preserved, every changed shelf completely
below actualGround by>=9.281mm;8placed raw/native checks clean. Only9Z coordinates
per Urn changed. UCX564pieces/6564tris, actualraw/native allUCX0/0/0/0;36original
pieces certified redundant by NEW complete57226triangle coverage proof,
446541partitionvertices/89.935644792mm upperbound/0unassigned/0degenerate.
Retained564UCX/render arrays EXACT against corresponding previous raw/native exports.
175wideUCXpairs remainOPEN, not a gap waiver.38MAF/4582plants retained;
NPM178571raw178556native/VPM311042rawnative, nativeNPM15face lossFAIL.
WholeVPM3595faces0vertices36bowties and nativevalidator3/3/1/5FAIL.
Rejected NPMBench/Canopy/UCXmerge/cluster/reconstructedr3 never promoted.
483affectedpass/5historical deselected; separateCURRENT4failed, isolated3failed2passed.
286Drivefiles351458541bytes sealed,22original/source/library/map/resume hashes equal.
No new user question; all prior model/picture gates stay CLOSED. Technical work
remains worker-owned; finalvisual/material and completeSINTEZ only after repairs.
Full suite: deferred to merge batch (rule 68).
