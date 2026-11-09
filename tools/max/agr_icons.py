"""AGR Tools 0.6.0 icon set: own monochrome SVG sources, Dark/Light, PNG 24/30/36/48.

Pattern: new-case: generated monochrome icon set for the 3ds Max plugin package (#808).

Every icon is drawn here from primitives on a 24x24 grid (no third-party icon
fonts or files). One colour per theme: the Dark theme gets a light stroke, the
Light theme a dark stroke. Output layout matches the package spec of the
handoff: ``<out>/Dark/AgrIcons/agr_<name>.svg`` and ``agr_<name>_<NN>.png``.

    python tools/max/agr_icons.py <new-output-dir> [--sheet <new-sheet.png>]

PNG rendering needs PySide6 (QtSvg); SVG generation is stdlib only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SIZES = (24, 30, 36, 48)
THEMES = {"Dark": "#dcdcdc", "Light": "#383838"}

_S = 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
_F = 'fill="currentColor" stroke="none"'
# shared parts of the 0.9 bodies (mock-up sheet #853): a badge sits in the lower-right quarter
_B_CHECK = f'<circle {_S} cx="18" cy="18" r="4.6"/><path {_S} d="M16 18l1.4 1.4 2.6-2.8"/>'
_B_EYE = f'<circle {_S} cx="17" cy="17" r="3.4"/><path {_S} d="M19.5 19.5L22.5 22.5"/>'
_B_FIX = f'<path {_S} d="M14 22.5l4.6-4.6"/><circle {_S} cx="20.2" cy="16.3" r="2.6"/>'
_B_OUT = f'<path {_S} d="M14 18h8M19 15l3 3-3 3"/>'
_BENCH = f'<path {_S} d="M3 11h18M5 11v7M19 11v7M4 7h16M3 14h18"/>'
_TREE = f'<circle {_S} cx="12" cy="9" r="6"/><path {_S} d="M12 15v6M9 21h6"/>'
_BULB = f'<path {_S} d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3Z"/>'

# name -> (Russian label, SVG body on a 24x24 grid using currentColor)
BASE: dict[str, tuple[str, str]] = {
    "tools": ("Панель AGR Tools",
              f'<path {_S} d="M4 21V9l6-4v16M10 21V3l10 4v14M2 21h20"/>'
              f'<path {_S} d="M13 9h4M13 13h4M13 17h4M6 12h2M6 16h2"/>'),
    "xview": ("xView: перекрытия",
              f'<rect {_S} x="3" y="3" width="12" height="12" rx="1"/>'
              f'<rect {_S} x="9" y="9" width="12" height="12" rx="1"/>'
              f'<rect {_F} x="9" y="9" width="6" height="6" opacity="0.55"/>'),
    "matid": ("MatID",
              f'<rect {_S} x="3" y="3" width="8" height="8" rx="1"/>'
              f'<rect {_S} x="13" y="3" width="8" height="8" rx="1"/>'
              f'<rect {_S} x="3" y="13" width="8" height="8" rx="1"/>'
              f'<rect {_F} x="13" y="13" width="8" height="8" rx="1"/>'),
    "names": ("Имена NPM/VPM",
              f'<path {_S} d="M3 6.5V4h11l7 8-7 8H3v-2.5"/>'
              f'<path {_S} d="M6 9h6M6 12h8M6 15h5"/>'),
    "tris": ("Лимиты треугольников",
             f'<path {_S} d="M12 3L21.5 20H2.5Z"/>'
             f'<path {_S} d="M7.25 11.5h9.5L12 20Z"/>'),
    "textures": ("Текстуры",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="1.5"/>'
                 f'<path {_F} d="M3.8 3.8h5.4v5.4H3.8ZM14.8 3.8h5.4v5.4h-5.4ZM9.2 9.2h5.6v5.6H9.2Z'
                 f'M3.8 14.8h5.4v5.4H3.8ZM14.8 14.8h5.4v5.4h-5.4Z"/>'),
    "pivot": ("Пивот",
              f'<circle {_S} cx="12" cy="12" r="6.5"/>'
              f'<path {_S} d="M12 2v5M12 17v5M2 12h5M17 12h5"/>'
              f'<circle {_F} cx="12" cy="12" r="2"/>'),
    "cleanup": ("Очистка перед экспортом",
                f'<path {_S} d="M14.5 3.5l-4 7"/>'
                f'<path {_S} d="M7 10.5h7.5l2 3.5H5Z"/>'
                f'<path {_S} d="M5.5 14L4 21M9 14l-1 7M12.5 14l.5 7M16 14l1.5 7"/>'
                f'<path {_S} d="M19 3v3M17.5 4.5h3"/>'),
    "nudge": ("UV: сдвиг на целый тайл",
              f'<path {_S} d="M3 3v18h18" opacity="0.6"/>'
              f'<rect {_S} x="5" y="11" width="6" height="6" rx="0.5" stroke-dasharray="2 1.6"/>'
              f'<rect {_S} x="14" y="4" width="6" height="6" rx="0.5"/>'
              f'<path {_S} d="M10 12l4-3.5M14 8.5h-2.6M14 8.5v2.4"/>'),
    "atlas": ("UDIM -> атлас NPM",
              f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/>'
              f'<path {_S} d="M3 13h10M13 3v18M13 9h8M17 9v12"/>'),
    "texel": ("Плотность текселя",
              f'<path {_S} d="M3 16L16 3l5 5L8 21Z"/>'
              f'<path {_S} d="M7 12l2 2M10 9l1.5 1.5M13 6l2 2M5.5 13.5l1 1M11.5 7.5l1 1"/>'),
    "ucx": ("Коллизия UCX",
            f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5Z" stroke-dasharray="2.4 1.8"/>'
            f'<path {_S} d="M12 7l4.5 2.5v5L12 17l-4.5-2.5v-5Z"/>'
            f'<path {_S} d="M7.5 9.5L12 12l4.5-2.5M12 12v5"/>'),
    "export": ("Экспорт с проверкой",
               f'<path {_S} d="M4 13v7h16v-7"/>'
               f'<path {_S} d="M12 15V3M7.5 7.5L12 3l4.5 4.5"/>'),
    "geojson": ("Проверка GeoJSON",
                f'<path {_S} d="M3 19l5-2 8 3 5-2V6l-5 2-8-3-5 2Z" opacity="0.6"/>'
                f'<path {_S} d="M12 15.5s-4-3.6-4-6.5a4 4 0 0 1 8 0c0 2.9-4 6.5-4 6.5Z"/>'
                f'<circle {_F} cx="12" cy="9" r="1.4"/>'),
    # 0.7.0 pre-delivery checks (#860): bodies from the #853 mock-up (make_mockup.py, Drive agr-tools-suite)
    "census": ("Перепись сцены",
               f'<rect {_S} x="5" y="4" width="14" height="17" rx="1.5"/><path {_S} d="M9 4V2.5h6V4M8 10h8M8 14h8M8 18h5"/>'),
    "units": ("Единицы и гамма",
              f'<path {_S} d="M3 16L13 6l5 5L8 21Z"/><path {_S} d="M7 12l2 2M9.5 9.5l1.5 1.5M12 7l2 2"/>'),
    "drop": ("Опуск периметра",
             f'<path {_S} d="M5 12V4h14v8M2 12h20M5 12v7M19 12v7M12 13v8M9.5 18.5L12 21l2.5-2.5"/>'),
    "mattype": ("Тип материала",
                f'<circle {_S} cx="12" cy="12" r="8.5"/><path {_S} d="M3.5 12c3 3 14 3 17 0"/>'
                f'<circle {_F} cx="9" cy="8.5" r="1.6"/>'),
    "ucxaudit": ("UCX: аудит сцены",
                 '<g transform="scale(0.68)">'
                 f'<path {_S} d="M4 8l8-4 8 4v8l-8 4-8-4Z"/><path {_S} d="M4 8l8 4 8-4M12 12v8"/></g>'
                 f'<circle {_S} cx="18" cy="18" r="4.6"/><path {_S} d="M16 18l1.4 1.4 2.6-2.8"/>'),
    "setscount": ("Число текстурных наборов",
                  f'<rect {_S} x="3" y="9" width="12" height="12" rx="1"/><rect {_S} x="6" y="6" width="12" height="12" rx="1"/>'
                  f'<path {_S} d="M14 2.5l3 2-3 2M19 2.5h3"/>'),
    "split": ("Разделение FBX",
              f'<rect {_S} x="3" y="3" width="8" height="9" rx="1"/><rect {_S} x="13" y="3" width="8" height="9" rx="1"/>'
              f'<rect {_S} x="8" y="14" width="8" height="7" rx="1"/>'),
    "glasscheck": ("Стекло",
                   '<g transform="scale(0.68)">'
                   f'<rect {_S} x="4" y="3" width="16" height="18" rx="1"/>'
                   f'<path {_S} d="M12 3v18M4 12h16M7 9l2.5-2.5M14.5 18l2.5-2.5"/></g>'
                   f'<circle {_S} cx="18" cy="18" r="4.6"/><path {_S} d="M16 18l1.4 1.4 2.6-2.8"/>'),
    "preflight": ("Предсдача: все проверки",
                  f'<rect {_S} x="4" y="4" width="16" height="17" rx="1.5"/><path {_S} d="M9 4V2.5h6V4"/>'
                  f'<path {_S} d="M7 10l1.5 1.5 3-3M7 16l1.5 1.5 3-3M14 10.5h3M14 16.5h3"/>'),
    "hygiene": ("Лишнее в сцене",
                f'<rect {_S} x="3" y="7" width="12" height="10" rx="1"/><path {_S} d="M15 10.5l6-3v9l-6-3M3 3l18 18"/>'),
    "xform": ("Трансформы",
              f'<path {_S} d="M5 19V4M5 19h15M5 19l10-10M3 6.5L5 4l2 2.5M17.5 17L20 19l-2.5 2M11.5 9H15v3.5"/>'),
    "zero": ("Нулевые площади и рёбра",
             f'<path {_S} d="M4 7v10M20 7v10M4 12h16"/><circle {_F} cx="10.8" cy="12" r="1.8"/>'
             f'<circle {_F} cx="13.2" cy="12" r="1.8"/>'),
    "roadmap": ("Путь: как пользоваться",
                f'<circle {_S} cx="5" cy="5" r="2.5"/><circle {_S} cx="19" cy="12" r="2.5"/><circle {_S} cx="5" cy="19" r="2.5"/>'
                f'<path {_S} d="M7.5 5H14a5 5 0 0 1 0 7M16.5 12H10a5 5 0 0 0 0 7H7.5"/>'),
    # 0.8 delivery edits (#908): names = `icon` of the plan rows of version 0.8 (agr-tools-suite.json)
    "missing": ("Пропавшие карты",
                f'<rect {_S} x="3" y="4" width="13" height="13" rx="1"/><path {_S} d="M3 14l4-4 3 3 2-2 4 4"/>'
                f'<circle {_S} cx="17.5" cy="17.5" r="4"/><path {_S} d="M17.5 15.5v2.3"/>'
                f'<circle {_F} cx="17.5" cy="19.6" r="0.8"/>'),
    "triangulate": ("Триангуляция",
                    f'<path {_S} d="M3 6h18v12H3Z"/><path {_S} d="M3 18L10 6l5 12 6-12"/>'),
    "pngfix": ("PNG: формат",
               f'<path {_S} d="M5 3h9l5 5v13H5Z"/><path {_S} d="M14 3v5h5"/>'
               f'<path {_S} d="M8 16l2.5 2.5L16 13"/>'),
    "plug": ("Заглушки текстур",
             f'<rect {_S} x="3" y="3" width="18" height="18" rx="1.5"/><rect {_F} x="7" y="7" width="10" height="10" '
             f'rx="1" opacity="0.55"/><path {_S} d="M7 7l10 10"/>'),
    "ucxtri": ("UCX: триангуляция",
               f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5Z" stroke-dasharray="2.4 1.8"/>'
               f'<path {_S} d="M7 16l5-9 5 9Z"/><path {_S} d="M12 7v9"/>'),
    "ucxname": ("UCX: имена",
                '<g transform="scale(0.68)">'
                f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5Z" stroke-dasharray="2.4 1.8"/></g>'
                f'<path {_S} d="M11 14h10l-2.5 3.5L21 21H11Z"/>'),
    "id2udim": ("ID → UDIM",
                f'<rect {_S} x="2.5" y="8" width="6" height="8" rx="1"/><path {_S} d="M10 12h3M11.5 10.5L13 12l-1.5 1.5"/>'
                f'<rect {_S} x="15" y="4" width="7" height="7"/><rect {_S} x="15" y="13" width="7" height="7"/>'),
    "namefix": ("Исправить имена",
                f'<path {_S} d="M3 6.5V4h11l7 8-7 8H3v-2.5"/><path {_S} d="M6 12l2.5 2.5L13 9.5"/>'),
    "package": ("Проверка пакета",
                f'<path {_S} d="M3 7l9-4 9 4v10l-9 4-9-4Z"/><path {_S} d="M3 7l9 4 9-4M12 11v10"/>'
                f'<path {_S} d="M7.5 5l9 4"/>'),
    "geojsonw": ("Паспорт GeoJSON",
                 f'<path {_S} d="M3 19l5-2 8 3 5-2V6l-5 2-8-3-5 2Z" opacity="0.6"/>'
                 f'<path {_S} d="M8 15l7-7 2 2-7 7H8Z"/>'),
    "groundfbx": ("FBX благоустройства",
                  f'<path {_S} d="M2 17l5-3 5 2 5-3 5 2"/><path {_S} d="M7 14V9M5 10.5L7 7l2 3.5"/>'
                  f'<path {_S} d="M14 21v-6M11.5 18.5L14 21l2.5-2.5"/>'),
    "place": ("Пивот и положение",
              f'<path {_S} d="M3 19h18"/><circle {_S} cx="12" cy="12" r="4"/><path {_S} d="M12 3v5M12 16v3"/>'
              f'<circle {_F} cx="12" cy="12" r="1.5"/>'),
    "zip": ("Архив пакета",
            f'<rect {_S} x="4" y="3" width="16" height="18" rx="1.5"/>'
            f'<path {_S} d="M11 3v2h2v2h-2v2h2v2h-2"/><rect {_S} x="10" y="13" width="4" height="4" rx="0.8"/>'),
    # 0.9 rows (#979): names = `icon` of the plan rows of version 0.9 (agr-tools-suite.json). Bodies from the #853
    # mock-up sheet (make_mockup.py, team-scripts agent-jobs/agr-tools-suite, SHA256 4a1be887...be54; SYNTHESIS §4
    # «не строки плана»), the 0.6 sheet style; `mapsuse` and `procobj` are new rows (SYNTHESIS §4) drawn here.
    "ermn": ("ERM и нормали DirectX",
             f'<circle {_S} cx="9" cy="9" r="5"/><circle {_S} cx="15" cy="9" r="5"/><circle {_S} cx="12" cy="14.5" r="5"/>'),
    "finish": ("Покраска по легенде",
               f'<rect {_S} x="3" y="3" width="14" height="6" rx="1"/><path {_S} d="M17 6h3v5h-8v3"/>'
               f'<rect {_F} x="10" y="14" width="4" height="7" rx="1"/>'),
    "mafuv": ("MatID → UDIM (МАФ)",
              f'<g transform="scale(0.68)">{_BENCH}</g><path {_S} d="M14 14h8v8h-8ZM18 14v8M14 18h8"/>'),
    "slots": ("UDIM: тайлы и слоты",
              f'<rect {_S} x="2.5" y="6" width="5" height="12" rx="1"/><rect {_S} x="9.5" y="6" width="5" height="12" rx="1"/>'
              f'<rect {_F} x="16.5" y="6" width="5" height="12" rx="1" opacity="0.55"/>'),
    "flora": ("Атлас Flora", _TREE),
    "groundel": ("Атлас GroundEl", _BENCH),
    "florafix": ("Flora: ремонт и проверка", f'<g transform="scale(0.68)">{_TREE}</g>{_B_FIX}'),
    "mafcheck": ("Проверки МАФ", f'<g transform="scale(0.68)">{_BENCH}</g>{_B_CHECK}'),
    "replace": ("Замена объектов",
                f'<rect {_S} x="3" y="3" width="8" height="8" rx="1"/><circle {_S} cx="17" cy="17" r="4"/>'
                f'<path {_S} d="M14 6h6M18 4l2 2-2 2M10 18H4M6 16l-2 2 2 2"/>'),
    "schedule": ("Расстановка по ведомости",
                 f'<rect {_S} x="3" y="3" width="11" height="17" rx="1"/><path {_S} d="M6 8h5M6 12h5M6 16h3"/>'
                 f'<path {_S} d="M18.5 21s-3.5-3.4-3.5-6a3.5 3.5 0 0 1 7 0c0 2.6-3.5 6-3.5 6Z"/>'),
    "ground": ("Посадить на рельеф",
               f'<rect {_S} x="8" y="3" width="8" height="6" rx="1"/>'
               f'<path {_S} d="M12 10.5v6M9.5 14L12 16.5l2.5-2.5M3 20c4-2 14-2 18 0"/>'),
    "address": ("Адрес и улицы",
                f'<path {_S} d="M12 21.5s-7-6.5-7-11.5a7 7 0 0 1 14 0c0 5-7 11.5-7 11.5Z"/>'
                f'<circle {_S} cx="12" cy="10" r="2.5"/>'),
    "compare": ("Сравнение с листом фасада",
                f'<rect {_S} x="2" y="5" width="6" height="14" rx="1"/><rect {_S} x="9" y="5" width="6" height="14" rx="1"/>'
                f'<rect {_S} x="16" y="5" width="6" height="14" rx="1"/><path {_S} d="M4 9h2M11 9h2M18 9h2"/>'),
    "normals": ("Нормали и двойные грани",
                f'<path {_S} d="M3 18h18M7 18V9M12 18V6M17 18V9M5.5 10.5L7 9l1.5 1.5M10.5 7.5L12 6l1.5 1.5'
                f'M15.5 10.5L17 9l1.5 1.5"/>'),
    "sintez": ("Сверка с SINTEZ",
               f'<rect {_S} x="3" y="3" width="9" height="12" rx="1"/><rect {_S} x="12" y="9" width="9" height="12" rx="1"/>'
               f'<path {_S} d="M14.5 14h4M14.5 17h4"/>'),
    "batch": ("Пакетный экспорт",
              f'<rect {_S} x="3" y="3" width="12" height="9" rx="1"/><rect {_S} x="3" y="13" width="12" height="8" rx="1"/>'
              f'{_B_OUT}'),
    "mapsuse": ("Карты: использованные / лишние",
                '<g transform="scale(0.68)">'
                f'<rect {_S} x="3" y="4" width="18" height="16" rx="1.5"/><path {_S} d="M3 16l5-5 4 4 3-3 6 6"/></g>'
                f'<path {_S} d="M14 15h8M14 18h8M14 21h5"/>'),
    "lightcheck": ("Проверка света", f'<g transform="scale(0.68)">{_BULB}</g>{_B_CHECK}'),
    "procobj": ("Процедурные объекты",
                '<g transform="scale(0.68)">'
                + "".join(f'<circle {_F} cx="{x}" cy="{y}" r="1.6"/>' for x, y in
                          [(5, 6), (11, 4), (18, 7), (7, 12), (14, 11), (20, 14), (4, 18), (11, 18), (17, 20)])
                + f'</g>{_B_EYE}'),
    # 1.0 conveyor (#1024, branch 0): icons of the 33 stage buttons (plan row `icon`; export.place_by_passport
    # shares `passport`). Big stage buttons: passport, body, winplace, capsule, roof, mattable, vpm, npm, npm2vpm,
    # deliver, agentreq (plan stages[].icon).
    "passport": ("Паспорт проекта",
                 f'<rect {_S} x="4" y="2.5" width="16" height="19" rx="1.5"/><circle {_S} cx="12" cy="9" r="2.6"/>'
                 f'<path {_S} d="M8 15h8M8 18h5"/>'),
    "intake": ("Приём источника",
               f'<path {_S} d="M3 14v5.5h18V14"/><path {_S} d="M12 3v11M8 10l4 4 4-4"/>'),
    "source": ("Класс источника",
               '<g transform="scale(0.68)">'
               f'<path {_S} d="M12 3l8 4.5v9L12 21l-8-4.5v-9Z"/><path {_S} d="M4 7.5l8 4.5 8-4.5M12 12v9"/></g>'
               f'{_B_EYE}'),
    "body": ("Бадик",
             f'<path {_S} d="M3 8l7-4 11 4v10l-11 4-7-4Z"/><path {_S} d="M3 8l11 4 7-4M14 12v10"/>'),
    "attachmat": ("Объединить по материалам",
                  f'<rect {_S} x="3" y="3" width="8" height="8" rx="1"/><rect {_F} x="13" y="3" width="8" height="8" '
                  f'rx="1" opacity="0.55"/><rect {_S} x="7" y="14" width="10" height="7" rx="1"/>'
                  f'<path {_S} d="M7 11l3 3M17 11l-3 3"/>'),
    "moveapart": ("Раздвинуть задвойки",
                  f'<path {_S} d="M9 4v16M15 4v16"/><path {_S} d="M6.5 12H2M4 10l-2 2 2 2M17.5 12H22M20 10l2 2-2 2"/>'),
    "gridclean": ("Чистка сетки фасада",
                  '<g transform="scale(0.68)">'
                  f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><path {_S} d="M3 12h18M12 3v18M3 3l9 9"/>'
                  f'</g>{_B_CHECK}'),
    "smallparts": ("Мелкие детали",
                   f'<path {_S} d="M7 3h6l3 5.2-3 5.2H7L4 8.2Z"/><circle {_S} cx="10" cy="8.2" r="2"/>'
                   f'<path {_S} d="M16 15l5 5M14.5 19.5l5-5"/>'),
    "winplace": ("Окна по проёмам",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><rect {_S} x="6" y="6" width="5" height="6"/>'
                 f'<rect {_S} x="13" y="6" width="5" height="6"/><path {_S} d="M8.5 6v6M15.5 6v6M8.5 15v4M6.5 17l2 2 '
                 f'2-2"/>'),
    "wingen": ("Генератор типов окон",
               f'<rect {_S} x="3" y="3" width="11" height="14" rx="0.5"/><path {_S} d="M8.5 3v14M3 10h11"/>'
               f'<circle {_S} cx="18" cy="18" r="2.2"/><path {_S} d="M18 13.5v2M18 20.5v2M13.5 18h2M20.5 18h2"/>'),
    "glass": ("Стекло плоскостями",
              f'<path {_S} d="M4 20L8 4h12l-4 16Z"/><path {_S} d="M10 15l4-6M13 16l2-3"/>'),
    "capsule": ("Капсулы интерьера",
                f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><rect {_S} x="7" y="7" width="10" height="10" '
                f'rx="4"/><rect {_F} x="9.5" y="9.5" width="5" height="5" rx="2" opacity="0.55"/>'),
    "roof": ("Крыша по парапету",
             f'<path {_S} d="M3 9h18M3 9v12M21 9v12M3 9V6h2v3M19 9V6h2v3"/><path {_S} d="M5 11.5h14" '
             f'stroke-dasharray="2 1.6"/><path {_S} d="M7 21v-5h4v5"/>'),
    "mattable": ("Таблица материалов",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><path {_S} d="M3 9h18M3 15h18M9 3v18"/>'
                 f'<rect {_F} x="4.5" y="10.5" width="3" height="3"/><path {_S} d="M12 6h6M12 12h6M12 18h4"/>'),
    "mattiles": ("Плитки: серые карты",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/>'
                 f'<path {_S} d="M3 9h18M3 15h18M9 3v6M15 9v6M9 15v6M17 3v6M7 9v6"/>'),
    "plugcolour": ("Цвет заглушки",
                   f'<rect {_F} x="3" y="3" width="11" height="11" rx="1" opacity="0.55"/>'
                   f'<rect {_S} x="3" y="3" width="11" height="11" rx="1"/>'
                   f'<path {_S} d="M21 3l-3 3M15.5 8.5l5 5M13 13l-5 5-2 .5.5-2 5-5M17 7l3 3"/>'),
    "vpm": ("Сборка ВПМ",
            f'<rect {_S} x="3" y="3" width="8" height="8" rx="0.5"/><rect {_S} x="13" y="3" width="8" height="8" '
            f'rx="0.5"/><rect {_S} x="3" y="13" width="8" height="8" rx="0.5"/><rect {_S} x="13" y="13" width="8" '
            f'height="8" rx="0.5"/><path {_S} d="M5 9V6l2-1.5L9 6v3M15 9V5h4v4"/>'),
    "rescale": ("Подгонка плотности",
                f'<rect {_S} x="3" y="13" width="8" height="8" rx="0.5"/><path {_S} d="M3 9V3h6M21 15v6h-6"/>'
                f'<path {_S} d="M11 13l9-9M15 4h5v5"/>'),
    "distort": ("Искажения UV",
                f'<path {_S} d="M3 4c6 2 12-2 18 0M3 12c6 3 12-3 18 0M3 20c6 2 12-2 18 0"/>'
                f'<path {_S} d="M3 4v16M12 3.5c1 5-1 11 0 17M21 4v16"/>'),
    "dilate": ("Отступы карт (dilate)",
               f'<path {_F} d="M8 8h6l2 4-2 4H8Z" opacity="0.55"/><path {_S} d="M6 5h9.5l3.5 7-3.5 7H6Z" '
               f'stroke-dasharray="2 1.6"/><path {_S} d="M2 12h3M22 12h-2"/>'),
    "udimplug": ("Острова-заглушки в UDIM",
                 f'<rect {_S} x="3" y="3" width="18" height="18" rx="0.5"/><path {_S} d="M12 3v18M3 12h18"/>'
                 f'<rect {_F} x="5.5" y="5.5" width="4" height="4"/><rect {_F} x="14.5" y="14.5" width="4" '
                 f'height="4"/>'),
    "npm": ("ВПМ → НПМ",
            f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><path {_S} d="M3 15h18M9 15v6M15 15v6"/>'
            f'<path {_S} d="M7 12V7l5-2.5L17 7v5"/>'),
    "strip": ("Фасадный атлас run-strip",
              f'<rect {_S} x="3" y="3" width="18" height="18" rx="1"/><path {_S} d="M3 8h18M3 13h18M3 17.5h18"/>'
              f'<path {_S} d="M7 3v5M13 8v5M17 13v4.5"/>'),
    "npm2vpm": ("НПМ → ВПМ",
                f'<rect {_S} x="2.5" y="7" width="8" height="10" rx="1"/><rect {_S} x="13.5" y="3" width="8" '
                f'height="8" rx="0.5"/><rect {_S} x="13.5" y="13" width="8" height="8" rx="0.5"/>'
                f'<path {_S} d="M10.5 9.5l3-2.5M10.5 14.5l3 2.5"/>'),
    "udim2id": ("UDIM → ID",
                f'<rect {_S} x="3" y="3" width="8" height="8" rx="0.5"/><rect {_S} x="3" y="13" width="8" height="8" '
                f'rx="0.5"/><path {_S} d="M13 12h3M14.5 10l2 2-2 2"/><path {_S} d="M19 8v8M17.5 9.5L19 8"/>'),
    "deliver": ("Сдача пакета",
                f'<path {_S} d="M3 8l9-5 9 5v9l-9 5-9-5Z"/><path {_S} d="M3 8l9 5 9-5M12 13v9M7.5 5.5l9 5"/>'),
    "ucxgap": ("UCX: нарезка и зазор",
               f'<path {_S} d="M10.5 3H4v18h6.5" stroke-dasharray="2.4 1.8"/><path {_S} d="M13.5 3H20v18h-6.5" '
               f'stroke-dasharray="2.4 1.8"/><path {_S} d="M12 2v20"/>'),
    "ucxstairs": ("UCX лестниц",
                  f'<path {_S} d="M3 21h4v-4h4v-4h4V9h4V5"/><path {_S} d="M3 21L19 5h2v16Z" '
                  f'stroke-dasharray="2.4 1.8"/>'),
    "lightfbx": ("FBX освещения", f'<g transform="scale(0.68)">{_BULB}</g>{_B_OUT}'),
    "omk": ("Код ОМК ТЭ",
            f'<path {_S} d="M3 6h18v12H3Z"/><path {_S} d="M6 9v6M8.5 9v6M10 9v6M13 9v6M15.5 9v6M18 9v6"/>'),
    "agentreq": ("Запрос агенту",
                 f'<path {_S} d="M4 4h16v11H11l-5 4.5V15H4Z"/><path {_S} d="M10 8a2 2 0 1 1 3 1.7c-.7.4-1 .9-1 1.6"/>'
                 f'<circle {_F} cx="12" cy="13" r="0.9"/>'),
    "agentok": ("Приём от агента",
                f'<path {_S} d="M4 4h16v11H11l-5 4.5V15H4Z"/><path {_S} d="M8.5 9.5l2.5 2.5 4.5-5"/>'),
    # 1.1: Max <-> Blender handoff on the agent stage and the Claude dock
    "handoffout": ("Хендофф: выгрузить в Blender",
                   f'<path {_S} d="M3 8l6-3.5L15 8v7l-6 3.5L3 15Z"/><path {_S} d="M3 8l6 3.5L15 8M9 11.5v7"/>'
                   f'<path {_S} d="M15.5 12h6M19 9.5l2.5 2.5-2.5 2.5"/>'),
    "handoffin": ("Хендофф: принять из Blender",
                  f'<path {_S} d="M9 8l6-3.5L21 8v7l-6 3.5L9 15Z"/><path {_S} d="M9 8l6 3.5L21 8M15 11.5v7"/>'
                  f'<path {_S} d="M2.5 12h6M6 9.5l2.5 2.5L6 14.5"/>'),
    "handoffcheck": ("Хендофф: сверка круга",
                     f'<path {_S} d="M4 9a8 8 0 0 1 14-3.5M20 15a8 8 0 0 1-14 3.5"/><path {_S} d="M18 2.5v3.5h-3.5'
                     f'M6 21.5V18h3.5"/><path {_S} d="M8.5 12l2.5 2.5 4.5-5"/>'),
    "matrestore": ("Восстановить материалы",
                   f'<circle {_S} cx="10" cy="10" r="6.5"/><path {_S} d="M6 8.5a4.5 4.5 0 0 1 6-2.5"/>'
                   f'<path {_S} d="M13 20a6 6 0 1 0 1-9"/><path {_S} d="M13.5 15.5V20h4.5"/>'),
    "agentdock": ("Claude-док",
                  f'<rect {_S} x="3" y="3" width="18" height="18" rx="1.5"/><path {_S} d="M14 3v18"/>'
                  f'<path {_S} d="M16.5 7.5h2M16.5 10.5h2M16.5 13.5h2"/><path {_S} d="M6 9l3 3-3 3"/>'),
    # status / control icons for the result table and the progress row
    "ok": ("Статус: ок",
           f'<circle {_S} cx="12" cy="12" r="9"/><path {_S} d="M7.5 12.5l3 3 6-6.5"/>'),
    "error": ("Статус: ошибка",
              f'<circle {_S} cx="12" cy="12" r="9"/><path {_S} d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>'),
    "warn": ("Статус: предупреждение",
             f'<path {_S} d="M12 3l9.5 17h-19Z"/><path {_S} d="M12 9.5v5"/>'
             f'<circle {_F} cx="12" cy="17.3" r="1.1"/>'),
    "cancel": ("Отмена",
               f'<circle {_S} cx="12" cy="12" r="9"/><rect {_F} x="8.5" y="8.5" width="7" height="7" rx="1"/>'),
    "select": ("Выделить в сцене",
               f'<path {_S} d="M5 3l13 7.5-5.5 1.5-2.5 5.5Z"/><path {_S} d="M13 12.5l5 6.5"/>'),
}

# "apply to new export copy" variants = base icon (scaled) + copy badge
APPLY: dict[str, tuple[str, str]] = {
    "cleanup_apply": ("cleanup", "Очистка: применить к копиям"),
    "nudge_apply": ("nudge", "UV-сдвиг: применить к копиям"),
    "atlas_apply": ("atlas", "Атлас: применить к копиям"),
    "ucx_apply": ("ucx", "UCX: применить к копиям"),
}

_BADGE = (f'<rect fill="none" stroke="currentColor" stroke-width="1.5" x="13.5" y="13.5" width="9" height="9" rx="1.5"/>'
          f'<path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" d="M18 15.6v4.8M15.6 18h4.8"/>')


def icon_body(name: str) -> str:
    if name in BASE:
        return BASE[name][1]
    if name in APPLY:
        base = BASE[APPLY[name][0]][1]
        return f'<g transform="scale(0.68)">{base}</g>{_BADGE}'
    raise KeyError(f"unknown AGR icon: {name}")


def names() -> list[str]:
    return list(BASE) + list(APPLY)


def label(name: str) -> str:
    return BASE[name][0] if name in BASE else APPLY[name][1]


def svg(name: str, color: str) -> str:
    body = icon_body(name).replace("currentColor", color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
            f'{body}</svg>\n')


def png_bytes(svg_text: str, size: int) -> bytes:
    """Render one PNG in memory (needs PySide6 and a Q(Gui)Application)."""
    from PySide6 import QtCore, QtGui, QtSvg

    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("invalid SVG")
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.WriteOnly)
    if not image.save(buf, "PNG"):
        raise OSError("cannot encode PNG")
    return bytes(buf.data())


def _render_png(svg_text: str, size: int, path: Path) -> None:
    from PySide6 import QtCore, QtGui, QtSvg

    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"invalid SVG for {path.name}")
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise OSError(f"cannot write {path}")


def build(out: Path, png: bool = True) -> list[Path]:
    if out.exists():
        raise FileExistsError(f"output exists, refusing to overwrite: {out}")
    written: list[Path] = []
    if png:
        from PySide6 import QtGui
        _app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])  # noqa: F841
    for theme, color in THEMES.items():
        folder = out / theme / "AgrIcons"
        folder.mkdir(parents=True)
        for name in names():
            text = svg(name, color)
            path = folder / f"agr_{name}.svg"
            path.write_text(text, encoding="utf-8", newline="\n")
            written.append(path)
            if png:
                for size in SIZES:
                    p = folder / f"agr_{name}_{size}.png"
                    _render_png(text, size, p)
                    written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--svg-only", action="store_true")
    args = ap.parse_args(argv)
    files = build(args.out, png=not args.svg_only)
    print(f"{len(files)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
