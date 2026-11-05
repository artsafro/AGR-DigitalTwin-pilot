# Лаборатория 0.9, лот L07: `qa.procedural_objects` (процедурные объекты)

05.11.2026, 3ds Max 2024.2.1 (ноутбук, AGR Lab runner). Код плагинов не читался и не исполнялся. Плагины не устанавливались.
Доказательства: GeoAGR-private `lab-exp/09-L07`, `work/lab-experiments/qa.procedural_objects/`.

- **Строка плана:** блок `qa`, версия 0.9, вердикт `new`.
- **Источник:** T07 — только имена классов. Продукты:
  - Forest Pack Pro 9.2.4;
  - RailClone Pro;
  - MultiScatter 1.630;
  - Chaos Scatter;
  - RayFire 2024;
  - tyFlow;
  - Populate.
- **Джобы:**

| Job id | Что |
|---|---|
| `20261105-123418-96cf611e` | проба классов и DLL |
| `20261105-123509-1f1fe827` | параметры классов |
| `20261105-123702-11647754` | FBX: контроль, Chaos Scatter, Populate, ScatterGeometry |
| `20261105-123946-ec4c68ca` | Chaos Scatter, 3 варианта + bake |

- **FBX:** параметры как у `export.checked` (`adapters/max/agr_tools/runtime.py` `_write_max_fbx`), readback —
  `export_core.readback`.

## Что есть на ноутбуке (изм., job `…123418-96cf611e`)
| Продукт | Классы | Есть в Max 2024 на ноутбуке |
|---|---|---|
| Forest Pack Pro | `Forest_Pro`, `Forest_Lite` | нет |
| RailClone Pro | `RailClone_Pro`, `RailClone_Lite` | нет |
| MultiScatter | `MultiScatter`, `MultiPainter` | нет |
| RayFire | `RayFireBomb`, `RFCloth` | нет |
| tyFlow | `tyFlow`, `tyCache`, `tyMesher` | нет |
| Chaos Scatter | `ChaosScatter` (classOf `ChaosScatter`, superClassOf `GeometryClass`, creatable) | да |
| Corona Scatter | `CScatter` (`GeometryClass`, из скрипта не создаётся) | да |
| Populate (встроен) | `Flow`, `IdleAreaObj` (`GeometryClass`), `Crowd` (`helper`) | да |
| не из списка T07 | `ScatterGeometry` (`GeometryClass`; `scatter.dlo`, ApplicationPlugins `sinisoftware2024`) | да |

**Лот частичный:** Forest Pack, RailClone, MultiScatter, RayFire и tyFlow — `blocked: plugins only on PC`. Пробу на ПК
(Max 2024, слот No_Defender) нужно поставить отдельным поручением.

## FBX-гипотеза T07 (изм.)
| Объект | Max: треугольники | FBX readback: объектов / треугольников |
|---|---|---|
| контроль Box | 12 | 1 / 12 |
| Chaos Scatter: 50 боксов по 12 треугольников на плоскости | сетки нет; инстансов 0 до и после `update` | **0 / 0**, экспорт при этом `ok` |
| Chaos Scatter, `convertInstancesToGeometry` | вернул 0, новых нод нет | — |
| Populate Flow без симуляции | 2 | 1 / 2 (только поверхность пути) |
| Populate Idle Area | 0 | 0 / 0 |
| ScatterGeometry | 0 | 1 / **824** |

- В batch-Max Chaos Scatter не создаёт инстансы ни в одном из трёх вариантов настройки. FBX получается без объектов, а
  экспорт сообщает успех: это **молчаливая потеря** рассаженной геометрии.
- У ScatterGeometry Max-снимок даёт 0 треугольников, а FBX — 824. То, что видит скрипт, и то, что попадает в файл, не
  совпадает.
- **Отсутствующий плагин (`Missing_*`): не измерено.** На ноутбуке нет сцены с объектом отсутствующего плагина, а создать
  её без удаления плагина нельзя.

## Гипотезы (гип.)
- Ноль инстансов Chaos Scatter в batch может быть из-за лицензии Chaos или из-за отсутствия вьюпорта. В GUI Max это не
  проверялось.

## Вердикт лаборатории: `new` (без изменений)
- Ловить объекты по списку классов **до** экспорта.
- Не полагаться на треугольники: снимок Max и FBX расходятся, а scatter может выгрузиться пустым без ошибки.
- `export.checked` должен останавливаться на этих классах.

## Список для `procedural_classes.json`
- **Изм. на ноутбуке:** `ChaosScatter`, `CScatter`, `Flow`, `IdleAreaObj`, `Crowd` (helper), `ScatterGeometry`.
- **Только имена T07, без измерения:** `Forest_Pro`, `Forest_Lite`, `RailClone_Pro`, `RailClone_Lite`, `MultiScatter`,
  `RayFire*`, `tyFlow`, `tyCache`.

## Что меняется в требованиях issue
- Добавить `CScatter`, `IdleAreaObj`, `Crowd` и `ScatterGeometry`.
- Гипотезу «неполный экспорт» для Chaos Scatter считать подтверждённой в batch: 0 объектов при успешном экспорте.

## Требования
`-` (строка плана без NPM/VPM-требований). Связь: `qa.tris`, `export.checked`.

## Минимальная приёмка
1. Сцена с объектами всех измеренных классов (`ChaosScatter`, `Flow`, `IdleAreaObj`, `Crowd`) и одним обычным Box.
   Кнопка выделяет и перечисляет ровно процедурные объекты и ничего не сворачивает: хэш сцены до и после равен.
2. `export.checked` на этой сцене останавливается с кодом про процедурные объекты, FBX не пишется.
3. Классы из списка T07, которых нет в Max, не ломают проверку (проверка по имени класса, без `execute`).
4. После пробы на ПК: Forest/RailClone/MultiScatter/RayFire/tyFlow добавлены по `classOf`/`superClassOf` из джоба ПК.
