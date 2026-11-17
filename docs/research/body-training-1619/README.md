# Учебный полигон чистого бадика (#1619): журнал

Входы — копии в `C:/x/body-training/` (sha256 в `SHA256SUMS.txt`). Evidence:
`G:/Мой диск/AGR-evidence/1619-body-training/`. Данные заказчика в git не попадают.

## Gate 1 (2026-11-17): выбор этажей — ждёт «ок» Артёма

Участок 63 (`STLB-04_RR_AR.fbx`, Blender 4.4 headless, только чтение):
`site_census.py` выписывает bbox 27 629 меш-объектов. `split_buildings.py --gap 2 --zmin 12` берёт
фасадные стены выше стилобата и даёт 4 башни (на z ≥ 8 они те же):

| Башня | XY bbox, м | Верх, м | Уровней стен | Шаг этажа | Доля фасада вне главных азимутов |
|---|---|---|---|---|---|
| A | 81–120 × 64–96 | 78,2 | 22 | 3,15 | 0,092 |
| B | 55–96 × 1–34 | 61,4 | 18 | 3,15 (пояса через ~5 эт.) | 0,139 |
| C | 6–45 × 79–111 | 53,5 | 14 | 3,15 | 0,141 |
| D | −1–30 × −1–37 | 44,8 | 10 | 3,15 | 0,118 |

Предложение: G22 корпуса 1–3 (эталон) + башни 63 A, B, C; D — резерв. Лист: `gate1/gate1_sheet.png`.
Решение Артёма: _ожидается_.

## Журнал изменений правил по кругам

| Круг | Этаж | Замечания Артёма | Что изменено (doc / skill) |
|---|---|---|---|
| — | — | — | — |

## Воспроизведение

```
blender44 -b --factory-startup --python site_census.py -- STLB-04_RR_AR.fbx census.json
python split_buildings.py census.json buildings.json --gap 2 --zmin 12
blender44 -b --factory-startup --python render_candidates.py -- STLB-04_RR_AR.fbx boxes.json OUTDIR
python gate1_sheet.py tiles.json gate1_sheet.png
```
