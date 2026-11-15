# 4bk-k3 — 4БК, корпус К3 (STLB-04): VPM, then NPM

Intake per [D186], 2026-11-12. Customer A101 (Astro1). Profile: **VPM OKS** first, then **NPM** derived from it.
Cell `oks-vpm` (`docs/scenarios/oks-vpm.md`). Passport: `passport.json` / `PASSPORT.md`. Inputs and hashes: `sources.json`.
Status: **intake — questions open**, no production work yet.

## Requirement (Artem, 2026-11-12, verbatim excerpts)

> «Задача будет сделать ВПМ, а потом сделать НПМ.»
> «Влад успел сделать типовой этаж, капсулы. На типовом этаже рейки, и металлический пояс, который впоследствии надо
> будет соединить ... отдельно стоящий маленький стилобатик, сделал окна, все разложено на ID.»
> «Есть ТЗ от архитектора по текстурам, по кирпичу, по швам, логика, как швы должны быть на текстуре, лежать на объекте.»
> «Есть типовые этажи, потом межэтажные металлические проставки, которые тоже, как я понимаю, типовые. Их две штуки.
> И потом есть верхняя надстройка, часть, которая из металла, и часть, которая из кирпича.»
> «Первый этаж мы пока что у большого корпуса не моделим. У мелкого корпуса ... только кровля осталась. Козырьки
> стеклянные и лестница с другой стороны.»
> «Смоделировать типовые части, понять, что они нормально стыкуются ... одну разложим, затекстурим, поймем логику,
> потом уже размножим наверх.» «Уникальная будет верхняя надстройка ... другое сечение, и другие окошки.»
> «На кровле у нас есть пергола ... разные поверхности, которые раскладываются на ID-шку, плюс ограждение.»

Meeting note 2026-11-11 (Zoom My Notes «Рабочая сессия: Моделирование и подготовка третьего корпуса к VPM/NPM»):
deadline — VPM of K3 (tower + stylobate) by the end of the week; interiors by extruding the window polygon ~1 m inward;
UV first, UDIM, then replicate; brick → UDIM 1, tile with joints → UDIM 2; floors from 2 keep IDs 1–4, floor 1 gets
IDs 5, 6, 7…; glass transparency via map; all modelling in layer К3; naming like the previous LowPoly reference.
Vlad: tower floor 1, stair, door, Flora/ground (GAP data pending).

## Findings at intake (2026-11-12)

- `3k.max` (Max 2026.3, metres): layer `revit` = K3 FSD FBX (5787 meshes, 1.24 M tris); layer `К3` (hidden) = 5 objects:
  `Plane001` typical floor (Z 4.45..7.80, 33 windows), `Plane052` glass, `Plane053` small stylobate (Z −1.46..5.64),
  a copy of «Вентфасад фиолетовый» wall and of 101 imposts 50×50 (UV still in feet). Multi #13: ID 1 brick, 2 violet
  (АКП?), 3 reveals, 4 bottom sill, 9 frames, 10 capsules; IDs 5–8 empty. No metal belt, no level helpers yet.
- Revit levels: floor step **3.15 m**; floor 2 slab 4.45..4.65; per-floor bands Семейство1 0.7 m (4.65..5.35) and
  Семейство2 0.5 m (7.30..7.80); metal band floors at Z 23.18..26.70 (floor 8) and 38.93..42.45 (floor 13);
  terrace 51.6, parapet 58.6..59.8, top 62.23. 18 floors above ground.
- Finishes (`ТЗ_Архитекторы/file.ObyMIe.png`): K3 «Бетонная плитка под кирпич 280х85, RAL 020 30 20»; АКП RAL 4009 (bands,
  superstructure); frames, sills RAL 7024; reveals RAL 020 30 20; plaster RAL 020 30 20 on the top parapet. Note
  `photo_2026-11-11_14-49-53.jpg`: window surround on the brick facade ~RGB 122 92 96. АКП joints drawn in red on
  elevations 1/2/3.jpg; radial on rounded corners (`Screenshot_1.png`).
- `Bricks1` 4096²: running half bond 14 × 48 per tile, module 292.6 × 85.3 px (ratio 3.43 ≈ 290 × 85 mm), joint ~4 px.
- No written texture spec (no joint width, bond phase, alignment rules) in the inbox.

## Не трогать

- Everything in `…/63_4BK_vlad/inbox/` (sources, `3k.max` itself): work only in versioned copies.
- Layer `revit` geometry (reference only).
- Vlad's scope: tower floor 1, stair, door.

## Answers (Artem, 2026-11-12, verbatim excerpts)

> Q1 module: «это не совсем типовой этаж, этот модуль ... модуль первого этажа получается, ну первого относительно ...
> его нужно дорабатывать, чтобы он стал типовым ... Обрезать его правильно.»
> Q2 joints: «ТЗ от архитекторов, там картинки. На картинках показаны красными линиями или какими-то другими
> отметками как раз швы, поэтому нужно будет проанализировать картинки.» Brick: «надо брать брикс, который нам
> скинули, он уже принят.»
> Levels: «Отметки ... если ты уже их считал, то окей.»
> «Базовая стена вентфасад фиолетовый — это как раз то, что будет поясами металлическими, которые ... будут врезкой
> сделаны. Это под них болванка сделана. Но еще углы не проработаны. А прямоугольный импост — это рейки. Вертикальные.»
> Q3 IDs: «новые ID как раз под это и запланированы.» Q4: address, naming, GeoJSON — later.
> Q5: «Сцена и порядок ... я расставлю ... все остальное я принимаю.» «Изучи исходники получше ... начнешь работу по
> сценарию ВПМ.»

Resulting decisions:
- `Plane001` is the module of the first typical floor (floor 2) — to be reworked and cut correctly into the typical
  3.15 m module; floor step 3.15 from the Revit levels.
- Brick: `Bricks1` as delivered (accepted by the customer); joint/АКП panel layout read from the red lines on the
  architect's images.
- «Вентфасад фиолетовый» copy = blank for the metal bands (inset), corners not yet worked out; imposts 50×50 = vertical slats.
- IDs: 1 brick, 2 АКП RAL 4009, 3 reveals, 4 sill RAL 7024, 9 frames RAL 7024, 10 capsules; 5–8 for the new parts
  (band metal, slats, roof, pergola/railing) — exact split at texturing.
- Work in a versioned copy of `3k.max` after the user places the level points; first piece = one typical floor end to
  end, picture to Artem; then bands and joints, replication, superstructure, roof + pergola, stylobate.
- Branch `job/4bk-k3-vpm`.

## Levels (Artem's helpers, layer `helpers` in `3k.max`, read 2026-11-12)

All points at XY (55.57, 29.56). Interpretation from his description («начало → конец кирпичной кладки → металлическая
вставка → внутренняя часть → толщина металла → опять кирпич»; roof points = where the column groups land):

| Point | Z, m | Meaning | Check |
|---|---|---|---|
| Point001 | 4.450 | start (floor 2 slab underside; brick module starts 4.65) | — |
| Point002 | 23.550 | brick ends / band 1 (floor 8) metal starts | 4.65 + 6 × 3.15 = 23.55 ✓ |
| Point003 | 24.355 | band 1 inner (recessed) part starts | lip 0.805 |
| Point004 | 26.190 | band 1 inner part ends | inner 1.835 |
| Point005 | 26.700 | band 1 metal ends / brick starts | lip 0.510; band = 3.15 ✓ |
| Point006 | 39.300 | brick ends / band 2 (floor 13) starts | 26.70 + 4 × 3.15 ✓ |
| Point007 | 40.105 | band 2 inner starts | = band 1 + 15.75 ✓ |
| Point008 | 41.950 | band 2 inner ends | ✓ |
| Point009 | 42.450 | band 2 ends / brick starts | ✓ |
| Point010 | 52.710 | superstructure base / roof level 1 (columns group 1) | 42.45 + 3 × 3.15 = 51.90, +0.81 |
| Point011 | 58.200 | columns group 2 | — |
| Point012 | 59.800 | parapet top / columns group 3 | Revit parapet 58.6..59.8 |
| Point013 | 60.360 | roof level | — |
| Point014 | 62.200 | top | Revit max 62.23 |

Stack: floors 2–7 brick (6 × 3.15), floor 8 band, floors 9–12 brick (4×), floor 13 band, floors 14–16 brick (3×),
superstructure from 51.90/52.71. Band floors 8 and 13 have identical offsets → one band module, instanced.
Exact meaning of Point010–014 to confirm against the FBX roof analysis.

## Gate 1 (Artem, 2026-11-12)

> «Почти все принимаю ... цвет откосов мы берем как на PDF-ке ... основной источник истины по материалам это PDF,
> то есть папки ТЗ архитектора.» «Штукатурка ... только на внутренних стенах кровли. Парапета ... в заглушку закинем.
> Там швов не будет. А панели алюмокомпозитные со швами ... идут по всей высоте.» «Кондиционеры ... односторонние пока
> что ... по референсу ... с кондиционерами в конце разберемся. Сначала сделаем модель, потом ее распространим.»

Palette (authority: `ТЗ_Архитекторы`): brick tile = Bricks1 (course 85 mm); reveals RAL 020 30 20; window frames,
sills, metal RAL 7024; АКП panels RAL 4009 with the measured joints, full height; plaster RAL 020 30 20 only on the inner
roof-parapet walls, cap ID, no joints. AC units one-sided, placed last. Parts: `parts/k3_parts_v001.json` (confirmed).

## Brick scale (Artem, 2026-11-12)

37 courses per floor broke the half bond at every floor seam (odd count). Artem chose **38 courses per 3.15 floor**:
brick ≈ 284 × 83 mm, square tile 3.979 m, ≈ 1029 px/m, Bricks1 unchanged, no shear. Supersedes «course 85 mm» in
Gate 1 Q2. UDIM tiles are renumbered contiguously at assembly (reg p.23: no gaps).

## Typical module review (Artem, 2026-11-12, v003 in Blender)

> «Кирпич увидел, разложил хорошо, красиво.» «Пояса горизонтальные, они будут металлические ... на втором ID были.»
> «В нишах почему-то боковушки темные, а сама фронтальная часть кирпичная, тогда уже надо все делать под кирпич.»

Clarified: «Откосы ... сейчас выполнены в цвет кирпича, это правильно. Неправильно в нишах боковые стенки, что они
не кирпичные.»
→ v004: wedge bands (sloped faces of Семейство1/2) = ID2 АКП; niche side walls = ID1 brick; window reveals ID3 unchanged.

## Part joints (Artem, 2026-11-12)

> «Можно сделать так, чтобы у нас эти все кубики Лего были врезкой ... один торчал на другой, или врезался там по
> 6 миллиметров ... не обязательно точки подгонять.»

Parts (typical module, bands, superstructure, roof, stylobate) may join by embedding ≈ 6–20 mm instead of welded
vertices. Flush surfaces: «мелкую мы врезаем в большую, и у мелкой полигон, который врезался, мы просто его удаляем» —
the smaller part is embedded into the larger one and its faces that end up inside / coplanar with the larger part are
deleted (no coplanar overlap remains; the smaller part's open edge lies on the larger surface).

## Roof v001 accepted (Artem, 2026-11-12)

> «По кровле я принимаю.» «У металлика, который второй ID, тоже швы. Вот эти моменты надо все просмотреть.»

Roof: coping ID4, Семейство1 at 58.2–58.9 ID2 accepted. Next: joints on every ID2 (АКП) surface by the architect's
red lines (SOURCE_ANALYSIS «Joints»), brick joints come from Bricks1. АКП joint width 10 mm, dark (Artem,
2026-11-12); Artem sends close-up screenshots of which joints he means before the texture is made.

## UV review (Artem, 2026-11-12)

> «ID 2 занимает 4 тайла ... это окей.» «По полоскам я пока что не уверен, что ты их раскрасил по 5 сантиметров.»
> «По маленькому корпусу ... почему мы сделали его черно-белым. Он должен быть весь в кирпиче, а кровля ... серая,
> такая же, как у основного. Лестница тоже вся в кирпиче.»

→ ID2 multi-tile accepted; 5 cm АКП strips at window edges (typ_uv_v001) — open, Artem checks in Blender;
small stylobate: walls + stair = Bricks1 brick, roof grey = tower roof ID6. Then: «геометрию Влада, что ты под швы
порезал ... правильное решение ... швы должны быть на кирпиче, на текстуре отображены»; «светлый цоколь ... там все в
кирпиче» → keep the 124 cuts; brick texture baked with 10 mm panel joints; no light fascia. Plinth: «делаем как у
Влада» → Vlad's light plinth under the windows stays (own ID, light porcelain colour) (v002).
Final (Artem after checking with Vlad, 2026-11-12): «он кирпичный весь со швами как у архитектора» — our stylobate is the
brick block RIGHT of the tower in «1 эт_2.jpg» (the dark АКП block on the left is another building); all brick incl.
the plinth; «швы там по логике проёмов» → 10 mm joints on the brick: verticals at corners and opening reveals,
panels 1–2 m, horizontal at opening heads (the panel layout of the 124 cuts).

## Joint UV method (Artem, 2026-11-12)

> «Эджи вертикальные, которые идут от каждого проёма ... выбираю, что швы будут идти по левому эджу ... делаю всем
> полигонам один тексель, выравниваю по горизонтали, align по левому edge ... левый край рисую вертикальный шов на
> текстуре и кладу все полигоны друг по другу левым краем на этот шов.»

Every joint is a geometry edge (cut at openings / panel edges); panels share one texel, are straightened and stacked
by their left (joint) edge onto one painted joint line; the texture = plain field + one joint line per direction.
Target: ID2 АКП of the whole building in 2 tiles = 2 IDs (ID2, ID11), regular bitmaps visible in the Max viewport.
Refinement: «где не нарезано — шва не будет ... нарезать = уплотнение геометрии ... один тайл, где всё укладывается по
нарезке, а длинный полигон, которому нужен шов посередине, — в отдельном тайле» → tile A = stacked panels on existing
cuts; tile B = long faces with intermediate joints painted individually, no extra cuts.
2 tiles gave only 420 px/m (< 512 [D160]); Artem: «Давай 3 тайла» → tower АКП = 3 tiles / 3 IDs (ID2, ID11, ID12)
at ≥ 512 px/m, no cuts.

## Two VPM deliveries (Artem, 2026-11-12)

> «Поскольку стилобат отдельно стоящее здание, это будет отдельная ВПМ ... ВПМ большого корпуса с его текстурами и ВПМ
> мелкого корпуса с его текстурами. Не обязательно подгонять один к другому.»

Two OKS packages: the K3 tower and the small stylobate, each with its own textures, IDs and UDIM numbering.

## Tower floor 1 + small stylobate from Revit (Artem, 2026-11-14)

New source: Revit `STLB-04_AR_PRK_2025_K3_v001_отсоединено`, 3D view `K3_stylobate_v001` (id 23197235).
> «сделать первый этаж башни и стилобат маленький, отдельно стоящий ... VPM ... текстуры кирпича те же ... логику швов
> на первом этаже ... такую же, как на самом стилобате ... горизонтальные швы на верхнем этаже должны быть, наверное.»
> «Кровлю и там, и там моделим плоской, и делаем её врезкой. Вертикальные стойки на верхних стеклянных ограждениях ...
> ось стойки находится по центру оси стекла. Стекло у нас двойное. Козырьки мы пока не моделим ... Вент-решётки мы
> показываем текстурой. Окна ... с интерьерами, как выполнял Влад. Текстура ID по той же логике.»

Answers 2026-11-14: small stylobate rebuilt from the new Revit (old Plane053-based version = reference only for IDs and
joints); tower floor 1 is ours now (supersedes «Не трогать: Vlad's scope») and goes into the tower VPM package; same
branch `job/4bk-k3-vpm`. Joints on the stylobate top floor — decided at UV. Geometry in Blender, assembly in Max.
Parts by agents (Artem): bodies report openings → window agents read openings + Revit types, use `library/windows`
or add drafts, place them; roofs with railings separate. Stylobate has 2 levels, one overhangs the other: «первый
уровень будет врезкой сделан и врезаться будет в верхний уровень» → **3 bodies**: tower floor 1, stylobate level 1
(embedded into level 2), stylobate level 2. Interior elements in Revit are excluded.

Revit read 2026-11-14 (view 23197235, read-only): A = tower floor 1/podium X 56.8–108.3 Y 2.1–36.4, floor 0.00, roof
4.25–4.65, brick parapet to 5.05, glass railing 5.05–5.85 (63.5 m); 43 «Окн_Вит_Проем» openings, heads ≈ 3.15.
B = stylobate X 103.5–126.9 Y 41.8–69.9: lower tier −0.25…3.05 brick, 17 openings (+0.15…3.00/3.05); upper tier
3.05…9.45 curtain walls (импосты 50×70 step 1200, Стемалит, burgundy lamellae 50×500), soffit «Металл бордовый» at
3.00; roof 8.65–9.05, frame «Стены 1» to 9.45, railing 9.45–10.25 (71.9 m), 2 roof exit boxes to 10.63. Exclude by wall
type «Функция» = internal (140), doors (34, steel/lift), columns, shafts, furniture, plumbing, П01/П02. Canopies: 10
«ОбщМд_Козырек_Стеклянный» (not modelled yet).
Frame: project base point = Revit internal origin; shared N −14177.024, E −1251.298, abs 172.350 (= 0.000), angle to
true north 39.94°. FBX of view 23197235 exported via RevitBridge `export_fbx` (doc not saved) to
`…/63_4BK_vlad/build/revit_fbx/K3_GF_stylobate_v001.fbx` (8 180 848 B, 1719 meshes, metres, same frame as the old
parts). Railing defaults (Artem not answered yet): double glass 2×10 mm, posts 40×40 at panel joints ~1 m, post axis
on the centre line between sheets.

v001 review decisions (Artem «Да, по рекомендациям», 2026-11-14): (1) tower overhang soffit at 4.45 (+ NW arcade) is
built in body A (tower package); (2) railing posts: Revit section (A 25×25, B 34×34), full glass height, axis between
the sheets; (3) OKS perimeter extended 1 m below the bottom (reg p.28 §3.6); (4) grille-only cells get a dark back
panel; (5) stylobate roof-exit box walls = brick.

Artem's v001 review in Blender (2026-11-14, 28 empties → `…/gf_parts/_review/artem_marks_v001.json`): open polygons,
broken geometry, missing reveals and frames, flipped faces. «Двойные стёкла слишком буквально» → railing glass = ONE
glass slab (one box with thickness), not two sheets; posts on its axis. Blind doors / grilles do not reach down (hole
under them). A colonnade zone (columns + walls next to them, NW) badly done: half the windows and parts missing.
Stylobate «4−»: not all frames, an open polygon sticks out; Стемалит panels have no reveals, embed nowhere, no frame on
the upper floor. Tower floor 1 «на троечку» — rework. The v002 fix run was stopped; next round is v003.
Correction (Artem): no soffit at 4.45 in our parts — «подшивку будет давать башня сверху»; columns embed into the
tower's bottom polygon (supersedes decision (1) above).
Ground drop (Artem): «опуски делаем на несколько метров вниз» → exterior perimeter extended 2.0 m below the bottom
(−0.305 → −2.305; reg minimum 1 m). Where a window/door frame bottom is < 10 cm above the bottom of the facade, there is
no thin strip of plinth/concrete under it: the opening is cut down to the drop bottom and the window FRAME polygon is
extended down to −2.305 (frame goes into the ground), no ultra-thin polygons.
Protruding open polygon (Artem): move the polygon itself down / into the neighbour (embed), do not close it with a
flashing or extra cap faces.

## Open

Address, stem `SM_<Address>_NNN`, naming reference, GeoJSON — from Artem later.

### Stylobate B v003 accepted (Artem, 2026-11-14)

Artem accepted the geometry of stylobate B v003 («стилобат принимаю, почти идеальный»).
Review file: `build/gf_parts/_review/STY_review_v003.blend`.
Parts: sty_body_L1, sty_body_L2, sty_windows_B, sty_roof_B, all at v003, xView 0/0.
These questions are still open, and the v003 state stands until Artem answers:
- the SW-corner flashing/soffit "knife";
- frame width next to the lamellae (50 mm);
- colour of the L1 sandwich panels (frame colour);
- railing B post spacing (posts at the Revit positions, axis 8 mm outward).
Next for B: UV and joints, then ID mapping.

### Tower floor 1 (A) geometry accepted (Artem, 2026-11-14)

Artem accepted the geometry of tower floor 1 («принимаю первый этаж, все норм по геометрии»). Review file:
`build/gf_parts/_review/K3_GF_full_review_v004.blend`. Accepted parts:
- `gf_body_A_v004`: colonnade columns rebuilt from plan sections; the east tip modelled by hand; 0 unexplained open edges; xView 0/0.
- `gf_windows_A_v003`: 39/39 openings covered; xView 0/0 against body v004.
- `gf_roof_A_v003`.

The independent technical check of this assembly (`_check/check_v004.md`) is a separate status and was still running at the time of acceptance.

Open window questions; the v003 state stands until Artem answers:
- A_OP24: the frame head is lowered 50 mm to 3.550.
- A_OP19/22/26: a 6 mm ledge at the sill.
- A_OP07: one door leaf, no centre post.
- The look of the 17 extended frames: check after Ground.

Next: UV and joints for A. Floor 1 follows the stylobate joint logic, so A starts once the B UV variant is chosen.

### Check v004 follow-up: open-edge class (coordinator, 2026-11-14)

An open edge inside a part's shell, behind the window plane, is an allowed class when the
checker finds it not visible from outside (0 back-side hits). We do not close such edges: closing
faces would be hidden faces, which breaks the "exterior shell only" rule more than the open
edges do (L2 v004 attempt: +32.8 m² hidden). The dark back panels behind grilles and Stemalit are
visible and are not hidden faces. L2 stays at v003; v004 is archived.

### Stylobate B UV v001 review in 3ds Max (Artem, 2026-11-14)

Accepted: geometry, IDs, UV layout and the vertical brick joints, including their spacing and placement at the corners.
The ground drops, plinth and interiors look right; Artem will check the interiors in detail later.
The metal stays on variant H, the default.

Changes for UV v002:
- One brick texel everywhere. Artem cut the 12.55 m L1 wall in Max himself; we carry his cut over into L1 v004.
- The two roof exit boxes get the roof colour/ID6 instead of brick.
- The glass railing gets a top handrail on A and on B. Revit is closed, so the size is our assumption:
  40×40 mm, role railing_post, glass embedded 10 mm. Check it against Revit later.
- Floor 1 of the tower (A) will most likely get a horizontal joint above the openings. Apply this at the A UV stage.
- Texel target is ≥ 520 px/m, not 512 (Artem, 2026-11-14). 512 is the bare norm threshold and any drift falls below it.
  This applies to B UV v002 and to the A UV.

### Check v005 follow-up (coordinator, 2026-11-14)

- L2 stays at v005: v003 plus the panel cuts for the 520 px/m ID2 texel. v006 is rejected.
- Why v006 is rejected: the checker flagged 4 L2 edges at 9.368, and those flags were false positives. In its visibility test the ray
  skipped the back-face hits on the parapet and reached the railing glass. Closing the edges only added hidden faces.
- Rule for the next check: a visibility ray stops at the first face it hits, front or back. Only glass and grilles are
  transparent.

### Checks v006–v009 (coordinator, 2026-11-15)

Current part versions are those in `_review/K3_GF_full_review_v009.blend`.
- A: body A v008e, windows A v006, roof A v008.
- B: L1 uv_v004, L2 geometry v008 / uv_v006, windows B uv_v004, roof B geometry v009 / uv_v006.

Reports are `_check/check_v006.md` … `check_v009.md`. At v009 these pass:
- xView 0/0 at every level;
- topology;
- levels;
- embeds;
- quads (except 30 triangles in body A).

One real item is open: two roof B edge ends at 25 mm, above the 20 mm limit. The other open items depend on the method.

Rules settled:
- The real tower geometry (K3_TypFloor, K3_Floor2Skirt) is the truth for "inside the tower". The skirt-outline prism
  is 0.26–0.36 m off the pylon at E2. Deleting the E2 post on the prism's evidence was wrong.
- Embeds are measured per edge: at the midpoint and at both ends, along the edge's own face.
- A face is hidden only if no eye sees it. That includes the close eyes 2 m in front of every pane.
- The visibility method differed from run to run, so v006–v009 do not compare one to one. Backlog Q10 asks for one
  shared tool.

Open for Artem:
- the 30 remaining triangles in body A;
- the plinth niche under A_OP19/22/26, closed in v007; it differs from Revit by 0.11 m;
- the roof B SW corner post, now 13 mm off the axis corner;
- the roof A railing visible deviations: E2 end and axis.

### Stylobate B textures v007 (Artem, 2026-11-15)

Review: `build/gf_parts/_review/max/STY_B_tex_review_v007.max` (textures `_uv/textures_v004`, readback pass).
Answers:
- Стемалит (ID12): a 256 px conventional colour for now. Artem replaces it later.
- Burgundy metal and lamellae (ID2, ID5): keep the current conventional colour. Artem chooses later.
- RAL 020 30 20 = 104,64,58, the value close to the real RAL, as in tower roof ID8. This is the source of truth.
  The light typ ID3 value 191,135,137 is to be aligned later.
- Reveals stay RAL 020 30 20.
- Interior capsule (ID10): conventional grey, accepted.

Geometry of A is frozen at v008e/v006/v008 for texturing. After Artem accepted the geometry, open defects go to him as helpers.
- Delivery rule (Artem, 2026-11-15): the main window glass is always its own object, detached from the frames, in the final model.
  Stylobate B v007 stays as it is: the glass is still inside the STY_WinB_* objects.
  In tower A the glass is detached at the end, into K3GF_WinA_Glass.

### Known window defects, fix later as a separate card (Artem, 2026-11-15)

These are window-agent defects on stylobate B (sty_windows_B), and they likely affect windows A as well. Do NOT fix them in the current delivery. A separate task will come from the kanban board.
1. The glass has no outline: it is not seated or embedded into the frame, and no frame lip overlaps the glass edge.
2. The ventilation grilles have the same problem: no border, and they are not embedded into the frame or reveal.
3. The interiors were built as a continuation of the frame. As a result, many frame-ID faces are very thin and the visible frame width is too small.

Fix idea for the card:
- Rebuild each opening from a library template (`library/windows`, frame topology rule in `docs/domain/geometry.md`):
  - outer rectangle minus panels, with 4 quads around each panel;
  - frame face width taken from the Revit type, or about 50–70 mm when no type is given.
- Glass and grille panels are 10–20 mm larger than the frame light and are embedded into the frame profile [D199-style embed]. They are seated mid-depth.
- The interior capsule is a separate box set back behind the glass. It is not extruded from the frame edge.
- The glass is its own object (delivery rule above).
- Then xView 0/0 and a close-eye visibility check.

### UCX plan accepted (Artem, 2026-11-15, «Да, принимаю рекомендации»)

Method: band envelopes as on K5 (`docs/agr/case_studies/SKUG26_K5_UCX_VPM.md`). Within each band the plan is split into convex pieces at the re-entrant corners. A single hull for all of A is not allowed.

Two agents, one per package:
- A (tower package): bands up to 4.47, then 4.47–5.08. Leave a gap to the future tower UCX above 4.47.
- B (stylobate package): L1 up to 3.00, L2 3.00–9.45, roof, exit boxes.

Decisions:
- UCX bottom = model bottom −2.305.
- Exploitable roofs A and B: the roof slab and the parapet ring are separate pieces. Do not fill the well behind the parapet.
- NW arcade and colonnade of A: the passage stays free; each column gets its own prism.
- Each exit box of B gets one box. Grilles get no UCX of their own.
- Railing glass, handrails and posts under 5 cm get no UCX (R04).

Gates:
- each piece is convex and closed, with no material slots;
- 0 intersections and 0 nested pieces;
- gaps 2 mm–1 cm, target 4 mm [D098];
- model → UCX at most 30 cm everywhere, measured one-sided (pedestrian zone) [D134];
- full coverage of the visible facade and roof;
- at most 15 000 triangles per package [D012].

Names: `UCX_SM_{Address}_Main_NNN` with a temporary Address, renamed at packaging. Build in Blender headless, review in 3ds Max.

### A geometry for UV and textures = accepted v004 set (Artem, 2026-11-15)

Artem rejected the geometry in `K3_A_tex_review_v001` (body v008e). UV, textures and UCX of A use the set he accepted on 2026-11-14:
- body A v004
- windows A v003
- roof A v003

That is the content of `_review/K3_GF_full_review_v004.blend`. The QA-round versions v005–v008e are not used.
Open: roof A v003 has no top handrail, which Artem asked for later.

### Stylobate B geometry, UV and textures finished by Artem (2026-11-15)

Artem finished the stylobate by hand in his Max scene `STY_B_tex_review_v007` and attached it into one object. He fixed these himself:
- the Стемалит;
- the grilles;
- glass and grille embeds and their outlines;
- the vertical lamellae, re-modelled so their loops and rings meet the frame vertices;
- the materials and ID split.

He considers stylobate geometry, UV and textures done. What is left for B: UCX, then the canopies.
The analysis of his edits, written as rules for agents, goes to `_review/max/artem_v007_analysis/ANALYSIS.md`.

### Long walls past the UDIM tile: cut by vertical loops (Artem, 2026-11-15)

When a wall does not fit one tile (e.g. 32 m), it is cut with vertical loops: select its horizontal edges, then Connect.
- The loop runs the full height of the strip; there are no partial cuts.
- With joints, the cuts sit on the joints.
- Without joints, the cuts make segments of about 4 m, each no wider than one tile.
- The segments are then laid into the tiles.

Applied to A as UV v003, on top of geometry v004. The only geometry change is the new loops. Run xView once afterwards.

### UCX B v001 accepted as is (Artem, 2026-11-15)

Artem accepted `ucx_B/sty_ucx_B_v001.blend` and `_review/max/STY_B_ucx_review_v001.max` as built («Да, как есть»).
- 10 pieces, 148 triangles.
- L1 is one piece, and L2 is one piece including the overhang and the fins.
- Roof slab 8.75–9.05.
- Parapet ring of 5 wedges.
- 2 exit boxes.

Open: re-run the deviation and coverage check against Artem's hand-finished stylobate once he saves it.

### Stylobate B status about 80 % (Artem, 2026-11-15)

Artem checked the UCX on his finished stylobate and is satisfied, so the planned re-check is not needed. Geometry, UV and UCX of B are closed.
Waiting for the naming (address) and the model's rotation angle:
- names (`SM_<Address>_Main`, UCX, materials, textures);
- the full texture set (ERM and normal maps);
- GeoJSON;
- the pivot at the geometric centre / origin.
Canopies (10 «ОбщМд_Козырек_Стеклянный») are not modelled yet. They were named earlier as part of B and are not in this list.
- Canopies for B (Artem, 2026-11-15): Artem will provide a typical canopy model. We then place it at the 10 Revit positions («ОбщМд_Козырек_Стеклянный»). Wait for his model; do not model canopies ourselves.

### A and B at about 80 %, Artem's hand-finished etalons (Artem, 2026-11-15)

UCX A v001 accepted. Artem finished both buildings by hand in Max: attached, split by ID, no open polygons, UV, geometry and UCX. He re-modelled part of the geometry himself. On A he also re-unwrapped the brick and the АКП panels with joints and edited the maps.
Artem does the rest himself: canopies on A and B, RALs, the final UDIM distribution.
A combined scene `63_4BK_vlad/scene_build_A_build_B.max` has layers Build_A, Build_B, UCX_A and UCX_B.
The analysis of his finals against our deliveries goes to `_review/max/artem_final_analysis/`.
Artem now works on the big tower by hand.
- Artem confirmed the final analysis (`_review/max/artem_final_analysis/ANALYSIS.md`) as correct (2026-11-15). He finishes the rest of A and B himself: n-gons go away at triangulation; he unwraps the faces that are still unwrapped and checks zero-area faces and zero-area UV islands.
