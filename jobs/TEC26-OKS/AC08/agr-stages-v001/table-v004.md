# AC08 (TEC26-OKS) через этапы 0–9 — AGR Tools 1.1.0 (Max 28000.68.0)

**Модель: РЕАЛЬНАЯ AC08** `C:\x\1513-ac08-agr-stages\src\AC08_source_geomfinal.fbx` sha256 `9cae468e714118c501dfffa77531aabecd88662c4e34d0be57274d446bb3e5fd`; карта id {"1": 999, "2": 11, "3": 2}.



| Этап | Кнопки (статус) | Время, с | Треугольники: видимые / всего / новые | Статус этапа | Коротко |
|---|---|---:|---|---|---|
| 0 Паспорт | project.passport findings (0.07 с); source.intake done (0.1 с); scene.source_class done (0.03 с) | 0.28 | 348 / 708 / 348 | findings | codes: role_missing x2 — паспорт: C:\x\1513-ac08-agr-stages\run-v004\proj\jobs\TEC26-OKS\passport.json readback копий: [6.058754, 2.438, 4.596754] |
| 1 Бадик | body.prepare done (0.06 с); model.attach_by_material done (0.05 с); model.move_apart done (0.07 с); model.grid_cleanup done (0.69 с); scene.small_parts done (0.02 с) | 0.99 | 664 / 1024 / 664 | done |  — attach: фасад и парапет стали одним телом BODY_MultiMat0_001 |
| 2 Окна | win.place ambiguous (0.1 с); win.generate skipped (0.0 с); model.glass_planes skipped (0.0 с) | 0.12 | 664 / 1024 / 0 | ambiguous | ambiguous: нет проёмов и меток: запрос агенту «разметь проёмы → тип по размерам и альбому» |
| 3 Капсулы | body.capsules done (0.08 с) | 0.1 | 664 / 1024 / 0 | done | codes: no_openings x1 |
| 4 Крыша | body.roof done (0.06 с) | 0.09 | 664 / 1024 / 0 | done | codes: no_roof_loop x1 — плита: [] |
| 5 Материалы | mat.table findings (0.04 с); mat.tiles refused (0.03 с); tex.plug_colour skipped (0.0 с) | 0.11 | 664 / 1024 / 0 | findings | codes: id_not_in_library x1 |
| 6 ВПМ | vpm.build refused (1.04 с); vpm.build (повтор без library_path: шаг 6 карт выключен) refused (0.67 с); udim.rescale done (0.27 с); udim.distortion findings (0.26 с); tex.dilate skipped (0.0 с); udim.plugs skipped (0.0 с) | 2.34 | 664 / 1024 / 0 | refused | ValueError: nothing to build: every object has findings (see the preview) — нет копии ВПМ: малые кнопки этапа 6 нажаты на рабочем теле |
| 7 НПМ | npm.build refused (0.54 с); atlas.facade_strip done (0.9 с) | 1.47 | 1012 / 1372 / 348 | refused | ValueError: nothing to build: the preview has findings (fail-closed, nothing written) — нет копий ВПМ: npm.build нажат на рабочем теле |
| 8 НПМ→ВПМ | npm.to_vpm refused (0.03 с); udim.udims_to_ids findings (0.26 с) | 0.32 | 1012 / 1372 / 0 | refused | ValueError: nothing selected: select the objects — нет npm_table.json от npm.build: npm.to_vpm без таблицы (регионы атласа) |
| 9 Сдача | qa.names_fix done (0.1 с); ucx (0.8 runtime.ucx_preview/ucx_apply) done (0.56 с); ucx.rename done (0.02 с); ucx.gap done (0.09 с); ucx.stairs refused (0.01 с); light.export refused (0.02 с); qa.omk_te ambiguous (0.01 с); pack.deliver ambiguous (3.73 с); pack.deliver (B: skip light.check, light.export, qa.omk_te, qa.preflight, qa.sintez) ambiguous (1.72 с); export.place_by_passport refused (0.02 с) | 7.17 | 1444 / 2152 / 780 | ambiguous | ambiguous: {'item': 'pack.deliver', 'reason': 'qa.preflight: SM_Nku_1_Main: fbx_ground_missing qa.fbx_split: VPM: нет Ground FBX; UCX_SM_Nku_1_Main_001: fbx_grou — A: этап 9 blocked; шаги qa.preflight=fail, qa.names=fail, qa.tris=pass, ucx.audit=pass, light.check=error, qa.sintez=error, ucx.gap=error, qa.omk_te=fail, light.export=error, export.checked=fail, export.zip=planned B: этап 9 blocked; шаги qa.preflight=skipped, qa.names=fail, qa.tris=pass, ucx.audit= |

## SINTEZ и qa.package

- `qa_package`: skipped — pack.deliver не записал архив (этап 9 blocked)
- `qa_sintez`: refused — ValueError: qa.sintez needs options.sintez: the SINTEZ AGR Checker report (JSON of run_agr_checker.py)

## Шаги стенда (не кнопки)

- этап 0: исходник скрыт после source.intake; дальше работает копия АС.08_AGR_intake_001
- этап 0: source.intake сдвинул копию на -origin_m [30.0, -2.0, -3.0]: +-0.000 = 3.0 м, уровни [{'name': 'L1', 'z_m': 3.0}, {'name': 'roof', 'z_m': 5.5502}]
- этап 9: рабочее имя копии ВПМ BODY_MultiMat0_001 -> Nku_1_VPM_Main (токен роли Main для qa.names_fix: vpm.build называет копию <источник>_VPM_NNN)
- этап 9: рабочая копия ВПМ Nku_1_VPM_Main скрыта: сдаётся копия qa.names_fix SM_Nku_1_Main
- этап 9: вход художника: AGR_EXPORT_PATH=C:/x/1513-ac08-agr-stages/run-v004/deliver_B/SM_Nku_1.fbx на 8 узлах, AGR_ZERO_M=3.0000 на SM_Nku_1_Main (+-0.000 исходника после сдвига source.intake; ни одна кнопка 1.0 их не задаёт)
- этап 9: вход художника: 1 узлов перенесены на слой «0» (qa.scene_hygiene hyg_layer)

Всего: 18.63 с; журнал: 63 строк.
