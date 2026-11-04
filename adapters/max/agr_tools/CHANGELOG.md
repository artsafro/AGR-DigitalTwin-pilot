# AGR Tools changelog

## 0.8.0 (#908) — в работе

Сдача: правки только на экспортных копиях или в новых файлах, каждая с preview. Пакет пока остаётся 0.7.0:
кнопки 0.8 есть в меню и MCP, в панели они серые «в версии 0.8» до релизной ветки.

### Основа (ветка 0)

- `edit_core.py`: контракт правки — preview → apply со сверкой хэша, `new_path()` без перезаписи,
  списки `done` / `skipped` (с причиной) / `ambiguous`, JSON-контракт 0.5.0, статус `not_implemented`.
- `edit_max.py`: экспортные копии, одна запись Undo на запуск, восстановление выделения, снимок до/после.
- `runtime.EDITS_080` (13 строк плана) и `runtime.edits_080(tool, mode, preview)`; пустой модуль отвечает
  `status: not_implemented`. Секция «Сдача (копии)»: 13 macroScript, пункты меню, 13 иконок, 13 MCP-инструментов.
- План: вердикт `take_fix` по лаборатории #907 для `model.triangulate`, `ucx.triangulate`, `export.ground_fbx`.

### A — геометрия (`improve/issue-908-geom`)

- Заглушка ветки A: `model.triangulate`, `ucx.triangulate`, `export.pivot_place`.

### B — текстуры (`improve/issue-908-tex`)

- Заглушка ветки B: `tex.format_fix`, `tex.placeholders`, `scene.missing_maps`.

### C — имена и UDIM (`improve/issue-908-names`)

- Заглушка ветки C: `qa.names_fix`, `ucx.rename`, `udim.ids_to_udims`.

### D — пакет (`improve/issue-908-package`)

- Заглушка ветки D: `qa.package`, `export.zip`, `export.ground_fbx`, `export.geojson_write`.

## 0.7.0 (#860)

Pre-delivery checks (read-only) + tab rail by block + «Путь», all from `agr-tools-suite.json` (#853 plan).

- 12 checks of plan version 0.7 (`suite_core.py` logic, `suite_max.py` pymxs reads, snapshots only, D6):
  `scene.census`, `scene.units` (D5), `model.perimeter_drop` (AGR_ZERO_M, ≥ 1 m), `tex.material_type`,
  `ucx.audit` (twinqa ucx_audit slice), `atlas.sets_count`, `qa.fbx_split`, `qa.glass` (D2, D3),
  `qa.preflight` (all object checks, one table), `qa.scene_hygiene` (D7), `qa.xform` (D6), `qa.zero_area`.
  JSON report contract of 0.5.0 (`schema`/`tool`/`status`/`objects`/`plan`), status derived from findings.
- Panel: tab rail on the left — «Путь» + the 10 blocks in plan order, one accent per block derived from the
  Max palette (≥ 3:1 against window and base, else an error, never a pale colour). Planned buttons of
  versions 0.8–1.x are shown greyed with «в версии 0.x».
- «Путь»: pipeline nodes in block colours with steps and buttons, tooltip (what / when / mode / requirements),
  «?» card, live status per block from the last reports of this scene (`%LOCALAPPDATA%/AGRTools/reports`),
  «Следующий шаг». `docs/agr-tools/GUIDE.md` + `flow.svg` are generated from the same JSON.
- MCP (`agr-mcp` phase 0): 12 read-only tools `agr_<block>_<name>` over `runtime.checks_070`.

## 0.6.0 (#808)

Native Qt UI over all 17 existing actions; no check logic changed.

- Dockable panel `AgrToolsPanel` (PySide6 on Max 2025/2026, PySide2 on 2024 through `ui_qt.py`),
  parented to the Max main window, Max accelerators disabled on focus, dock position kept in
  `3dsMax.ini` `[AGRTools] dock=`. Five sections by work step, each with its own accent hue
  (stripe, header, icon tint) derived from the Max palette; result table (red/green), click selects
  the object, «Выделить ошибки», «Сохранить отчёт JSON…».
- Progress bar + «Отмена» and the Max progress bar (progressStart/Update/getProgressCancel/End).
  xView and MatID run in chunks of 25 objects (exact merge); other actions are one runtime call
  with a busy bar. Buttons are disabled while running.
- Every action is a macroScript with `iconName:"AgrIcons/agr_<id>"`, Russian label and tooltip
  (what it does + requirement ids); `agr_tools_runtime.ui('<tool>')` and `agr_tools_runtime.panel()`
  stay the Python/MAXScript API. Classic rollout `AGRToolsClassic` is the fallback.
- Menu «AGR Tools» via `#cuiRegisterMenus` (Max 2025+), survives a menu preset change.
- Application Plugin Package `AGR-Tools.bundle` (`build_agr_tools.py --bundle`), UpgradeCode
  `{BA2C2E6E-54F9-402E-8875-3D616C9030FD}`, Dark/Light icon components. Icons: own SVG set,
  PNG 24/30/36/48 rendered at build time (not committed).

## 0.5.0 (#804)

Five read-only diagnostics. None of them edits the open scene. Each writes a 0.4.0 JSON report
(`schema`, `tool`, `status`, `objects`, `plan`) to the Listener.

Base: GeoAGR 13.64 (author Artem), recovered `GeoAGR.ms` (GeoAGR-private@31c723e), with the author's
permission. Only the functions in use are adapted, in `checks_core.py`. Each function's docstring names
its `GeoAGR.ms:<line>` and its changes.

- **Names check NPM/VPM** (`names`): object (SM/UCX), (sub-)material (M) and texture file (T) names.
  Adapted from `check_names_all` (`GeoAGR.ms:6907`) and `check_names_all_vpm` (`:7331`).
  Fixes D2: the exact last token decides Main/MainGlass/Ground/UCX, not a substring `case`.
  Fixes D4: SlotNumber 1..7 is legal; GeoAGR required exactly `1`.
- **Triangle limits per FBX** (`tris`): budgets are summed per `AGR_EXPORT_PATH` FBX and per model
  kind. The limits are NPM OKS 150 000, NPM Ground 180 000, VPM OKS 1 000 000 (UCX excluded), VPM
  Ground by the site-area table (`AGR_SITE_AREA_HA`) and VPM UCX by the decided formula. Fixes D8,
  where GeoAGR summed over the selection. The stale 2 000 000 VPM limit is gone.
- **Textures check (all objects)** (`textures`): the maps of every object are checked. Fixes D1,
  where GeoAGR read the last object only. An empty `usedMaps` array means "no maps". Fixes D3,
  where GeoAGR tested the array against undefined. The checks are size, square shape, placeholders,
  alpha, 8 bits per channel (from the PNG header), file size, the UDIM set and UV padding. Padding is
  NPM 8 px and VPM 16/32 px for 2048/4096 maps; GeoAGR's 16/32 px branch was commented out.
  Padding is measured per texture atlas: each face goes to its matID's sub-material maps, and the
  islands of all objects of one FBX that share an atlas are measured together (per UDIM tile). An
  unmapped matID is `tex_unmeasurable`; a sub-material without maps is `tex_missing`. In VPM, touching
  or overlapping islands (gap 0) are the review-level `tex_overlap_review`, not `tex_padding`:
  regulation 2.5.1.5 applies padding only to islands with unique images, and repeating islands may
  overlap. A VPM gap above 0 and below 16/32 px is still `tex_padding`; NPM is unchanged.
- **Pivot check** (`pivot`): VPM-2.9-4.b requires pivot Z = 0 within 1 mm. VPM-2.9-5 requires every
  pivot of one FBX to coincide within 1 mm. UCX pivots are free (VPM-2.9-4.c).
- **GeoJSON check** (`geojson`): runs the pilot `twinqa.geojson` checker on a chosen `.geojson`
  in the project Python (`AGR_PYTHON` or `<repo>/.venv`). A broken file or a crashing checker is
  reported as a finding, never a raise.
- D6 (Prepare LowPoly/HighPoly destroy the scene) does not apply: the glue only reads
  `snapshotAsMesh` copies in memory, `usedMaps` and the PNG files on disk.

## 0.4.0

Checked export: one FBX per `AGR_EXPORT_PATH`, gated and read back.

## 0.3.0

UCX collision, texel readout.
