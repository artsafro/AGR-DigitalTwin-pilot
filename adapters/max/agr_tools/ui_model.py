"""new-case: pure model of the AGR Tools 0.6.0 panel (#808); no Qt, no pymxs.

Actions, sections, Russian labels and tooltips, report -> table rows, the batched
progress loop with cancel (read on the next chunk boundary, about 0.9 s on Max 2024),
dock-state parsing and palette-derived accents. Everything here runs under plain
pytest; ui_panel.py only draws it.
"""
import base64
import binascii
import colorsys
import json
import math
import os
from collections import namedtuple

VERSION = '1.1.0'

# wip=True (1.0 conveyor, #1024): the button is visible but disabled, tooltip «в работе, #1024», its macro never
# runs an edit. Default False keeps every 0.x Action(...) call of nine fields valid.
Action = namedtuple('Action', 'id tool icon section label tip reqs macro batch wip', defaults=(False,))

SECTIONS = ('Проверки', 'UV и атласы', 'Коллизии UCX', 'Экспорт', 'GeoJSON', 'Сдача (копии)',
            'Проверить и выделить', 'Исправить — копии / undo / новые файлы')  # 6, 7: 0.9 rows by mode (#979)

# id == icon name in tools/max/agr_icons.py; tool == runtime.ui() argument; macro == macroScript name.
# batch=True only for tools whose report is a per-object independent list (merge is exact).
ACTIONS = (
    Action('xview', 'xview', 'xview', 0, 'xView: перекрытия',
           'Ищет совпадающие вершины и перекрытые грани; выделяет объекты с ошибками.',
           ('NPM-2.3-9', 'VPM-2.3-11'), 'AGRToolsXView', True),
    Action('matid', 'matid', 'matid', 0, 'MatID',
           'Проверяет ID материалов граней против слотов Multi/Sub-Object.',
           ('NPM-2.4-5', 'VPM-2.4-5'), 'AGRToolsMatID', True),
    Action('names', 'names', 'names', 0, 'Имена NPM/VPM',
           'Проверяет имена объектов, материалов и текстур по маскам NPM/VPM (только чтение).',
           ('NPM-2.10-1', 'NPM-2.10-2', 'NPM-2.10-3.3.a', 'VPM-2.10-2.a', 'VPM-2.11-0.a',
            'VPM-2.11-0.c'), 'AGRToolsNames', False),
    Action('tris', 'tris', 'tris', 0, 'Треугольники по FBX',
           'Считает треугольники на каждый FBX и сравнивает с лимитом (только чтение).',
           ('NPM-2.3-6', 'VPM-2.3-9', 'VPM-2.3-10'), 'AGRToolsTris', False),
    Action('textures', 'textures', 'textures', 0, 'Текстуры (все)',
           'Проверяет формат, размер, альфу и отступы текстур всех объектов (только чтение).',
           ('NPM-2.5-1', 'NPM-2.5-4', 'VPM-2.5-1'), 'AGRToolsTextures', False),
    Action('pivot', 'pivot', 'pivot', 0, 'Пивот',
           'Проверяет пивот: Z = 0 и один пивот на FBX, допуск 1 мм (только чтение).',
           ('VPM-2.9-4', 'VPM-2.9-5'), 'AGRToolsPivot', False),
    Action('nudge', 'nudge', 'nudge', 1, 'UV-сдвиг (пробно)',
           'Пробный расчёт сдвига UV-островов на целый тайл; сцену не меняет.',
           ('VPM-2.5-2.1.3.a',), 'AGRToolsNudge', False),
    Action('nudge_apply', 'nudge_apply', 'nudge_apply', 1, 'UV-сдвиг → копии',
           'Применяет последний пробный UV-сдвиг к новым экспортным копиям; оригиналы не трогает.',
           ('VPM-2.5-2.1.3.a',), 'AGRToolsNudgeApply', False),
    Action('atlas', 'atlas', 'atlas', 1, 'UDIM → атлас (пробно)',
           'Пробная сборка атласа NPM из UDIM-тайлов; сцену не меняет.',
           ('NPM-2.5-1', 'NPM-2.5-4'), 'AGRToolsAtlas', False),
    Action('atlas_apply', 'atlas_apply', 'atlas_apply', 1, 'Атлас → копии',
           'Применяет последний пробный атлас к новым экспортным копиям; оригиналы не трогает.',
           ('NPM-2.5-1', 'NPM-2.5-4'), 'AGRToolsAtlasApply', False),
    Action('texel', 'texel', 'texel', 1, 'Тексель',
           'Показывает минимум и медиану px/m по объектам и материалам (только чтение).',
           ('VPM-2.6-2', 'NPM-2.6-1'), 'AGRToolsTexel', False),
    Action('ucx', 'ucx', 'ucx', 2, 'UCX (пробно)',
           'Пробный расчёт выпуклых коллизий UCX_; сцену не меняет.',
           ('VPM-2.13-1', 'VPM-2.13-7'), 'AGRToolsUcx', False),
    Action('ucx_apply', 'ucx_apply', 'ucx_apply', 2, 'UCX → копии',
           'Создаёт UCX_-коллизии из последнего пробного расчёта на новых копиях.',
           ('VPM-2.13-1', 'VPM-2.13-7'), 'AGRToolsUcxApply', False),
    Action('cleanup', 'cleanup', 'cleanup', 3, 'Очистка (пробно)',
           'Пробная очистка перед экспортом: каналы UV, свойства, атрибуты; сцену не меняет.',
           ('VPM-2.3-11.e',), 'AGRToolsCleanup', False),
    Action('cleanup_apply', 'apply', 'cleanup_apply', 3, 'Очистка → копии',
           'Применяет последнюю пробную очистку к новым экспортным копиям.',
           ('VPM-2.3-11.e',), 'AGRToolsCleanupApply', False),
    Action('export', 'export', 'export', 3, 'Экспорт с проверкой',
           'Первое нажатие: пробный экспорт и все проверки; второе на том же выделении пишет FBX.',
           ('NPM-1.2-1', 'VPM-1.2-1'), 'AGRToolsExport', False),
    Action('geojson', 'geojson', 'geojson', 4, 'Проверка GeoJSON',
           'Проверяет паспорт GeoJSON проверяющим модулем twinqa (выбор файла).',
           ('GJ-1', 'GJ-2', 'GJ-3', 'VPM-2.2-1'), 'AGRToolsGeojson', False),
    # 0.7.0 pre-delivery checks (#860): read-only, plan rows of version 0.7 (docs/plans/agr-tools-suite.json)
    Action('census', 'census', 'census', 0, 'Перепись сцены',
           'Перепись: классы объектов, материалы, карты, пропавшие файлы, bbox, инстансы (только чтение).',
           ('NPM-2.1-1.b', 'VPM-2.1-1.c'), 'AGRToolsCensus', False),
    Action('units', 'units', 'units', 0, 'Единицы и гамма',
           'Проверяет System Unit = метры, масштаб 1, гамму файлов 1.0 (только чтение).',
           ('NPM-1.2-1', 'VPM-1.2-1'), 'AGRToolsUnits', False),
    Action('perimeter_drop', 'perimeter_drop', 'drop', 0, 'Опуск периметра ≥1 м',
           'Нижняя точка ОКС/Ground не меньше 1 м ниже ±0.000 (AGR_ZERO_M) (только чтение).',
           ('NPM-2.3-4', 'VPM-2.3-6', 'VPM-2.3-7.a'), 'AGRToolsPerimeterDrop', False),
    Action('material_type', 'material_type', 'mattype', 0, 'Тип материала',
           'Только Standard/Physical; Corona, VRay и другие — ошибка с именем материала (только чтение).',
           ('NPM-2.4-1.a', 'NPM-2.4-1.b', 'VPM-2.4-1.a', 'VPM-2.4-1.b'), 'AGRToolsMaterialType', False),
    Action('ucx_audit', 'ucx_audit', 'ucxaudit', 0, 'UCX: аудит сцены',
           'Готовые UCX_: замкнутость, выпуклость, без материалов, имя, пересечения SAT, бюджет (только чтение).',
           ('VPM-2.13-1.a', 'VPM-2.13-3', 'VPM-2.13-4.a', 'VPM-2.13-7.a'), 'AGRToolsUcxAudit', False),
    Action('sets_count', 'sets_count', 'setscount', 0, 'Число текстурных наборов',
           'Наборы на FBX: ОКС ≤40 (+1 кровля), Ground ≤20, GroundEl 1, Flora 1 (только чтение).',
           ('NPM-2.1-4.c', 'NPM-2.1-5.b', 'NPM-2.5-11.a', 'NPM-2.5-11.b'), 'AGRToolsSetsCount', False),
    Action('fbx_split', 'fbx_split', 'split', 0, 'Разделение FBX',
           'ОКС ≤20 FBX, ≤20 объектов на FBX, Ground обязателен, нумерация сквозная (только чтение).',
           ('NPM-2.1-2', 'NPM-2.1-4.a', 'NPM-2.2-1', 'VPM-2.1-3.a'), 'AGRToolsFbxSplit', False),
    Action('glass', 'glass', 'glasscheck', 0, 'Стекло',
           'Стекло на отдельном *Glass, ≤20 прозрачных, ≤7 материалов, без карт, 50 % (только чтение).',
           ('NPM-2.7-2', 'NPM-2.4-2', 'VPM-2.8-1', 'VPM-2.8-2'), 'AGRToolsGlass', False),
    Action('scene_hygiene', 'scene_hygiene', 'hygiene', 0, 'Лишнее в сцене',
           'Камеры, свет, кости, анимация, группы и иерархия, пустые объекты, модификаторы (только чтение).',
           ('NPM-2.1-3.a', 'NPM-2.1-3.b', 'VPM-2.3-1', 'VPM-2.3-2'), 'AGRToolsSceneHygiene', False),
    Action('xform', 'xform', 'xform', 0, 'Трансформы сброшены',
           'Несброшенный масштаб, поворот, зеркало и родители; сброс только на копиях (только чтение).',
           ('NPM-2.3-14', 'VPM-2.3-18'), 'AGRToolsXform', False),
    Action('zero_area', 'zero_area', 'zero', 0, 'Нулевые площади и рёбра',
           'Грани нулевой площади, рёбра нулевой длины, изолированные вершины (только чтение).',
           ('NPM-2.3-7.b', 'NPM-2.3-7.c', 'VPM-2.3-11.b', 'VPM-2.3-11.c'), 'AGRToolsZeroArea', False),
    Action('preflight', 'preflight', 'preflight', 0, 'Предсдача: все проверки',
           'Все проверки 0.7 одним нажатием, одна таблица; сцена не меняется.',
           ('NPM-2.1-3.c', 'VPM-2.3-1'), 'AGRToolsPreflight', False),
    # 0.8 delivery edits (#908): one Action per plan row of version 0.8; tool == plan row id, routed to
    # runtime.edits_080 (preview, then apply on the same selection). Copies / new files only, never overwrite.
    Action('missing_maps', 'scene.missing_maps', 'missing', 5, 'Пропавшие карты',
           'Список битмапов с несуществующим путём и кандидаты для relink; файлы не переименовываются (только чтение).',
           ('NPM-2.1-1.b', 'VPM-2.4-2'), 'AGRToolsMissingMaps', False),
    Action('triangulate', 'model.triangulate', 'triangulate', 5, 'Триангуляция → копии',
           'Первое нажатие: пробно; второе на том же выделении триангулирует n-гоны на экспортных копиях.',
           ('NPM-2.3-11', 'VPM-2.3-17'), 'AGRToolsTriangulate', False),
    Action('format_fix', 'tex.format_fix', 'pngfix', 5, 'PNG: формат → новые файлы',
           'Пробно, затем пишет исправленные PNG в новую папку: без альфы, 24 бит, до лимита; исходники не трогает.',
           ('NPM-2.5-2.a', 'NPM-2.5-3', 'NPM-2.5-5', 'VPM-2.5-1.6', 'VPM-2.5-1.9'), 'AGRToolsFormatFix', False),
    Action('placeholders', 'tex.placeholders', 'plug', 5, 'Заглушки 256 / 128',
           'Пробно, затем создаёт новые однотонные заглушки Diffuse/ERM/Normal нужного размера и цвета.',
           ('VPM-2.5-3.1', 'VPM-2.5-3.3', 'VPM-2.5-3.4', 'NPM-2.5-7'), 'AGRToolsPlaceholders', False),
    Action('ucx_triangulate', 'ucx.triangulate', 'ucxtri', 5, 'UCX: триангуляция → копии',
           'Пробно, затем триангулирует UCX на копиях и проверяет выпуклость после.',
           ('VPM-2.3-17', 'VPM-2.13-1.a'), 'AGRToolsUcxTriangulate', False),
    Action('ucx_rename', 'ucx.rename', 'ucxname', 5, 'UCX: имена',
           'Пробно, затем переименовывает куски в UCX_SM_<Address>_Main/Ground_NNN одной записью Undo.',
           ('VPM-2.13-1.d', 'VPM-2.10-4.2.b'), 'AGRToolsUcxRename', False),
    Action('ids_to_udims', 'udim.ids_to_udims', 'id2udim', 5, 'ID → UDIM на копии',
           'Пробно, затем раскладывает материал ID n в тайл 1000+n на экспортных копиях.',
           ('VPM-2.5-2.1.3.a', 'VPM-2.5-2.1.3.b'), 'AGRToolsIdsToUdims', False),
    Action('names_fix', 'qa.names_fix', 'namefix', 5, 'Исправить имена → копии',
           'Пробно, затем переименовывает объекты, материалы и файлы карт по маске на экспортных копиях.',
           ('NPM-2.10-3.3.a', 'NPM-2.10-3.4.a', 'VPM-2.11-0.a', 'VPM-2.10-4.3'), 'AGRToolsNamesFix', False),
    Action('package', 'qa.package', 'package', 5, 'Проверка пакета ZIP',
           'ZIP: размеры, состав FBX/PNG/GeoJSON, имена, битые файлы, readback (только чтение).',
           ('NPM-2.1-1.a', 'NPM-2.1-1.b', 'VPM-2.1-1.a', 'VPM-2.1-1.b', 'VPM-2.1-2.a', 'VPM-2.1-2.c',
            'VPM-2.1-2.d'), 'AGRToolsPackage', False),
    Action('geojson_write', 'export.geojson_write', 'geojsonw', 5, 'Паспорт GeoJSON → новый файл',
           'Пробно, затем пишет новый GeoJSON из сцены (пивот, положение, адрес, превью) и сразу проверяет.',
           ('VPM-2.2-1', 'VPM-2.2-2', 'VPM-2.2-6.a', 'VPM-2.2-7', 'GJ-1', 'GJ-19.a', 'GJ-19.b', 'GJ-21.a',
            'VPM-2.10-4.1.e'), 'AGRToolsGeojsonWrite', False),
    Action('ground_fbx', 'export.ground_fbx', 'groundfbx', 5, 'FBX благоустройства',
           'Пробно, затем пишет новый _Ground.fbx: Ground, GroundEl, Flora, GroundGlass в одном файле.',
           ('NPM-2.1-5.a', 'VPM-2.1-4'), 'AGRToolsGroundFbx', False),
    Action('pivot_place', 'export.pivot_place', 'place', 5, 'Пивот и положение → копии',
           'Пробно, затем ставит пивот на копиях: НПМ в МСК с высотами, ВПМ в ноль (чистый пол).',
           ('NPM-2.8-1', 'NPM-2.8-2', 'VPM-2.9-4.b', 'VPM-2.9-5'), 'AGRToolsPivotPlace', False),
    Action('zip', 'export.zip', 'zip', 5, 'Архив пакета → новый ZIP',
           'Пробно, затем пишет новый ZIP НПМ/ВПМ с лимитами 500 МБ / 1 ГБ, проверка до и после.',
           ('NPM-2.1-1.a', 'VPM-2.1-1.a', 'VPM-2.1-1.b', 'VPM-2.1-2.b'), 'AGRToolsZip', False),
    # 0.9 rows (#979): one Action per plan row of version 0.9, plan order; tool == plan row id, routed to
    # runtime.edits_090. The section names the mode: 6 = read/select (scene unchanged), 7 = copies / undo / new files.
    # Logic is written by branches A–D; until then every press answers status not_implemented.
    Action('erm_normal_check', 'tex.erm_normal_check', 'ermn', 6, 'ERM и нормали DirectX',
           'Проверяет каналы ERM (R только свечение) и ориентацию нормалей DirectX (только чтение).',
           ('VPM-2.5-1.7', 'VPM-2.14-1', 'VPM-2.14-2', 'VPM-2.14-3'), 'AGRToolsErmNormalCheck', False),
    Action('finish_map', 'tex.finish_map', 'finish', 7, 'Покраска по легенде → копии',
           'Пробно, затем на копиях: ID → отделка по листу цветового решения, легенда, кольца швов, проверка.',
           ('NPM-2.4-4', 'VPM-2.4-1.a'), 'AGRToolsFinishMap', False),
    Action('matid_unwrap', 'udim.matid_unwrap', 'mafuv', 7, 'MatID → UDIM (МАФ) → копии',
           'Пробно, затем на копиях: развёртка по MatID в тайлы с плотностью и упаковкой.',
           ('VPM-2.6-2', 'VPM-2.5-2.1.3.a'), 'AGRToolsMatidUnwrap', False),
    Action('udim_slots', 'udim.slots', 'slots', 6, 'UDIM: тайлы и слоты',
           '1001… без пропусков, ≤100 карт на материал, SlotNumber 1…7 подряд (только чтение).',
           ('VPM-2.4-3.a', 'VPM-2.4-3.b', 'VPM-2.5-2.1.3.a', 'VPM-2.11-0.b'), 'AGRToolsUdimSlots', False),
    Action('atlas_flora', 'atlas.flora', 'flora', 7, 'Атлас Flora → новые файлы',
           'Пробно, затем пишет новые атласы: диффуз флоры + прозрачность, кроп по UV, тайл на текстуру.',
           ('NPM-2.5-13.a', 'NPM-2.5-13.b', 'NPM-2.5-4'), 'AGRToolsAtlasFlora', False),
    Action('atlas_groundel', 'atlas.groundel', 'groundel', 7, 'Атлас GroundEl ≤512 → копии',
           'Пробно, затем на копиях: один набор элементов благоустройства, ≤512 px.',
           ('NPM-2.5-12', 'NPM-2.1-5.b'), 'AGRToolsAtlasGroundel', False),
    Action('flora_repair', 'place.flora_repair', 'florafix', 7, 'Flora: ремонт → копии',
           'Пробно, затем на копиях чинит трансформы и треугольники Flora и проверяет набор.',
           ('NPM-2.5-13.a', 'NPM-2.3-14'), 'AGRToolsFloraRepair', False),
    Action('maf_checks', 'place.maf_checks', 'mafcheck', 6, 'Проверки МАФ',
           'Летающие и утопленные МАФ: AABB-предфильтр, лучи вниз к Ground с допуском; пересечения (только чтение).',
           ('NPM-2.3-6.b', 'NPM-2.5-12'), 'AGRToolsMafChecks', False),
    Action('replace', 'place.replace', 'replace', 7, 'Замена объектов (Undo)',
           'Пробно, затем заменяет объекты по маске или выделению на эталон одной записью Undo; отчёт со списками.',
           ('NPM-2.3-5', 'VPM-2.3-8'), 'AGRToolsReplace', False),
    Action('schedule', 'place.schedule', 'schedule', 7, 'Расстановка по ведомости → копии',
           'Пробно, затем ставит МАФ по ведомости; отчёт: поставлено / нет эталона / нет места.',
           ('NPM-2.1-5.a',), 'AGRToolsSchedule', False),
    Action('drop_to_ground', 'place.drop_to_ground', 'ground', 7, 'Посадить на рельеф (Undo)',
           'Пробно, затем опускает выделенные объекты на Ground лучом вниз одной записью Undo.',
           ('-',), 'AGRToolsDropToGround', False),
    Action('address', 'qa.address', 'address', 6, 'Адрес и улицы',
           'Проверка Address по справочнику улиц, составных частей и длины (только чтение).',
           ('NPM-1.3-2.a', 'NPM-1.3-3.a', 'VPM-1.3-2.a', 'VPM-1.3-3.a'), 'AGRToolsAddress', False),
    Action('facade_compare', 'qa.facade_compare', 'compare', 6, 'Сравнение с листом фасада',
           'Картинка «лист | ВПМ | НПМ» в одном масштабе и счёт швов (только чтение).',
           ('-',), 'AGRToolsFacadeCompare', False),
    Action('normals', 'qa.normals', 'normals', 6, 'Нормали и двойные грани',
           'Нормали к наблюдателю, двусторонние полигоны стекла/Flora, сглаживание (только чтение).',
           ('NPM-2.3-8.a', 'NPM-2.3-15', 'VPM-2.3-14', 'VPM-2.3-15.a', 'VPM-2.12-3'), 'AGRToolsNormals', False),
    Action('sintez', 'qa.sintez', 'sintez', 6, 'Сверка с SINTEZ',
           'Сравнивает наши находки с отчётом SINTEZ по тем же правилам (только чтение).',
           ('VPM-2.3-17',), 'AGRToolsSintez', False),
    Action('batch', 'export.batch', 'batch', 7, 'Пакетный экспорт → новые FBX',
           'Пробно, затем пишет все FBX сцены по AGR_EXPORT_PATH одним запуском с одним отчётом.',
           ('NPM-2.1-2',), 'AGRToolsBatch', False),
    Action('maps_usage', 'scene.maps_usage', 'mapsuse', 6, 'Карты: использованные / лишние',
           'Какие файлы карт используются геометрией, какие лишние в папке maps, какие пропали (только чтение).',
           ('-',), 'AGRToolsMapsUsage', False),
    Action('light_check', 'light.check', 'lightcheck', 6, 'Проверка света',
           '≤250 источников, только Omni/Spot, Omni ≥5 м, Spot ≥1.5 м, корень и пивот (только чтение, выделяет нарушителей).',
           ('VPM-2.15-2', 'VPM-2.15-4', 'VPM-2.15-5.a', 'VPM-2.15-5.b', 'VPM-2.15-6', 'VPM-2.15-8', 'VPM-2.15-9.b'),
           'AGRToolsLightCheck', False),
    Action('procedural_objects', 'qa.procedural_objects', 'procobj', 6, 'Процедурные объекты',
           'Несвёрнутые Forest Pack, RailClone, MultiScatter, Chaos Scatter, tyFlow, RayFire, Populate перед FBX '
           '(только чтение и выделение).', ('-',), 'AGRToolsProceduralObjects', False),
)

# ---- 1.0 conveyor (#1024, branch 0): the 33 stage buttons in station order 1.0.1..1.0.33 ----------------------
# One Action per plan row with fate `stage` (roadmap.stage_buttons); tool == plan row id (runtime.EDITS_100),
# icon / label / reqs == the plan row. They live on the stage rail of «Путь», not in SECTIONS (section None) and not
# in ACTIONS (the 0.x panel, 61 actions). wip=True until the owner branch (F..U) ships the logic.
# A test checks every field and the stage grouping against docs/plans/agr-tools-suite.json.
WIP_TIP = 'в работе, #1024'
STAGES_100 = (  # (stage id, label_ru, icon, (rows; the first is the big button)) == plan `stages`
    (0, 'Паспорт', 'passport', ('project.passport', 'source.intake', 'scene.source_class')),
    (1, 'Бадик', 'body', ('body.prepare', 'model.attach_by_material', 'model.move_apart', 'model.grid_cleanup',
                          'scene.small_parts')),
    (2, 'Окна', 'winplace', ('win.place', 'win.generate', 'model.glass_planes')),
    (3, 'Капсулы', 'capsule', ('body.capsules',)),
    (4, 'Крыша', 'roof', ('body.roof',)),
    (5, 'Материалы', 'mattable', ('mat.table', 'mat.tiles', 'tex.plug_colour')),
    (6, 'ВПМ', 'vpm', ('vpm.build', 'udim.rescale', 'udim.distortion', 'tex.dilate', 'udim.plugs')),
    (7, 'НПМ', 'npm', ('npm.build', 'atlas.facade_strip')),
    (8, 'НПМ → ВПМ', 'npm2vpm', ('npm.to_vpm', 'udim.udims_to_ids')),
    (9, 'Сдача', 'deliver', ('pack.deliver', 'ucx.gap', 'ucx.stairs', 'light.export', 'qa.omk_te',
                             'export.place_by_passport')),
    ('agent', 'Агент', 'agentreq', ('agent.request', 'agent.accept', 'handoff.export', 'handoff.import',
                                    'handoff.verify', 'handoff.restore_materials')),
)
_ROWS_100 = {  # plan row id -> (icon, label_ru, reqs)
    'project.passport': ('passport', 'Паспорт проекта', '-'),
    'source.intake': ('intake', 'Приём источника', '-'),
    'scene.source_class': ('source', 'Класс источника', '-'),
    'body.prepare': ('body', 'Бадик для агента', '-'),
    'model.attach_by_material': ('attachmat', 'Объединить по материалам', '-'),
    'model.move_apart': ('moveapart', 'Раздвинуть задвойки', 'NPM-2.3-9 VPM-2.3-13'),
    'model.grid_cleanup': ('gridclean', 'Чистка сетки фасада', 'NPM-2.3-7.b VPM-2.3-11.b'),
    'scene.small_parts': ('smallparts', 'Мелкие детали (метизы)', '-'),
    'win.place': ('winplace', 'Окна по проёмам', '-'),
    'win.generate': ('wingen', 'Окна: генератор типов', '-'),
    'model.glass_planes': ('glass', 'Стекло плоскостями', 'NPM-2.3-10 VPM-2.8-4'),
    'body.capsules': ('capsule', 'Капсулы интерьера', '-'),
    'body.roof': ('roof', 'Крыша по парапету', '-'),
    'mat.table': ('mattable', 'Таблица материалов', '-'),
    'mat.tiles': ('mattiles', 'Плитки: серые карты', '-'),
    'tex.plug_colour': ('plugcolour', 'Цвет заглушки', 'VPM-2.5-3.4'),
    'vpm.build': ('vpm', 'Сборка ВПМ', '-'),
    'udim.rescale': ('rescale', 'Подгонка плотности', 'VPM-2.6-2 NPM-2.6-1'),
    'udim.distortion': ('distort', 'Искажения UV', 'VPM-2.6-2'),
    'tex.dilate': ('dilate', 'Отступы карт (dilate)', 'NPM-2.5-4 VPM-2.5-1.5'),
    'udim.plugs': ('udimplug', 'Острова-заглушки в UDIM', '-'),
    'npm.build': ('npm', 'ВПМ → НПМ', '-'),
    'atlas.facade_strip': ('strip', 'Фасадный атлас run-strip', 'NPM-2.5-11.a NPM-2.5-4'),
    'npm.to_vpm': ('npm2vpm', 'НПМ → ВПМ', '-'),
    'udim.udims_to_ids': ('udim2id', 'UDIM → ID (просмотр)', 'VPM-2.5-2.1.3.a'),
    'pack.deliver': ('deliver', 'Сдача пакета', '-'),
    'ucx.gap': ('ucxgap', 'UCX: нарезка и зазор', 'VPM-2.13-4.a VPM-2.13-4.b'),
    'ucx.stairs': ('ucxstairs', 'UCX лестниц', 'VPM-2.13-5 VPM-2.13-6'),
    'light.export': ('lightfbx', 'FBX освещения _Light',
                     'VPM-2.1-2.b VPM-2.11-0.f VPM-2.11-0.g VPM-2.10-4.1.c VPM-2.10-4.5'),
    'qa.omk_te': ('omk', 'Код ОМК ТЭ', 'NPM-2.10-3.1'),
    'export.place_by_passport': ('passport', 'Поставить по паспорту', '-'),
    'agent.request': ('agentreq', 'Запрос агенту', '-'),
    'agent.accept': ('agentok', 'Приём от агента', '-'),
    # 1.1: Max <-> Blender handoff on the agent stage (stations 1.1.1..1.1.4)
    'handoff.export': ('handoffout', 'Хендофф: выгрузить в Blender', '-'),
    'handoff.import': ('handoffin', 'Хендофф: принять из Blender', '-'),
    'handoff.verify': ('handoffcheck', 'Хендофф: сверка круга', '-'),
    'handoff.restore_materials': ('matrestore', 'Восстановить материалы', '-'),
}
# plan version of a stage row that is not 1.0 (its tooltip says «1.1, этап ...»)
ROW_VERSION_100 = {'handoff.export': '1.1', 'handoff.import': '1.1', 'handoff.verify': '1.1',
                   'handoff.restore_materials': '1.1'}
# 1.1: stage rows with a parameter form in the dock (== params_core.TOOLS, a test pins it). Their macro opens the
# panel form (runtime.form_ui) instead of pressing without options.
FORM_100 = ('atlas.facade_strip', 'tex.dilate', 'tex.plug_colour', 'export.place_by_passport', 'agent.request',
            'agent.accept', 'handoff.export', 'handoff.import', 'handoff.verify', 'handoff.restore_materials')
# 1.1: «Claude-док» (agentbridge_max.agent_dock through runtime.agent_dock): a panel/menu action outside the plan
# rows (no report, no preview/apply), like the open-panel macro.
DOCK_MACRO = 'AGRToolsAgentDock'
DOCK_LABEL = 'Claude-док'
DOCK_TIP = '1.1, этап «Агент»: док агента Claude (свой listener, профиль modeller, «Применить» только в доке)'
DOCK_ICON = 'agentdock'


# Release 1.0.0 (#1024 R): all 13 branches F..U are merged (Q #1085 last), so no 1.0 row is wip. A row of a later
# branch would be listed here (SPLIT.md «Порядок слияния» 3: an unmerged branch keeps wip and moves to 1.1.0).
WIP_100 = frozenset()


def stage_tip(tool):
    """Tooltip head of a released stage button: «<plan version>, этап <n> <stage>» (the agent stage has no number):
    «1.0, этап 2 «Окна»», «1.1, этап «Агент»»."""
    for sid, label, _icon, rows_ in STAGES_100:
        if tool in rows_:
            return ROW_VERSION_100.get(tool, '1.0') + ', ' + (
                'этап «Агент»' if sid == 'agent' else 'этап {} «{}»'.format(sid, label))
    raise KeyError('not a 1.0 stage row: ' + repr(tool))


def _action_100(tool):
    icon, label, reqs = _ROWS_100[tool]
    macro = 'AGRTools' + ''.join(p.capitalize() for p in tool.replace('.', '_').split('_'))
    wip = tool in WIP_100
    return Action(tool.replace('.', '_'), tool, icon, None, label, WIP_TIP if wip else stage_tip(tool),
                  tuple(reqs.split()), macro, False, wip)


ACTIONS_100 = tuple(_action_100(tool) for _sid, _label, _icon, rows_ in STAGES_100 for tool in rows_)
ALL_ACTIONS = ACTIONS + ACTIONS_100
BY_ID = {a.id: a for a in ALL_ACTIONS}
BY_TOOL = {a.tool: a for a in ALL_ACTIONS}
OPEN_MACRO = 'AGRToolsOpen'
CATEGORY = 'AGR Tools'
ICON_PREFIX = 'AgrIcons/agr_'


def action(key):
    """Unknown id is an error naming it, never a default."""
    if key in BY_ID:
        return BY_ID[key]
    if key in BY_TOOL:
        return BY_TOOL[key]
    raise KeyError('unknown AGR Tools action: ' + repr(key))


def tooltip(a):
    return '{} Треб.: {}'.format(a.tip, ', '.join(a.reqs))


def icon_name(a):
    return ICON_PREFIX + a.icon


def sections():
    """[(title, [actions...]), ...] in work-step order."""
    return [(title, [a for a in ACTIONS if a.section == i]) for i, title in enumerate(SECTIONS)]


Row = namedtuple('Row', 'handle name check ok code detail ids')


def rows(report):
    """Report -> table rows. Each object gives one row per finding, or one OK row.
    A report without an objects list (texel, export) gives one summary row.
    Report-level failures (GeoJSON plan findings, an export stopped by a gate, a cancelled run) give
    their own error rows; status == 'fail' <=> at least one error row, else ValueError (#808 review P1)."""
    if not isinstance(report, dict) or 'tool' not in report:
        raise ValueError('not an AGR Tools report')
    check = report['tool']
    status = report.get('status')
    if status == 'not_implemented':  # 0.8/0.9 stub module (#908/#979): one error row, never a pass
        plan = report.get('plan') if isinstance(report.get('plan'), dict) else {}
        issue = plan.get('issue') if isinstance(plan.get('issue'), str) else '#908'
        return [Row(None, '—', check, False, 'not_implemented', 'в работе ({}): модуль ещё пуст'.format(issue), ())]
    if status not in ('pass', 'fail'):
        raise ValueError('report without pass/fail status: ' + repr(status))
    objects = report.get('objects')
    if objects is None:
        return [Row(None, '—', check, status == 'pass', status, '', ())]
    if not isinstance(objects, list):
        raise ValueError('report objects is not a list')
    out = _object_rows(check, objects) + _report_rows(check, report)
    bad = any(not r.ok for r in out)
    if status == 'pass' and bad:
        raise ValueError('report status pass with error rows: ' + repr(check))
    if status == 'fail' and not bad:  # failed without a named cause (e.g. FBX read-back mismatch)
        out.append(Row(None, '—', check, False, 'fail', 'отчёт: status fail', ()))
    return out


def _report_rows(check, report):
    """Error rows for failures that live outside report['objects']."""
    out = []
    plan = report.get('plan')
    if isinstance(plan, dict):
        findings = plan.get('findings')
        if findings is not None:
            if not isinstance(findings, list):
                raise ValueError('plan findings is not a list')
            name = os.path.basename(str(plan.get('path') or '')) or '—'
            for f in findings:
                if not isinstance(f, dict) or 'status' not in f:
                    raise ValueError('plan finding without status: ' + repr(f))
                if f['status'] == 'pass':
                    continue
                code = str(f.get('name', '?'))
                if f['status'] != 'fail':
                    code += ': ' + str(f['status'])
                out.append(Row(None, name, check, False, code,
                               'получено {}, ожидалось {}'.format(f.get('observed', ''), f.get('expected', '')), ()))
        stopped = plan.get('stopped')
        if stopped not in (None, 'texel'):
            out.append(Row(None, '—', check, False, 'stopped', 'остановлено проверкой ' + str(stopped), ()))
    cancelled = report.get('cancelled')
    if cancelled:
        out.append(Row(None, '—', check, False, 'cancelled',
                       'отменено: {} / {}'.format(cancelled.get('done'), cancelled.get('total')), ()))
    return out


def _object_rows(check, objects):
    out = []
    for o in objects:
        findings = o.get('findings')
        if not isinstance(findings, list):
            raise ValueError('object without findings list: ' + repr(o.get('name')))
        handle = o.get('handle')
        name = str(o.get('name', ''))
        if not findings:
            out.append(Row(handle, name, check, True, 'ok', '', ()))
        for f in findings:
            out.append(Row(handle, name, check, False, str(f.get('code', '')), str(f.get('detail', '')),
                           tuple(f.get('ids') or ())))
    return out


# (report tool, finding code) -> component kind of the finding ids (#861). The ids are 1-based polyop indices of
# the checked node's Editable_Poly copy; any other check or code is selected as the whole object.
COMPONENT_IDS = {('xview', 'overlap_vertices'): 'vertex', ('xview', 'overlap_faces'): 'face',
                 ('matid', 'udim_id'): 'face', ('matid', 'empty_id'): 'face', ('matid', 'empty_slot'): 'face',
                 ('matid', 'missing_material'): 'face'}


def component_selection(row, num_verts, num_faces):
    """Row -> (kind, sorted unique ids) to select on its node, or None = select the object only.
    Fail-closed: an unknown (check, code), empty ids, a non-int id or an id outside 1..count gives None."""
    kind = COMPONENT_IDS.get((row.check, row.code))
    if kind is None or not row.ids:
        return None
    count = num_verts if kind == 'vertex' else num_faces
    if any(type(i) is not int or not 1 <= i <= count for i in row.ids):
        return None
    return kind, sorted(set(row.ids))


def counts(row_list):
    bad = sum(1 for r in row_list if not r.ok)
    return bad, len(row_list) - bad


def summary(row_list):
    bad, ok = counts(row_list)
    return 'Ошибок {} · ОК {}'.format(bad, ok)


def chunks(items, size):
    if size < 1:
        raise ValueError('chunk size must be >= 1')
    items = list(items)
    return [items[i:i + size] for i in range(0, len(items), size)]


def merge(tool, parts):
    """Merge per-chunk reports of a batch tool. Duplicate handles are an error."""
    objects, seen = [], set()
    for p in parts:
        if p.get('tool') != tool:
            raise ValueError('chunk report of another tool: ' + repr(p.get('tool')))
        for o in p['objects']:
            if o['handle'] in seen:
                raise ValueError('duplicate handle in chunks: ' + repr(o['handle']))
            seen.add(o['handle'])
            objects.append(o)
    return {'schema': 1, 'tool': tool,
            'status': 'fail' if any(o['findings'] for o in objects) else 'pass', 'objects': objects}


class Cancelled(Exception):
    def __init__(self, message, partial=None, done=0):
        super().__init__(message)
        self.partial = partial
        self.done = done


# Event-loop pumps during a batch are timed, not counted. Max 2024 spent 1.36 s
# inside one 25-object xView chunk before the next processEvents; Max 2026 chunks
# were already under 0.2 s. The gap must stay strictly under PUMP_GAP_LIMIT_S.
# A budget of exactly that limit (or anything outside (0, limit)) is an error.
# One pymxs object is atomic, so a gap is at most the budget plus that object.
# PUMP_BUDGET_S leaves headroom under the limit for a small object.
PUMP_GAP_LIMIT_S = 0.1
PUMP_BUDGET_S = 0.09


def check_pump_budget(budget):
    if isinstance(budget, bool) or not isinstance(budget, (int, float)):
        raise ValueError('unsupported pump budget')
    value = float(budget)
    if not math.isfinite(value) or value <= 0.0 or value >= PUMP_GAP_LIMIT_S:
        raise ValueError('pump budget out of range')
    return value


def check_pump_cost(cost):
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        raise ValueError('unsupported pump cost')
    value = float(cost)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError('pump cost out of range')
    return value


def object_pump(since, estimate, cost, budget=PUMP_BUDGET_S):
    """Online pump decision after one atomic object (pymxs cannot be sliced).

    `cost` is that object's wall time. Returns (pump, since, estimate). The next
    similar object is assumed to cost `estimate`, so the open gap closes before
    it would meet the budget. A huge object is not sliced: the gap that just
    closed is at most the budget plus that one object. Empty, partial, unsupported,
    non-finite, negative and a budget of exactly PUMP_GAP_LIMIT_S are errors.
    """
    limit = check_pump_budget(budget)
    spent = check_pump_cost(cost)
    since = check_pump_cost(since)
    estimate = check_pump_cost(estimate)
    since += spent
    if spent > 0.0:
        estimate = spent
    if since >= limit or (estimate > 0.0 and since + estimate >= limit):
        return True, 0.0, estimate
    return False, since, estimate


def run_batched(tool, fn, nodes, size, progress, cancelled):
    """Run fn(chunk) per chunk; progress(done, total) after each; cancelled() before each.

    Cancel is not read inside a chunk. A Cancel click takes effect only before the
    next chunk, so on Max 2024 the latency is one 25-object chunk (about 0.9 s).
    The chunk already running is still merged and counted; raising from the
    per-object pump would drop that chunk's results. A cancel raises Cancelled
    with the partial report attached (status fail, never a pass).
    """
    nodes = list(nodes)
    if not nodes:
        raise ValueError('empty target set')
    parts, done = [], 0
    progress(0, len(nodes))
    for chunk in chunks(nodes, size):
        if cancelled():
            partial = None
            if parts:  # a cancelled run is never a pass, even when every finished chunk was clean
                partial = merge(tool, parts)
                partial['status'] = 'fail'
                partial['cancelled'] = {'done': done, 'total': len(nodes)}
            raise Cancelled('cancelled at {} / {}'.format(done, len(nodes)), partial, done)
        parts.append(fn(chunk))
        done += len(chunk)
        progress(done, len(nodes))
    return merge(tool, parts)


def percent(done, total):
    if total <= 0:
        return 0
    return max(0, min(100, int(done * 100 // total)))


# Dock state: {'floating': bool, 'area': int, 'geometry': base64 str, 'visible': bool}
DOCK_AREAS = (1, 2, 4, 8)  # Qt.LeftDockWidgetArea .. BottomDockWidgetArea
DEFAULT_DOCK = {'floating': False, 'area': 2, 'geometry': '', 'visible': True}


def dump_dock(state):
    return json.dumps(parse_dock(json.dumps(state)), sort_keys=True)


def parse_dock(text):
    """Bad or partial saved state falls back to the default dock (right side), never crashes."""
    try:
        data = json.loads(text) if text else {}
    except (TypeError, ValueError):
        return dict(DEFAULT_DOCK)
    if not isinstance(data, dict):
        return dict(DEFAULT_DOCK)
    out = dict(DEFAULT_DOCK)
    if isinstance(data.get('floating'), bool):
        out['floating'] = data['floating']
    if isinstance(data.get('visible'), bool):
        out['visible'] = data['visible']
    if data.get('area') in DOCK_AREAS and not isinstance(data.get('area'), bool):
        out['area'] = data['area']
    geo = data.get('geometry')
    if isinstance(geo, str) and geo:
        try:
            base64.b64decode(geo, validate=True)
            out['geometry'] = geo
        except (binascii.Error, ValueError):
            pass
    return out


def _lum(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


_HUES = {'error': 0.0, 'ok': 1.0 / 3.0, 'warn': 1.0 / 7.0}
# Section accents (Artem 2026-11-04: «разбавить цветовыми оттенками»): hue per work step, chosen
# >= 30 degrees away from the status hues red 0 and green 120 so a section never reads as a status.
SECTION_HUES = (210.0, 275.0, 35.0, 185.0, 320.0, 245.0,  # Проверки, UV, UCX, Экспорт, GeoJSON, Сдача (deg)
                60.0, 155.0)  # 0.9 (#979): Проверить и выделить, Исправить
STATUS_HUES_DEG = (0.0, 120.0)


def hue_gap(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def section_accent(index, base_rgb, text_rgb):
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(SECTIONS):
        raise KeyError('unknown section: ' + repr(index))
    return _accent_hue(SECTION_HUES[index] / 360.0, base_rgb, text_rgb)


def accent(kind, base_rgb, text_rgb):
    """Accent colour derived from the theme: hue by meaning, lightness from the palette text,
    pushed until the contrast against the table base is >= 3 (WCAG large/UI)."""
    if kind not in _HUES:
        raise KeyError('unknown accent: ' + repr(kind))
    return _accent_hue(_HUES[kind], base_rgb, text_rgb)


def _accent_hue(hue, base_rgb, text_rgb):
    for v in (*base_rgb, *text_rgb):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not 0 <= v <= 255:
            raise ValueError('bad palette colour')
    dark = _lum(base_rgb) < _lum(text_rgb)
    light = colorsys.rgb_to_hls(*(c / 255.0 for c in text_rgb))[1]
    lightness = min(0.72, max(0.55, light * 0.8)) if dark else max(0.22, min(0.38, light + 0.25))
    for _ in range(40):
        rgb = tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(hue, lightness, 0.6))
        if contrast(rgb, base_rgb) >= 3.0:
            return rgb
        lightness = lightness + 0.02 if dark else lightness - 0.02
        lightness = min(0.95, max(0.05, lightness))
    raise ValueError('no accent with contrast >= 3 for this palette')


def theme_name(window_rgb):
    return 'Dark' if _lum(window_rgb) < 0.2 else 'Light'


# ---- 0.7.0 tab rail: blocks of the plan (#853/#860) ---------------------------------------------------
# Every panel action is one row of docs/plans/agr-tools-suite.json; the *_apply variants share the row of
# their dry run. A test checks this map against the JSON (no action without a row, no row id twice).
ROW = {'xview': 'qa.xview', 'matid': 'qa.matid', 'names': 'qa.names', 'tris': 'qa.tris', 'textures': 'tex.check',
       'pivot': 'qa.pivot', 'nudge': 'udim.nudge', 'nudge_apply': 'udim.nudge', 'atlas': 'atlas.npm',
       'atlas_apply': 'atlas.npm', 'texel': 'udim.texel', 'ucx': 'ucx.build', 'ucx_apply': 'ucx.build',
       'cleanup': 'export.cleanup', 'cleanup_apply': 'export.cleanup', 'export': 'export.checked',
       'geojson': 'qa.geojson', 'census': 'scene.census', 'units': 'scene.units',
       'perimeter_drop': 'model.perimeter_drop', 'material_type': 'tex.material_type', 'ucx_audit': 'ucx.audit',
       'sets_count': 'atlas.sets_count', 'fbx_split': 'qa.fbx_split', 'glass': 'qa.glass',
       'preflight': 'qa.preflight', 'scene_hygiene': 'qa.scene_hygiene', 'xform': 'qa.xform',
       'zero_area': 'qa.zero_area'}
ROW.update({a.id: a.tool for a in ACTIONS if a.section == SECTIONS.index('Сдача (копии)')})  # 0.8: tool == row id
ROW.update({a.id: a.tool for a in ACTIONS if a.section in (6, 7)})  # 0.9 (#979): tool == row id
ROW.update({a.id: a.tool for a in ACTIONS_100})  # 1.0 (#1024): tool == row id
NEUTRAL_SAT = 0.06   # block 0 «Сцена» is a service block: almost grey (plan §7)
BLOCK_SAT = 0.6


def row_of(action_id):
    if action_id not in ROW:
        raise KeyError('action without a plan row: ' + repr(action_id))
    return ROW[action_id]


def block_accent(hue_deg, window_rgb, base_rgb, text_rgb):
    """Block colour derived from the Max theme (plan §7): hue of the block, lightness moved away from the
    background until the contrast is >= 3:1 against BOTH window and base; unreachable -> ValueError."""
    if hue_deg is not None and (not isinstance(hue_deg, (int, float)) or isinstance(hue_deg, bool)
                                or not math.isfinite(hue_deg) or not 0 <= hue_deg < 360):
        raise ValueError('bad block hue: ' + repr(hue_deg))
    for v in (*window_rgb, *base_rgb, *text_rgb):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not 0 <= v <= 255:
            raise ValueError('bad palette colour')
    hue = (hue_deg or 0.0) / 360.0
    sat = NEUTRAL_SAT if hue_deg is None else BLOCK_SAT
    dark = _lum(base_rgb) < _lum(text_rgb)
    start = 62 if dark else 36
    # nearest lightness to the theme's start that clears 3:1 against both backgrounds (either direction)
    for step in sorted(range(3, 98), key=lambda v: (abs(v - start), -v if dark else v)):
        rgb = tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(hue, step / 100.0, sat))
        if contrast(rgb, base_rgb) >= 3.0 and contrast(rgb, window_rgb) >= 3.0:
            return rgb
    raise ValueError('no block accent with contrast >= 3 for this palette')


def _vkey(version):
    """'0.7' / '0.7.0' / '1.x' -> sortable tuple (same order as roadmap.vkey)."""
    out = [(1, 0) if part == 'x' else (0, int(part)) for part in str(version).split('.')]
    return tuple(out + [(0, 0)] * (3 - len(out)))


def rail(suite_blocks, suite_rows, version=None):
    """[(block, [done actions], [planned rows])] in the plan's block order (Artem's order, 0..9).
    Done = a panel action exists for the row AND the row's version is shipped by this package version
    (the actions of a version exist from its base branch on, but stay greyed «в версии 0.x» until VERSION ships it:
    0.8 in 0.8.0, 0.9 in 0.9.0). A wip action (1.0, #1024) is never done here: it lives on the stage rail.
    Block pages list only rows whose id prefix is their block (roadmap.block_rows): the new 1.0 rows with a stage
    prefix (project., body., win., ...) are stage buttons only, so pages 0-9 stay as they were."""
    version = version or VERSION
    have = {}
    for a in ALL_ACTIONS:
        have.setdefault(row_of(a.id), []).append(a)
    by_id = {r['id']: r for r in suite_rows}
    for rid in have:
        if rid not in by_id:
            raise KeyError('plan row missing from agr-tools-suite.json: ' + rid)
    out = []
    for b in suite_blocks:
        done, planned = [], []
        for r in suite_rows:
            if r['block'] != b['id'] or r['id'].partition('.')[0] != b['id']:
                continue
            if any(a.wip for a in have.get(r['id'], ())):
                planned.append(r)
                continue
            if r['id'] in have and _vkey(r['version']) <= _vkey(version):
                done += have[r['id']]
            else:
                planned.append(r)
        out.append((b, done, planned))
    return out


# ---- 1.0 stage rail of «Путь» (#1024): big stage buttons, a second row of small buttons under each --------------
STAGE_STATUS = ('todo', 'work', 'done', 'blocked')  # == ProjectPassport.schema.json stages[].status
STAGE_STATUS_RU = {'todo': 'не начат', 'work': 'в работе', 'done': 'готов', 'blocked': 'заблокирован'}
Stage = namedtuple('Stage', 'id label icon big small status')


def stage_title(stage_id, label):
    """'0 Паспорт' .. '9 Сдача'; the agent stage (all stages) has no number: 'Агент'."""
    return label if stage_id == 'agent' else '{} {}'.format(stage_id, label)


def stage_statuses(stage_ids, passport=None):
    """{stage id: todo|work|done|blocked} from the project passport (contract K1). The passport reader is branch F;
    without a passport (None) every stage is `todo`. A passport is read fail-closed: no `stages` list, an unknown
    stage id or status, a stage twice or a stage missing is a ValueError naming it, never a guessed status."""
    stage_ids = list(stage_ids)
    if passport is None:
        return {sid: 'todo' for sid in stage_ids}
    stages = passport.get('stages') if isinstance(passport, dict) else None
    if not isinstance(stages, list):
        raise ValueError('passport without a stages list')
    out = {}
    for e in stages:
        sid = e.get('id') if isinstance(e, dict) else None
        if isinstance(sid, bool) or sid not in stage_ids:
            raise ValueError('passport names an unknown stage: ' + repr(sid))
        if sid in out:
            raise ValueError('passport lists stage {!r} twice'.format(sid))
        if e.get('status') not in STAGE_STATUS:
            raise ValueError('passport stage {!r} has an unknown status {!r}'.format(sid, e.get('status')))
        out[sid] = e['status']
    missing = [sid for sid in stage_ids if sid not in out]
    if missing:
        raise ValueError('passport lacks stages ' + repr(missing))
    return out


def stage_rail(suite, passport=None):
    """[Stage] in the plan's stage order: big = Action of the stage's big_button; small = Actions of the stage's
    rows minus the big button (plan order); status from stage_statuses(). Every stage row needs its Action."""
    stages = suite['stages']
    status = stage_statuses([s['id'] for s in stages], passport)
    out = []
    for s in stages:
        for rid in s['rows']:
            if rid not in BY_TOOL:
                raise KeyError('stage {!r} row without a panel action: {}'.format(s['id'], rid))
        small = tuple(BY_TOOL[rid] for rid in s['rows'] if rid != s['big_button'])
        out.append(Stage(s['id'], s['label_ru'], s['icon'], BY_TOOL[s['big_button']], small, status[s['id']]))
    return out


# ---- MAXScript entry points (generated; tests compare them with the committed files) -------------
import uuid as _uuid  # noqa: E402

MENU_ID = '0b5898ec-a68d-43ff-a95f-b60edcdd8b43'
UPGRADE_CODE = '{BA2C2E6E-54F9-402E-8875-3D616C9030FD}'
_NS = _uuid.UUID('f44d56e0-ac87-46b8-b5ff-e908e08e376b')
MACRO_TABLE = 647394  # ActionTable id of macroScripts (measured in Max, see PR)
CLASSIC_MACRO = 'AGRToolsClassic'
DOCUMENTED_GLOBALS = ('AGRToolsRoot', 'AGRToolsRegistered', 'AGRToolsDialog', 'AGRToolsRegisterMenus')


def stable_id(key):
    return str(_uuid.uuid5(_NS, key))


def product_code(version=VERSION):
    return '{' + stable_id('AGR Tools ' + version).upper() + '}'


def _ms(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


_CLASSIC = '''macroScript AGRToolsClassic category:"AGR Tools" tooltip:"AGR Tools (classic rollout)" buttonText:"AGR Tools (classic)"
(
    on execute do (
        global AGRToolsDialog
        try (destroyDialog AGRToolsDialog) catch ()
        rollout AGRToolsDialog "AGR Tools" width:360 (
{buttons}
            label info "JSON report in Listener; checks select offenders."
{handlers}
        )
        createDialog AGRToolsDialog
    )
)
'''


MENU_100 = 'Конвейер 1.0 (#1024)'  # released in 1.0.0 (R); was «— в работе»


def macro_100(a):
    """macroScript lines of a 1.0 stage button. Released: one press = runtime.edit_ui (preview, then apply on the
    same selection). wip: isEnabled false (greyed on toolbars/menus/quads) and execute only shows «в работе, #1024»
    (macros.run cannot reach an edit either)."""
    head = 'macroScript {} category:"{}" buttonText:"{}" tooltip:"{}" iconName:"{}"'.format(
        a.macro, CATEGORY, _ms(a.label), _ms(tooltip(a)), icon_name(a))
    if not a.wip and a.tool in FORM_100:  # 1.1: the press opens the parameter form of the panel
        return [head, '(on execute do python.Execute "agr_tools_runtime.form_ui(\'{}\')")'.format(a.tool)]
    if not a.wip:
        return [head, '(on execute do python.Execute "agr_tools_runtime.edit_ui(\'{}\')")'.format(a.tool)]
    return [head, '(', '    on isEnabled return false',
            '    on execute do messageBox "{}" title:"AGR Tools"'.format(_ms('{} ({}): {}'.format(a.label, a.tool,
                                                                                               WIP_TIP))),
            ')']


def macros_ms():
    lines = ['-- Generated by ui_model.macros_ms() (AGR Tools {}). Own implementation.'.format(VERSION),
             '-- Every action is a macroScript (toolbar/menu/hotkey) calling the Python runtime.']
    lines.append('macroScript {} category:"{}" buttonText:"AGR Tools" tooltip:"Открыть панель AGR Tools" '
                 'iconName:"{}tools"'.format(OPEN_MACRO, CATEGORY, ICON_PREFIX))
    lines.append('(on execute do (try (python.Execute "agr_tools_runtime.panel()") catch ('
                 'format "AGR_TOOLS_PANEL_FALLBACK %\\n" (getCurrentException()); '
                 'macros.run "{}" "{}")))'.format(CATEGORY, CLASSIC_MACRO))
    lines.append('macroScript {} category:"{}" buttonText:"{}" tooltip:"{}" iconName:"{}{}"'.format(
        DOCK_MACRO, CATEGORY, _ms(DOCK_LABEL), _ms(DOCK_TIP), ICON_PREFIX, DOCK_ICON))
    lines.append('(on execute do python.Execute "agr_tools_runtime.agent_dock()")')
    for a in ACTIONS:
        lines.append('macroScript {} category:"{}" buttonText:"{}" tooltip:"{}" iconName:"{}"'.format(
            a.macro, CATEGORY, _ms(a.label), _ms(tooltip(a)), icon_name(a)))
        lines.append('(on execute do python.Execute "agr_tools_runtime.ui(\'{}\')")'.format(a.tool))
    lines.append('-- 1.0 conveyor (#1024): stage buttons call runtime.edit_ui; while wip the macro is disabled and only '
                 'says so.')
    for a in ACTIONS_100:
        lines += macro_100(a)
    buttons = '\n'.join('            button b_{} "{}" width:340'.format(a.id, _ms(a.label)) for a in ACTIONS)
    handlers = '\n'.join('            on b_{} pressed do python.Execute "agr_tools_runtime.ui(\'{}\')"'.format(
        a.id, a.tool) for a in ACTIONS)
    return '\n'.join(lines) + '\n' + _CLASSIC.format(buttons=buttons, handlers=handlers)


def menu_ms():
    out = ['-- Generated by ui_model.menu_ms() (AGR Tools {}): main menu "AGR Tools", Max 2025+ CuiMenuManager.'.format(
        VERSION),
        '-- #cuiRegisterMenus fires at start-up and on every menu preset change. Only macroScripts are allowed.',
        'global AGRToolsRegisterMenus',
        'fn AGRToolsRegisterMenus = (',
        '    local mgr = callbacks.notificationParam()',
        '    local sub = mgr.mainMenuBar.CreateSubMenu "{}" "AGR Tools"'.format(MENU_ID),
        '    sub.CreateAction "{}" {} "{}`{}"'.format(stable_id(OPEN_MACRO), MACRO_TABLE, OPEN_MACRO, CATEGORY)]
    for i, (title, actions) in enumerate(sections()):
        out.append('    sub.CreateSeparator "{}"'.format(stable_id('sep' + str(i))))
        out.append('    local s{} = sub.CreateSubMenu "{}" "{}"'.format(i, stable_id('section' + str(i)), _ms(title)))
        for a in actions:
            out.append('    s{}.CreateAction "{}" {} "{}`{}"'.format(i, stable_id(a.macro), MACRO_TABLE, a.macro,
                                                                     CATEGORY))
    # 1.0 conveyor (#1024): one submenu, a sub-submenu per stage in plan order (wip macros show greyed)
    out.append('    sub.CreateSeparator "{}"'.format(stable_id('sep100')))
    out.append('    local c100 = sub.CreateSubMenu "{}" "{}"'.format(stable_id('section100'), _ms(MENU_100)))
    for i, (sid, label, _icon, rows_) in enumerate(STAGES_100):
        out.append('    local t{} = c100.CreateSubMenu "{}" "{}"'.format(i, stable_id('stage100_' + str(sid)),
                                                                      _ms(stage_title(sid, label))))
        for tool in rows_:
            a = BY_TOOL[tool]
            out.append('    t{}.CreateAction "{}" {} "{}`{}"'.format(i, stable_id(a.macro), MACRO_TABLE, a.macro,
                                                                     CATEGORY))
        if sid == 'agent':  # 1.1: the Claude dock next to the agent stage buttons
            out.append('    t{}.CreateAction "{}" {} "{}`{}"'.format(i, stable_id(DOCK_MACRO), MACRO_TABLE,
                                                                     DOCK_MACRO, CATEGORY))
    out += ['    ok',
            ')',
            'if (maxVersion())[1] >= 27000 do (',
            '    callbacks.removeScripts id:#agrTools',
            '    callbacks.addScript #cuiRegisterMenus AGRToolsRegisterMenus id:#agrTools',
            '    -- installed after the menus were built (MZP, post-start-up): re-apply the current preset once',
            '    local mgr = maxOps.GetICuiMenuMgr()',
            '    if mgr != undefined and (mgr.GetMenuById "{}") == undefined do'.format(MENU_ID),
            '        mgr.LoadConfiguration (mgr.GetCurrentConfiguration())',
            ')',
            '']
    return '\n'.join(out)
