# Фрагменты станций баз 0.8 и 0.9 (#979)

Базы 0.8 (станции `0.8.1`–`0.8.13`) и 0.9 (`0.9.1`–`0.9.19`) стоят в `polygon_core.py` с ветки 0; номер станции —
порядок строки в `versions[].rows` плана. Объекты и ожидания станций пишут ветки #979, каждая в **свой** файл:

| Файл | Ветка | Кнопки (`polygon_core.OWNER`) |
|---|---|---|
| `A.json` | `improve/issue-979-place` | `place.*` |
| `B.json` | `improve/issue-979-tex-udim-atlas` | `tex.erm_normal_check`, `tex.finish_map`, `udim.matid_unwrap`, `udim.slots`, `atlas.flora`, `atlas.groundel` |
| `C.json` | `improve/issue-979-qa` | `qa.address`, `qa.normals`, `qa.sintez`, `qa.facade_compare`, `qa.procedural_objects` |
| `D.json` | `improve/issue-979-export-scene-light` | `export.batch`, `scene.maps_usage`, `light.check` |
| `E1.json` | `improve/issue-979-rework-tex-names` | `tex.format_fix`, `tex.placeholders`, `scene.missing_maps`, `qa.names_fix`, `ucx.rename` |
| `E2.json` | `improve/issue-979-rework-geom-udim` | `ucx.triangulate`, `export.pivot_place`, `udim.ids_to_udims`, `model.triangulate` |
| `E3.json` | `improve/issue-979-rework-package-suite` | `export.zip`, `qa.package`, `export.geojson_write`, `export.ground_fbx` |

## Формат

```json
{"schema": 1, "branch": "A", "issue": "#979", "stations": [
  {"button": "place.replace",
   "objects": [{"name": "SM_Replace_Ok_Main", "role": "Main", "size": [2, 2, 2], "mat_name": "M_Polygon_001_Main_1"},
               {"name": "SM_Replace_Bad_Main", "role": "Main", "extra": {"reference": "нет"}}],
   "expected": [{"name": "SM_Replace_Ok_Main", "scene": "polygon_all", "expect": "pass", "codes": []},
                {"name": "SM_Replace_Bad_Main", "scene": "polygon_all", "expect": "fail", "codes": ["no_reference"]}],
   "reason": "", "options": {"mask": "SM_*"}}
]}
```

- `objects`: поля `_obj` (`polygon_core.OBJECT_KEYS`); `name` и `role` обязательны, имя не начинается с `_`.
  `scene`: `polygon_all` (по умолчанию), `vpm` или своя сцена `frag_<ветка>_*` (метры).
  XY объектов `polygon_all` ставит раскладка: они стоят на своей станции базы 0.8/0.9.
  Своё поле ветки — в `extra` (уходит в каталог и билдер как есть).
  Новый вид узла (свет, scatter…) — `"builder": "<ветка>_build"` и файл `stations/<ветка>_build.py` с
  `make(obj, rt) -> node` (вызывает `build/build_scene.py`).
- `homes` (необязательно) — все объекты `polygon_all` станции; `cluster` — плотная раскладка.
- `expected`: строки `{name, scene, expect pass|fail|error, codes}`, хотя бы один PASS и один FAIL, иначе
  непустой `reason`. Без `expected` станция остаётся «станция в работе, #979, ветка X».
- `tool` (по умолчанию id строки) нажимается в живом прогоне через `runtime.edits_090` / `edits_080` в режиме
  preview с `options`.

Объекты фрагментов не видят предсказания кнопок 0.1–0.7: их `expected/` не меняются.

## Что коммитит ветка

1. Свой `stations/<ветка>.json` (и `stations/<ветка>_build.py`, если нужен).
2. Свои `expected/<id>.json`: `python test-polygon/polygon_core.py --branch <ветка>` (пишет только их).
3. `catalog.json` и `bases.json` не трогает — их перегенерирует R. Билдер и тесты читают
   `polygon_core.load_catalog()` (полигон + фрагменты).
4. Живой прогон своих станций в Max 2024: `run_polygon.py` пишет `<out>/catalog.json` из `load_catalog()` и передаёт
   его билдеру (`AGR_POLYGON_CATALOG`).

## База 1.0 (#1024)

База 1.0 (станции `1.0.1`–`1.0.33`) стоит в `polygon_core.py` с ветки 0 в порядке этапов
(`roadmap.stage_buttons`), камера `_cam_База 1.0`, `TOUR_LAST = '1.0'`. Фрагменты веток F…U — тот же формат,
но `"issue": "#1024"`; владелец кнопки — `polygon_core.OWNER_100`:

| Файл | Кнопки |
|---|---|
| `F.json` | `project.passport`, `source.intake`, `scene.source_class`, `scene.small_parts` |
| `G.json` | `body.prepare`, `model.attach_by_material`, `model.move_apart` |
| `H.json` | `model.grid_cleanup`, `model.glass_planes` |
| `J.json` | `win.generate`, `win.place` |
| `K.json` | `body.capsules`, `body.roof` |
| `L.json` | `mat.table`, `mat.tiles`, `tex.plug_colour` |
| `M.json` | `vpm.build`, `udim.rescale`, `udim.distortion` |
| `N.json` | `tex.dilate`, `udim.plugs` |
| `P.json` | `npm.build`, `atlas.facade_strip` |
| `Q.json` | `npm.to_vpm`, `udim.udims_to_ids` |
| `S.json` | `pack.deliver`, `ucx.gap`, `light.export` |
| `T.json` | `ucx.stairs`, `qa.omk_te`, `export.place_by_passport` |
| `U.json` | `agent.request`, `agent.accept` |

Новый вид узла: `"builder": "<буква>_build"` и `stations/<буква>_build.py` (`make(obj, rt) -> node`).
Без `expected` станция остаётся «станция в работе, #1024, ветка X». Свои `expected/<id>.json` пишет
`python test-polygon/polygon_core.py --branch <буква>`. Строки хвоста (`fate: tail/obsolete`, версия 1.x) стоят
без станций, с прежним `reason`; три `step`-строки 1.0 (`model.window_placer`, `tex.vpm_sets`, `atlas.unatlas`)
не кнопки базы.

## База 1.1 (#1024)

База 1.1 (станции `1.1.1`–`1.1.4`) — хендофф Max ↔ Blender, `TOUR_LAST = '1.1'`, камера `_cam_База 1.1`, строки в порядке
`roadmap.stage_buttons(suite, '1.1')`. Один фрагмент, ветка `BH` (`polygon_core.OWNER_110`, `"issue": "#1024"`,
сцены `frag_bh_*`, билдер `BH_build`):

| Файл | Кнопки |
|---|---|
| `BH.json` | `handoff.export`, `handoff.import`, `handoff.verify`, `handoff.restore_materials` |

`handoff.export` (preview, `options.job_dir`): PASS — коробка с уникальным именем, FAIL — коробка с двойником того же имени
(`duplicate_name`). Остальным трём нужен бандл `handoff/<seq>` на диске, а станция статична: ожидание `error` и `reason`;
PASS и FAIL круга проверяет нативный джоб ветки BH `tests/max_tools/run_agr_tools_handoff_native.py`.
Свои `expected/<id>.json` пишет `python test-polygon/polygon_core.py --branch BH`.
