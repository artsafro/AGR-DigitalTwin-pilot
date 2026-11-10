# elv-tc-vpm — colleague review of delivery v005 against the album and Revit (2026-11-10)

**What the model missed**, as seen by a second modeller. Recorded by Claude on branch `job/elv-tc-vpm-album-review`;
the model is not changed here.

## Header

| | |
|---|---|
| Reviewer | Влад Жуков (3D, team chat «3D_A&V», topic «Среда ВПМ») |
| When | 2026-11-10 09:42–11:13 (chat ids 1540–1612); context 1532–1535 (2026-11-09) |
| Compared | our accepted v005 work FBX `SM_Elevatornaya_Vl_1_A_001_work_quads` (sent 2026-11-06, id 1507), textured in 3ds Max with UDIM Viewer (id 1556–1568) **vs** the AGR booklet PDF (42 sheets, id 1509) and the Revit FBX (id 1510), overlaid in one Max scene |
| Inputs (git-ignored) | `outputs/review-album-v001/thread.txt` (message text), `download_map.txt` (id → jpg), `screens/` (60 jpgs) |
| User remarks in the thread | 1585 «Это освещение» (the yellow / purple lines); 1613 «надписи на фасаде позже дадут»; 1604 asked for render-vs-PDF differences (answered 1606–1610) |
| Verified against | booklet text (PyMuPDF, sheets 18, 19, 30, 31), Revit FBX object names (9 808 models, 207 family/type names), `parts/elv_full_parts_v003.json`, `scripts/` (build, UV, export), `library/windows/window_types.json`, `TASK.md` |
| Not available | the v005 geometry itself: `C:\x\elv_view_v005\` is gone and job outputs are not in this worktree, so no measurement on our mesh. Findings that need one are class (e) |

Screens are named by their download time (UTC+0, one hour behind the chat time): `screens/photo_2026-11-10_HH-MM-SS[ (n)].jpg`.
Below, `08-44-02` means `screens/photo_2026-11-10_08-44-02.jpg`, `08-44-02(1)` its second photo.
A caption belongs to the first photo of a moment; the next uncaptioned photo is its pair (ours vs Revit / PDF).

Classes: **(a)** our build error or omission against the sources; **(b)** album, renders and Revit disagree and we
followed the FBX or a recorded decision; **(c)** deliberate simplification or user decision; **(d)** not a defect,
reviewer misread; **(e)** unclear, needs a measurement or the user. «TASK D07» etc. are the job's dispute numbers in
`TASK.md`, not project decisions `[D<n>]`.

## Findings

| # | Влад (quote) | Ids / screens | Where | Album / Revit shows | v005 has | Class |
|---|---|---|---|---|---|---|
| F01 | «вент боксы отличаются … короче это по всюду» | 1541–1545; `08-44-02`, `08-44-02(1)`, `08-44-26`, `08-44-26(1)`, `08-45-24` | main roof, all vent shafts, exits, cups, curbs | Revit: open steel frames with caps, brick shafts with louvres, curbs with open centres, rows of open «металлический стакан» frames (45 pcs) | one bbox box per cluster (P37 «bbox boxes (simplified)»), cups as solid boxes | (c) — our simplification in the parts list, Gate 1 for P21–P42 accepted 2026-11-05. Reviewer finds it too coarse; candidate for re-decision (Q1) |
| F02 | «заборы отличаются и сверху ботто не закончены» | 1548; `08-46-37` | roof zone between T1/T2 superstructures and the skylight (north-east roof) | Revit has 51 «(Ext)_(Ins-150)_(RAL7021)_ограждение кровли» screen walls and 9 «Сетка-Рабица» mesh doors | screens built from the terrace fence panels at y −19.17 only (P33); Влад's red contour runs along sides where ours has none | (e) — likely (a); needs an overlay of Revit screen walls on our P33 |
| F03 | «двери и врата отличаются … вообщем это по всюду» | 1550–1553; `08-48-46`, `08-48-46(1)`, `08-49-18`, `08-49-18(1)` | TP annex and service doors, all facades | Revit «(DR)-2H_TransformerPlant» leaves with two louvre bands each; frames proud of the wall; thresholds / sill plates break the plinth flashing | library ELV-11 «Дверь глухая двупольная» as an opaque leaf (no louvres in geometry or texture); leaves near flush, no proud frame, plinth flashing runs through | (a) — louvres and frames dropped when the type was reduced; ≤ 5 cm detail should have gone to the texture (reg p.32 §7), it went nowhere |
| F04 | «отличие двери» | 1554–1555; `08-50-26`, `08-50-26(1)` | sandwich facade doors (No 1/4/11/21/25) | Revit leaf without glass | ELV-21 with a vision panel | (b) — booklet sheets 18/19 and the customer TZ; user accepted v003 «Принимаю всё» (TASK, Delivery v003) |
| F05 | «здесь явно должна быть еще геометрия не только стекло» | 1558–1559; `08-51-32`, `08-51-32(1)` | main entrance И-А, revolving door | booklet sheet 18 item 2 and renders: framed drum (posts, top ring) | ELV-17: MainGlass drum + Main disc; with glass hidden only the disc is left, no posts or frame | (a) — not in the FBX, built from the booklet [TASK D07], but without the frame the booklet and renders show |
| F06 | «не доведенно» | 1561–1562; `08-55-00`, `08-55-00(1)` | parapet over the wood volume, north-east edge | Revit: parapet cap and inner ledge run to the end | inner ledge / cap seems to stop short of the step | (e) — needs a close-up of P12/P31 at that end |
| F07 | «нет таких странных кубиков» | 1563; `08-55-27` | main roof, small dark cubes | the same cubes are in the Revit overlay (`08-44-02(1)`) | 16 KPN-S mounting cups kept as boxes (P37, Revit «Стакан_монтажный_KPN-S» 30/56/90) | (d) — present in the Revit FBX |
| F08 | «тоже забор» | 1564; `09-11-05` | roof terrace railing | Revit «Square_4_rail(h-1200)», four rails | posts + top rail (P34) | (c) — user 2026-11-04: railings simple geometry, not alpha (TASK) |
| F09 | «сглаживание не настроенно» | 1565; `09-11-37` | all R 3.15 corners and curved bands | smooth curved surfaces | faceted: no script sets smooth shading; export `mesh_smooth_type="FACE"` on all-flat faces (`delivery_export_v005.py`, `work_export_v005.py`) | (a) — breaks reg p.8 §3.15 / p.29 §3.14 / p.43 fig. 4.1 (`docs/domain/geometry.md`: smoothing groups, no shading defects) |
| F10 | «такие эелементы отсуствуют на впм» | 1566–1567; `09-12-55`, `09-12-55(1)` | fire ladder at the parapet | Revit: a guard panel (mesh / plate) on the ladder at parapet height | stringers + rungs only (P38) | (a) — minor; the Revit element at the ladder was not carried over and not listed as dropped |
| F11 | «какаято странная синяя полоса … на ревит такого нету» | 1570–1571; `09-25-43`, `09-25-43(1)`, also `09-38-00`, `09-39-20(1)`, `09-40-54(1)`, `09-42-34` | base flashing, every facade | Revit: plinth battens z 0.15–0.42 (geometry is there); «RAL 5025» only on the two И-А base flashings; booklet fragment 9-10: plinth RAL 7021 | base flashing RAL 5024 (pastel blue) around the whole building | (a) — TASK D13 zones say 5024 only over curtain walls, 7021 elsewhere, and P25 in the parts list says RAL 7021; the v004 build note «5024 continued on P25» contradicts both. The user accepted the v002 renders that showed it, without a call-out |
| F12 | «на ревитке эти гаражные двери серые на впм черные» | 1572–1573; `09-26-56`, `09-26-56(1)`; render `09-38-00(1)` … `09-39-20` | 4 loading docks, rear facade | Revit and renders: dock shelters light grey | ID26 «DockShelter_9005» (jet black), colour with no source cited | (a) — colour picked by us, not from a source |
| F13 | «на пдф желтый материал имиеет текстуры а черный материал выглядет по темнее» | 1574–1575; `09-29-52`, `09-29-52(1)` | wood volumes, lower cassette | render: wood grain; darker cassette | smooth wood #C1AE93; cassette RAL 7024 | (c) — customer TZ + user 2026-11-05 (smooth cassettes per site photo, 7024; v004 colour accepted) |
| F14 | «на впм какието синие текстуры старнные» | 1576; `09-30-26` | curtain-wall bands И-А | booklet sheet 18 item 7: «стемалит RAL 5024» | stemalit tiles RAL 5024 (teal in a flat viewport) | (d) — booklet colour [TASK D06] |
| F15 | «в пдф есть такие тексты» / «в впм нету но есть какието обводки»; «ОТСУТСВУЮТ ЭТИ ТАБЛИЧКИ С ТЕКСТУОМИ»; «нету этого текста геомсетрии»; «эти знаки и рисунки» | 1577–1578, 1583–1584, 1595–1596, 1609–1610; `09-30-55`, `09-31-17`, `09-38-00`, `09-38-00(1)`, `09-43-49`, `09-43-49(1)`, `10-04-35`, `10-04-35(1)` | tenant signs, «СРЕDА» roof letters, address plate | renders: brands, logos, plates; drawings: frames | sign frames only, no brands, no letters | (c) — TASK D09 (frames, no brands), «СРЕDА» waits for the signage TZ (TASK); user 1613 «надписи на фасаде позже дадут» |
| F16 | «отличие разрезов плитки» | 1579–1580; `09-31-56`, `09-31-56(1)` | entrance portal over the revolving door | render: one dark cassette band, regular cuts | ELV-16 pane and transom layout from the FBX | (b) — FBX is primary where it matches the album (TASK); render differs from both |
| F17 | «геометрия этих деревянных декоров\проходов на пдф другая» | 1581–1582; `09-33-28`, `09-33-28(1)` | wood canopies with lamellas, south and west doors | render: dense full-width lamellas under a thick beam; booklet fragment 9-10: 4 lamellas | lamella positions from the FBX (P19/P30), canopies per [TASK D14] | (b) — render, booklet fragment and FBX disagree; we followed the FBX |
| F18 | «СТРАННЫЕ ЖЕЛТЫЕ И ФИОЛЕТОВЫЕ ЛИНИИ» | 1583; `09-38-00` | parapet and facade lines | booklet sheets 33–35 lighting | glow faces ID28 purple / ID29–30 2700K/2000K (P42) | (d) — lighting, user 1585 «Это освещение» |
| F19 | «ОТЛИЧИЕ ОТ ПДФ В ГЕОМЕТРИИ И ЦВЕТЕ и в детализации» | 1587–1588; `09-39-20`, `09-39-20(1)` | rear (north-west) facade | render: two tones of sandwich, light-grey dock houses, caged ladders, TP cabinet with louvres | one tone RAL 7021 [TASK D02]; docks F12; ladders F20; TP F23 | (b) for the tone — drawings over renders (TASK); rest under F12, F20, F23 |
| F20 | (red marks on the two ladders) | 1589–1590, 1593–1594; `09-40-54`, `09-40-54(1)`, `09-42-34(1)` | fire ladders, north facade 6-1 | renders: ladders with safety cages; booklet sheet 30: «лестница типа П1» | ladders present, no cage (P38 «no cage») | (c) — documented simplification, accepted at Gate 1; open whether a cage is required (Q4) |
| F21 | «нету лестницы» | 1591–1592; `09-41-26`, `09-41-26(1)` | top of the wood volume, north-east corner | render sheet 17: ladder / railing over the parapet | closed sandwich box, no ladder | (e) — not checked against Revit at that point |
| F22 | «отличается рисунок» | 1593–1594; `09-42-34`, `09-42-34(1)` | north sandwich facade, horizontal lines | render: two continuous strip lines at two levels | joint lattice per plane [Q1 of v005] + P44 cover strips where Revit has them (9 hidden strips not built, user v003) | (e) — need to check that P44 reads on this facade; the render may only show the strips we have |
| F23 | «тут явно что то должно было быть» | 1597–1598; `09-44-57`, `09-44-57(1)` | TP annex doors | booklet sheet 18 item 13 «вентиляционная решетка, цвет RAL 7021»: two grilles and a canopy bar over the doors | painted box, door outlines only | (a) — booklet-only element, not built and not in the dispute list |
| F24 | «тут должен был быть сточная труба» | 1599–1600; `09-46-05`, `09-46-05(1)` | south canopy, axes 9-10 | booklet fragment 9-10 and section Б-Б: round downpipe with elbows from the canopy gutter | P39 downpipe exists as a 100 × 100 box at x 10.455, but in the textured view it reads as a beige post | (e) — likely (a): the box shape and, if its UVs sit in a wood region, the texture; check P39 tile in v005 |
| F25 | «вообще странно что схема в пдф отличается от тех же рендеров и ревит модели»; «главный вход» | 1601–1602, 1606–1608; `09-47-21`, `09-47-22`, `10-03-30`, `10-03-30(1)`, `10-03-30(2)` | main entrance И-А | elevation 1: sliding + swing doors; elevation 2: two dark door sets; render: revolving door; Revit: no revolving door | revolving door Ø 4.12 [TASK D07] | (b) — album disagrees with itself; plan sheet 25 + legend item 2 + renders chose the revolving door |

Context, not findings: 1532–1534 Влад: the roof and parapet walls will be hard for collisions. The work FBX has no UCX by
[D198], although the delivery package has 959 UCX boxes; see root cause R5.

## Per-class summary

| Class | Count | Findings |
|---|---|---|
| (a) our miss | 7 | F03 door louvres / frames, F05 revolving-door frame, F09 smoothing, F10 ladder guard, F11 base flashing colour, F12 dock shelter colour, F23 TP grilles |
| (b) sources disagree, we followed FBX / decision | 5 | F04, F16, F17, F19, F25 |
| (c) simplification / user decision | 5 | F01 roof boxes, F08 railings, F13 wood / cassette colour, F15 signage, F20 ladder cages |
| (d) not a defect | 3 | F07 KPN-S cups, F14 stemalit, F18 lighting |
| (e) unclear | 5 | F02 roof fence, F06 parapet end, F21 roof ladder, F22 strip lines, F24 downpipe (F02, F24 lean to (a)) |

The biggest visible misses we own: **F09** (faceted curves on every corner of the building), **F11** (a blue band
around the whole base), **F01** (roof equipment as bare boxes; ours by choice, but it is what a viewer sees from above),
then the door / TP detail (**F03**, **F23**).

## Root causes (class a, plus the (e) items that lean to a)

| # | Cause | Findings | Gate that exists | Gate that is missing |
|---|---|---|---|---|
| R1 | **No element census from source to build.** Intake compared FBX and album on primary geometry and produced disputes D01–D16. Secondary elements (louvres, grilles, ladder guards, drum frames, roof screens) were never listed one by one, so dropping them left no trace. Library types were reduced to «opaque leaf» without a note on what the source had | F03, F05, F10, F23, (F02, F21) | parts list with Gate 1 (per part, not per source element); window/door census (types and sizes, not their detail) | a census of every source family (Revit names + counts) and every booklet legend item, each mapped to a part, a texture, or «dropped, because …»; unmapped = open at Gate 1 |
| R2 | **Nothing looks at shading.** All builders create flat faces; both exports write FACE smoothing; validator, xView, readback and SINTEZ do not flag faceted curves; the contact renders were small and evenly lit | F09 | `docs/domain/geometry.md` already states the rule (reg p.8 §3.15, p.29 §3.14, p.43) | a check on the work FBX: edges between faces at < ~30° on a curved band must not be hard; plus one grazing-light close-up of an R 3.15 corner in the acceptance pack |
| R3 | **Colours without provenance.** ID26 got RAL 9005 with no source. The base flashing 5024 was extended by a build note against TASK D13 and against our own parts list (P25 = 7021); nothing compares built colours with the parts list or the zone rule | F11, F12 | TASK D-list; parts-list legend items | per working ID a cited source (booklet item, TASK D, user); a build assertion that face colours match the parts-list legend and zone rules |
| R4 | **Acceptance on overview renders.** The user accepted v002–v005 «as rendered». Detail misses (doors, TP, roof boxes, ladder end) are not visible at that scale, so acceptance did not test them (the same pattern as retro section 3: our gates prove the file is legal, not that it looks finished) | F01, F03, F05, F06, F23 | visual acceptance on contact sheets | side-by-side close-ups, Revit / booklet vs ours, one per element class (doors, roof equipment, ladders, entrances, parapet ends) |
| R5 | **Review hand-off lacked the collisions.** The colleague got the work FBX ([D198]: no UCX) and planned to build collisions that the delivery package already has | (process) | [D198] work FBX next to the package | when a work FBX goes to a person for edits, say where the UCX are, or send them with it |

## Proposed checks and rules (proposals only — nothing here is decided)

1. **Source element census** (R1): at intake, list Revit FBX families with counts and booklet legend items; map each
   to part / texture / dropped-with-reason in the parts list; Gate 1 shows the unmapped ones. Would have caught F03,
   F05, F10, F23 and probably F02, F21.
2. **Shading check** (R2): in the look-finished gate proposed in the retro (section 6, #1), add «hard edges inside
   curved bands» on the work FBX, and a grazing-light close-up of one R 3.15 corner. Would have caught F09.
3. **Colour provenance** (R3): every working ID in the tex spec carries a source; the build asserts zone rules (TASK
   D13) and the parts-list colour per part. Would have caught F11, F12.
4. **Detail acceptance sheet** (R4): close-up pairs, source vs ours, per element class, before the user accepts a
   version. Would have shown F01, F03, F05, F06, F23.
5. **Work-FBX hand-off note** (R5): name the UCX source when the work FBX goes to a person.

These extend retro proposals #1 (look-finished gate) and #9 (colour swatch); they wait for the user's «да».

## Open questions for the user

1. **Roof equipment (F01).** Keep the bbox boxes or rebuild the 26 shafts / exits as Revit shows (open frames with
   caps, brick shafts, open curbs)? *Recommendation:* rebuild them as simple multi-box forms (frame, cap, curb ring)
   within the VPM budget; the KPN-S cups stay boxes.
2. **Base flashing (F11).** Return to TASK D13: RAL 5024 only under the И-А curtain wall, RAL 7021 on all other
   facades? *Recommendation:* yes.
3. **Dock shelters (F12).** Which colour? *Recommendation:* light grey as in Revit and the renders; RAL 7040 like the
   gates unless you have the product colour.
4. **Ladder cages (F20).** Add safety cages to the fire ladders (renders show them; booklet type П1)?
   *Recommendation:* yes, simple hoops and 3–5 vertical bars as geometry, like the ladders.
5. **Who fixes and on which base.** TASK says no more geometry changes in Max from Claude. Do Света / Влад apply this
   list by hand on the v005 work FBX, or do we patch the generator (v009) and hand over a new work FBX?
   *Recommendation:* we fix the generator-side items (F09 smoothing, F11, F12 colours, F23 grilles, F03 louvres in
   the texture) and verify the (e) items on the v005 geometry; the hand-modelled items (F01, F05, F10) go to Света.
