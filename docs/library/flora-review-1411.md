# Flora catalogue review for Artem — #1411

## Резюме для Артёма

Подготовлены **8 PNG, 61/61 вид** замороженного каталога v003: ID материала,
латинское и русское название, тип, NPM/VPM рядом, реальные числа треугольников,
наличие карт и двустороннее совпадение поверхностей из #305.
В каждой существующей паре — одна ортокамера и одинаковый масштаб, без выравнивания размеров растений.

**Это обзор геометрии без текстур, НЕ приёмка внешнего вида.** Все 99 объектов
найдены, но все **198 исходных bitmap bindings отсутствуют**; старые одобренные
карты по путям каталога тоже отсутствуют. Историческое одобрение карт не отменено,
однако наличие файлов из него не следует. Чужие A101-атласы и stand-in не подставлялись:
их совместимость с геометрией v003 не установлена (`library/flora/README.md`).
Карты действительно использованные на листах: **нет**; зелёно-серый цвет —
диагностическая заливка, а не цвет растения. Opacity также отсутствует: видны
геометрические прямоугольники листовых карточек, не вырезанный силуэт листвы.

В #305: **38 разных поверхностей, 23 вида без VPM**. Разная поверхность не означает
разный ботанический вид и не подтверждает правильность назначения NPM/VPM.
`catalogue.json`, `vpm_identity: unverified`, геометрия, UV и карты **не изменены**.
Подтверждения Артёма в этой работе не было; изменение статусов — только отдельным follow-up после ответа.

По завершении открывать библиотеку в **3ds Max 2026** для приёмки?
Можно открыть отдельную копию `G:/Мой диск/AGR-assets/flora/v003/flora-library-v003.max`;
автоматического открытия вместо текущей пользовательской сцены не выполнялось.
Для цветовой/ботанической приёмки сначала нужны именно исходные совместимые карты,
а не внешне похожая замена.

## PNG sheets and checksums

Evidence directory: `G:/Мой диск/AGR-evidence/1411-flora-catalogue/v001/`.
[Drive folder](https://drive.google.com/drive/folders/1aabcuAn8fgtxeaMFLu9W18QYhFU4Ernw).
[SHA256SUMS.txt](https://drive.google.com/file/d/10EscLG6BKGQH4_OAiyCNBCvnZKLXYEiM/view).
Existing Drive permissions are preserved; these are owner-access links, not a claim of anonymous access.
No PNG/MAX/FBX is committed to Git.

| Sheet | Catalogue rows | PNG attachment |
|---|---|---|
| 1 | 1–8 | [flora-review-01.png](https://drive.google.com/file/d/1nUnh4BjL9KNgRWw-mhBP7aR6YCe344Ei/view) |
| 2 | 9–16 | [flora-review-02.png](https://drive.google.com/file/d/1FRyALiqjurtJv2b2IhFTtmFYPmAUFt6q/view) |
| 3 | 17–24 | [flora-review-03.png](https://drive.google.com/file/d/1wFit4MH8uDeZjmobtB9RS4f84a022Q2H/view) |
| 4 | 25–32 | [flora-review-04.png](https://drive.google.com/file/d/1Ab4gM8TZBJ3Mo6QNOk7fhxLyrI_D-wWB/view) |
| 5 | 33–40 | [flora-review-05.png](https://drive.google.com/file/d/17Ai9KOa8uMR69yYzEqZIrSSJEtGX9oqu/view) |
| 6 | 41–48 | [flora-review-06.png](https://drive.google.com/file/d/1WbfqCbhiiWyOXcqh1oofjPHTk8JmVM8Q/view) |
| 7 | 49–56 | [flora-review-07.png](https://drive.google.com/file/d/1zfyDBN5gG1Jbo7Jcx7sjg4navQ4tJTuH/view) |
| 8 | 57–61 | [flora-review-08.png](https://drive.google.com/file/d/1DW07Pn2qDkkVk1ZeAQj8_3yONrrTwBhp/view) |

The small [machine receipt](flora-review-1411.json) binds every species to its sheet,
PNG SHA-256/size, actual native triangle counts, missing bitmap paths, historical
map approvals, exact #305 measurements and unchanged catalogue SHA-256.
The full evidence folder also contains the raw census (positions/faces/native bounds),
renderer camera receipts, execution log and fixed job drivers.

## Missing objects and maps

- No missing/duplicate **named** objects among the 99 expected objects: 61 NPM + 38 VPM.
- VPM is absent in the catalogue for IDs **102, 110, 111, 112, 118, 119, 201, 202,
  204, 206, 208, 210, 213, 214, 215, 216, 217, 219, 403, 404, 405, 406, 409**.
  Their cells say «объекта VPM нет», not zero triangles or a fabricated match.
- All 61 historical diffuse/opacity pairs are missing at their exact catalogue paths.
  All 198 material bitmap references in the saved library are missing too.
  Full paths, including repeated per-object bindings, are in the machine receipt.
- Catalogue `species_without_approved_maps: []` describes historical approval,
  **not current filesystem availability**; it is not rewritten here.
- The following 15 reserved gap IDs have no own library mesh and therefore are
  not disguised as extra reviewed species or rendered from their shared stand-in:

| ID | Latin | Russian |
|---|---|---|
| 121 | Quercus robur | Дуб черешчатый |
| 122 | Tilia cordata 'Greenspire' | Липа мелколистная Гринспайр |
| 123 | Alnus incana | Ольха серая |
| 124 | Picea abies | Ель обыкновенная |
| 125 | Abies koreana | Пихта корейская |
| 126 | Pinus sylvestris | Сосна обыкновенная |
| 127 | Acer platanoides 'Royal Red' | Клён остролистный Роял Ред |
| 228 | Cornus sanguinea 'Anny's Winter Orange' | Дёрен кроваво-красный Эннис Винтер Оранж |
| 229 | Cornus alba 'Red Gnome' | Дёрен белый Ред Гном |
| 231 | Salix repens 'Green Carpet' | Ива ползучая Грин Карпет |
| 232 | Juniperus sabina 'Tamariscifolia' | Можжевельник казацкий Тамарисцифолия |
| 233 | Juniperus sabina 'Mas' | Можжевельник казацкий Мас |
| 235 | Pinus mugo 'Mops' | Сосна горная Мопс |
| 236 | Picea abies 'Nidiformis' | Ель обыкновенная Нидиформис |
| 237 | Pinus mugo var. mughus | Сосна горная Мугус |

One unresolved inventory group remains: `library-080..083`, source names
`Многоцветник_v1`, `Многоцветник_v2`, `Многоцветник_v3`, `Многоцветники_v4`.
No Latin species identity is invented for it.

## Measurement and program choices

- **3ds Max 2026.3 live, pinned PID 832856**: native read-only mesh/material census
  from a byte-identical private copy; Max reads MAX directly without conversion assumptions.
  System units: metres, scale 1.0. All 99 vertex bounds agreed with native world bounds
  within 0.1 mm; all triangle counts agreed with the frozen catalogue.
- **Blender 5.1.2 background Workbench**: Max had a live user review scene; after the
  short native census, render isolated copies with a native depth buffer, not painter sorting.
  Vertices/faces come from the Max snapshot; no mesh simplification or botanical reconstruction.
  Pairs share a camera, angle, base-Z seating and scale. Single NPM-only images are fitted
  into the left cell with an explicit missing-VPM cell. No current Blender scene is touched.
- **Python/Pillow**: Cyrillic labels, sheet composition and SHA-256; no DCC needed for layout.

### #305 number definition

This is **historical report readback**, not a fresh surface-check run. The library SHA-256
`9942ae2be37c900c3066d791193eb0470cc08933881d9f72db833d42578dfa74`
is identical to #305's source. The historical report's catalogue hash is older than
this catalogue (later light metadata exists); each current object name/face count and
report direction is independently reconciled, and the current catalogue hash is recorded separately.

For each direction, the sheet shows conservative coverage bounds in percent:
`100 * (1 - uncovered_upper_m2 / area_m2)` through
`100 * (1 - uncovered_lower_m2 / area_m2)`.
The tolerance is 0.0001 m; percentages are display-rounded only. This compares the
unscaled geometric surfaces in the historical D100 pivot frame, not the posed
side-by-side render, opacity silhouette, species correctness or visual similarity.
23 absent VPM objects have no score, explicitly stated as not measured.

### Live restoration incident (not hidden as a clean run)

The first extraction raised `Scene restore mismatch` after `fetchMaxFile`: the 38-object
user scene was restored (`STY_BodyL1_Shell` first object), but Max retained the temporary
library filename in its document metadata. The complete 99-object census remained in
memory and was written out by a separate readback, not by rerunning the extraction.
The source MAX and catalogue hashes are unchanged. Assigning pymxs filename globals
also did not change the core document label; no source or user file was saved to repair it.
**The user scene content was restored, but its displayed/current save path is the private
`tmp/1411/flora-library-copy.max`, not its original STY_B path.** Before saving that scene,
use Save As to the intended review path. This limitation is separate from Flora acceptance;
the library was not left open and no original was overwritten.

## Verification boundary

The tests bind a static evidence packet, not a new production pipeline. RED at
`16018f7f`: 1 assertion failure for the missing packet before publication. Affected
commands/counts and mutation probes are recorded on the PR head. Every PNG was reopened
and its checksum checked; native bounds/counts and all sheet memberships are reconciled.
No topology/UV/material correctness, realistic appearance, regulatory delivery pass,
or Artem approval is inferred from the neutral geometry renders.

Full suite: deferred to merge batch (rule 68).
