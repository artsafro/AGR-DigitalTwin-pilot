# Lab experiment L02: `export.pivot_place` (pivot and position)

This page records how GeoAGR 13.64 behaved when its pivot tools ran in 3ds Max 2024.2.1, on synthetic scenes in the AGR
Lab runner (04.11.2026). It contains no GeoAGR code, only references to `GeoAGR.ms:<line>` (rule #853). The evidence is
in GeoAGR-private, branch `lab-exp/L02`, under `work/lab-experiments/export.pivot_place/`.

- **Plan row:** `docs/plans/agr-tools-suite.json`, block `export`, version 0.8, verdict `take_fix`.
- **Sources:** the GeoAGR "Geojson operations → Pivot operations" group:

| Button | Lines |
|---|---|
| Get Pivot | `GeoAGR.ms:64763` |
| Set Pivot to Down Center | `GeoAGR.ms:64778` |
| Set Position To | `GeoAGR.ms:64832` |
| Reset Transforms | `GeoAGR.ms:64709` |
| Combine two models near zero | `GeoAGR.ms:64730` |

## Synthetic scene
- A 20×10×9 m block stands on a 22×12×0.6 m slab.
- The clean floor (±0.000) is the slab top, at absolute 150.0.
- The model is rotated 30° about Z.
- X/Y are MSK-like: 12345.678 / -6789.012. A second position uses 1e6-scale values.

## Measured
Runner jobs: `20261104-230539-94c82812` and `20261104-231025-09c6127c`.

What works:
- Set Pivot with the floor faces selected puts the pivot at z 150.00006. The vertices do not move and no extra nodes are
  left in the scene.
- Set Position To 0,0,0 then puts the floor at z 0. This matches the VPM "clean floor at zero" requirement.
- Reset Transforms keeps the world geometry exactly and sets rotation to 0 and scale to 1. It also collapses the modifier
  stack.

Defects:
- **Precision.** Get Pivot writes the coordinates as text with about 6 significant digits. A Get → Set round trip loses
  2.3 cm at 1e4 m. At 1e6 it loses 2.35 m, and the fields switch to exponent notation such as `2.34568e+06`. That is not
  acceptable for MSK coordinates in the NPM.
- **Rotation sign.** The Z rotation field shows -30 for a model rotated +30° in the UI.
- **Pivot from selected vertices.** It uses the bbox centre of the faces around those vertices: 149.7 or 154.2 instead
  of 150.0.
- **Pivot with no selection.** It goes to the bbox bottom, 149.4, which is 0.6 m below the clean floor when there is a
  slab or a foundation.
- **Sloped face.** It uses the face centre, not the lowest point.
- **Empty field.** Set Position To reads an empty field as 0 and moves the object without a warning.
- **Combine near zero.** It moves both working objects and aligns their bbox centres, so the offset between the models
  is lost.
- **No copy mode.** None of the buttons works on a copy; each one changes the working objects.

## Recommendation: `take_fix`
- Take the idea "pivot z from the selected floor faces, then position 0,0,0 for the VPM" (B3/B5 are correct).
- Re-implement the rest:
  - work on export copies;
  - take the floor height as the min z of the selected faces or vertices, or as an explicit ±0.000 value;
  - keep coordinates in double precision, with fixed decimals in any text;
  - for the NPM, keep MSK X/Y/Z exactly and move only the pivot;
  - for the VPM, move the floor pivot to [0,0,0];
  - validate all inputs;
  - report the rotation as the UI shows it.

## Requirements the tool must meet
These are the plan row's `reqs`: NPM-2.8-1, NPM-2.8-2, VPM-2.9-4.b, VPM-2.9-5.
- The NPM keeps its position in MSK with absolute heights.
- The VPM is placed at zero, with the pivot on the clean floor (±0.000).
- The pivot is set on copies only.
- The ±0.000 reference of TEC26 is still open (`jobs/TEC26-OKS/STATE.md`). The tool must take ±0.000 as an input or from
  a selection, and must never guess it from the bbox.

## Minimal acceptance test (proposal)
Use the slab and block above at X/Y 12345.678 / -6789.012 (and 2345678.912 / 1234567.891), floor 150.0, rotated 30°.
1. **Working model.** Its position, pivot and vertices do not change. The test compares them before and after with a
   0 tolerance.
2. **NPM copy.** The vertex world positions equal the source within 1e-4 of the float spacing. The pivot is at
   [centre X, centre Y, 150.0] within 1 mm.
3. **VPM copy.** The pivot is at [0,0,0], the floor face is at z 0 within 1 mm, and the rotation is as configured.
4. **Floor from vertices** (4 slab-top vertices only) gives 150.0. **No selection and no explicit ±0.000** gives a
   refusal, not the bbox bottom.
5. **Read-back.** After FBX export of both copies, read the files back and repeat checks 2–3 in metres.

---

# Лаборатория 0.9, лот L07: AC Pivot Align для `export.pivot_place` (доработка 0.8)

05.11.2026, 3ds Max 2024.2.1 (ноутбук, AGR Lab runner). Кода командного скрипта здесь нет (#853).
Доказательства: GeoAGR-private `lab-exp/09-L07`, `work/lab-experiments/export.pivot_place/v09-L07/`.

- **Источник:** `codex-3ds-max/projects/ac-pivot-align/src/rotate_pivot_tool.ms`, SHA256
  `6344571ffbe927de8a481462136d6dd84f9e0ff7d28d167198891b8fc5f41e20` (сверен в джобе). T06 мерил его только в Max 2026, в метрах,
  у нуля (SYNTHESIS §1: «на сценах в см не запускался»).
- **Джоб:** `20261105-124137-6d11eec8`. `20261105-124047-8b319ea3` — сбой харнесса, не считается.
- **Сцены:** клетки 4×1×0,5 м под 17 / 45 / 89 / 135°; поворот запечён в сетку, у ноды поворота нет (как в T06).
  Порядок вызова как в README инструмента: dry-run → apply → `max undo`.

## Измерено (изм.)
| Сцена | Ошибка оси X после apply | Дрейф вершин / пивот | Отказы | Откат |
|---|---|---|---|---|
| метры у нуля | ≤ 1,5e-5° | ≤ 3,8e-6 м / 0 | 0 из 4 | 1 undo вернул всё |
| сантиметры у нуля (400×100×50 см) | ≤ 7,6e-6° | ≤ 7,6e-6 см / 0 | 0 из 4 | да |
| метры, X/Y 2 345 678 / 1 234 567 | **1,43° (17°), 1,0° (89° → 90°)**; 45° и 135° точно | 0 / 0 | 0 из 4 | да |
| сантиметры, X/Y 234 567 800 / 123 456 700 | **0,74–1,0°** | 0 / 0 | 0 из 4 | да |

- **Скан расстояния** (45°, метры): ошибка ≤ 4e-6° до 3e4 м, 0,04° при 1e5 м, 0,16° при 3e5 м, 0,32° при 1e6 м.
- **dry-run** не меняет сцену: трансформы до и после равны.
- **Editable_Mesh:** принят, повёрнут точно.
- **Отказы:**
  - ребёнок: «Linked nodes not supported»;
  - объект с модификатором: «Requires Editable Poly/Mesh» — сообщение неточное, это не ошибка класса;
  - квадратная клетка: «Square or degenerate footprint».
- **Время подбора:** 64 / 128 / 256 / 512 вершин — 0,1 / 0,83 / 6,7 / **56,8 с** (×8 на удвоение, O(n³)). Больше 512 — сразу
  отказ «Requires 3..512 vertices»; 5000 вершин инструментом не обрабатываются.

## Вывод по гипотезе
- **Гипотеза «допуск 0,002 ед. даёт отказ на валидных нодах» опровергнута:** отказов нет ни в см, ни далеко от нуля.
  Проверка дрейфа сравнивает точки, посчитанные одинаково через float32, поэтому проходит.
- **Новый дефект:** ось подбирается по мировым float32-координатам вершин. Далеко от нуля шаг float32 (0,25 м при 2,3e6)
  искажает направления рёбер, ошибка оси доходит до 1,4° без предупреждения.
- В сантиметрах у нуля инструмент работает так же точно, как в метрах.

## Что меняется в доработке `export.pivot_place`
- Подбирать ось в координатах относительно пивота (без переноса) или в double.
- Порог отказа — по неопределённости угла, а не по дрейфу вершин.
- Выпуклый контур + rotating calipers вместо перебора пар: O(n log n), без лимита 512.
- Оставить: dry-run, одну запись undo, проверки единичного масштаба и связей.

## Минимальная приёмка (доработка)
1. Клетки 17 / 45 / 89 / 135° в трёх сценах (метры у нуля, сантиметры, метры на 2 345 678 / 1 234 567):
   - ошибка оси ≤ 0,01° во всех 12 случаях;
   - мировые вершины не сдвигаются (≤ 1e-4 ед.);
   - пивот на месте.
2. dry-run не меняет сцену; одна запись undo возвращает все трансформы.
3. Клетка из 5000 вершин обрабатывается быстрее 2 с.
4. Квадратная клетка, ребёнок, объект с модификатором — отказ с точной причиной; трансформ не тронут.
