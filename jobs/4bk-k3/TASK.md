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

## Open

Address, stem `SM_<Address>_NNN`, naming reference, GeoJSON — from Artem later.
