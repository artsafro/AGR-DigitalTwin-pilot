"""new-case: AGR Tools test polygon, stdlib plus the shipped check cores. No pymxs.

The scene is synthetic. Expected codes for the read-only checks are produced by the same
cores the buttons call (suite_core, checks_core, texel, atlas, nudge, ucx build), so the
JSON in expected/ is a snapshot of that prediction. Live Max is a later run.
"""
import importlib.util
import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLY = Path(__file__).resolve().parent
PKG = ROOT / 'adapters' / 'max' / 'agr_tools'
SUITE_PATH = ROOT / 'docs' / 'plans' / 'agr-tools-suite.json'
EXPECTED = POLY / 'expected'

FBX_DIR = 'C:/x/test-polygon/export/'
CUBE_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
CUBE_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
          (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
QUAD_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
QUAD_T = [(0, 1, 2), (0, 2, 3)]
QUAD_UV = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

# Panel action id -> suite row id. Apply is the same row as its dry-run.
ACTION_ROW = {
    'xview': 'qa.xview', 'matid': 'qa.matid', 'names': 'qa.names', 'tris': 'qa.tris',
    'textures': 'tex.check', 'pivot': 'qa.pivot', 'nudge': 'udim.nudge', 'nudge_apply': 'udim.nudge',
    'atlas': 'atlas.npm', 'atlas_apply': 'atlas.npm', 'texel': 'udim.texel', 'ucx': 'ucx.build',
    'ucx_apply': 'ucx.build', 'cleanup': 'export.cleanup', 'apply': 'export.cleanup',
    'export': 'export.checked', 'geojson': 'qa.geojson', 'census': 'scene.census', 'units': 'scene.units',
    'perimeter_drop': 'model.perimeter_drop', 'material_type': 'tex.material_type', 'ucx_audit': 'ucx.audit',
    'sets_count': 'atlas.sets_count', 'fbx_split': 'qa.fbx_split', 'glass': 'qa.glass',
    'scene_hygiene': 'qa.scene_hygiene', 'xform': 'qa.xform', 'zero_area': 'qa.zero_area',
    'preflight': 'qa.preflight',
}
APPLY_STATUS = {'udim.nudge': 'pass', 'atlas.npm': 'pass', 'ucx.build': 'pass', 'export.cleanup': 'pass'}
PRIMARY = {}
for _action, _row in ACTION_ROW.items():
    PRIMARY.setdefault(_row, _action)

# Rectangles and captions are not part of a check. The runner drops them, and the
# offline cores never receive them. A later version extends the row by moving TOUR_LAST.
TOUR_LAST = '0.7'
BASE_LAYER = '_bases'
LABEL_LAYER = '_labels'
BASE_COLOURS = (
    (214, 69, 65),
    (230, 145, 40),
    (214, 196, 48),
    (62, 168, 94),
    (40, 168, 196),
    (66, 108, 214),
    (156, 92, 204),
)
# One station per button of a tour version. homes stand on that station (XY only;
# Z and the UCX overlap pair stay as authored). Empty homes: the specimen already
# stands on an earlier station, and the caption names it.
STATION_SPECS = (
    {'id': '0.1.1', 'version': '0.1', 'button': 'qa.matid',
     'homes': ('SM_Polygon_001_Main', 'SM_Polygon_010_Main')},
    {'id': '0.1.2', 'version': '0.1', 'button': 'qa.xview',
     'homes': ('SM_Polygon_009_Main',)},
    {'id': '0.1.3', 'version': '0.1', 'button': 'export.cleanup',
     'homes': ('SM_Polygon_Chan_Main',)},
    {'id': '0.2.1', 'version': '0.2', 'button': 'udim.nudge',
     'homes': ('SM_Polygon_NudgeOk_Main', 'SM_Polygon_NudgeBad_Main')},
    {'id': '0.2.2', 'version': '0.2', 'button': 'atlas.npm',
     'homes': ('SM_Polygon_AtlasOk_Main', 'SM_Polygon_AtlasBad_Main')},
    {'id': '0.3.1', 'version': '0.3', 'button': 'ucx.build', 'homes': ()},
    {'id': '0.3.2', 'version': '0.3', 'button': 'udim.texel',
     'homes': ('SM_Polygon_TexelOk_Main', 'SM_Polygon_TexelBad_Main')},
    {'id': '0.4.1', 'version': '0.4', 'button': 'export.checked', 'homes': ()},
    {'id': '0.5.1', 'version': '0.5', 'button': 'tex.check',
     'homes': ('SM_Polygon_007_Main', 'SM_Polygon_018_Main', 'SM_Polygon_019_Main',
               'SM_VeronaBit_Main')},
    {'id': '0.5.2', 'version': '0.5', 'button': 'qa.geojson', 'homes': ()},
    {'id': '0.5.3', 'version': '0.5', 'button': 'qa.names', 'homes': ('Bad Name',)},
    {'id': '0.5.4', 'version': '0.5', 'button': 'qa.pivot',
     'homes': ('SM_Verona_Main', 'SM_Verona_Ground')},
    {'id': '0.5.5', 'version': '0.5', 'button': 'qa.tris', 'homes': ()},
    {'id': '0.7.1', 'version': '0.7', 'button': 'scene.census', 'homes': ()},
    {'id': '0.7.2', 'version': '0.7', 'button': 'scene.units', 'homes': ()},
    {'id': '0.7.3', 'version': '0.7', 'button': 'model.perimeter_drop',
     'homes': ('SM_Polygon_004_Main', 'SM_Polygon_005_Main', 'SM_Polygon_Ground',
               'SM_Polygon_Patch_Ground')},
    {'id': '0.7.4', 'version': '0.7', 'button': 'tex.material_type',
     'homes': ('SM_Polygon_020_Main',)},
    {'id': '0.7.5', 'version': '0.7', 'button': 'ucx.audit', 'cluster': True,
     'homes': ('UCX_SM_Polygon_001_Main_001', 'UCX_SM_Polygon_001_Main_002',
               'UCX_SM_Polygon_001_Main_003', 'UCX bad',
               'UCX_SM_Polygon_001_Main_004', 'UCX_SM_Polygon_001_Main_005')},
    {'id': '0.7.6', 'version': '0.7', 'button': 'atlas.sets_count',
     'homes': ('SM_Polygon_013_Main',)},
    {'id': '0.7.7', 'version': '0.7', 'button': 'qa.fbx_split',
     'homes': ('SM_Polygon_001_GroundEl', 'SM_Polygon_001_Flora')},
    {'id': '0.7.8', 'version': '0.7', 'button': 'qa.glass',
     'homes': ('SM_Polygon_001_MainGlass', 'SM_Polygon_002_MainGlass', 'SM_Polygon_012_Main')},
    {'id': '0.7.9', 'version': '0.7', 'button': 'qa.preflight', 'homes': ()},
    {'id': '0.7.10', 'version': '0.7', 'button': 'qa.scene_hygiene',
     'homes': ('SM_Polygon_014_Main', 'Helper_Polygon', 'SM_Polygon_015_Main',
               'SM_Polygon_016_Main', 'SM_Polygon_017_Main', 'Camera_Polygon',
               'Light_Polygon', 'Spline_Polygon')},
    {'id': '0.7.11', 'version': '0.7', 'button': 'qa.xform',
     'homes': ('SM_Polygon_008_Main',)},
    {'id': '0.7.12', 'version': '0.7', 'button': 'qa.zero_area',
     'homes': ('SM_Polygon_011_Main',)},
)

NOT_SHIPPED = (
    'Кнопки ещё нет в AGR Tools 0.7: в панели её нет, объекты полигона и эта запись '
    'появляются в том же изменении, что и сама кнопка.'
)
NO_CLEANUP_PASS = (
    'Объекта PASS нет: у каждого объекта полигона есть AGR_TEST (и часто AGR_ZERO_M). '
    'Очистка считает такие строки пользовательскими свойствами и даёт clear_user_defined_lines. '
    'Пустой буфер свойств не может одновременно нести AGR_TEST. Прогон «Очистка → копии» '
    'ждёт status pass уже на копиях, где эти строки сняты.'
)
NO_EXPORT_PASS = (
    'Объекта PASS нет: экспорт с проверкой останавливается на воротах очистки, потому что '
    'AGR_TEST не входит в список свойств, которые экспорт прячет. Код находки — cleanup. '
    'Второе нажатие пишет FBX только в новый путь; раннер его не делает.'
)
NO_ATLAS_PASS = (
    'Объекта PASS нет. Пробная сборка атласа всегда сдвигает остров в ячейку с отступом 8 px '
    '(код atlas_cell), и повторный pack тех же UV снова их двигает. Стабильный остров, который '
    'кнопка оставила бы без находки, из этого ядра не получается. Объект FAIL — SM_Polygon_AtlasBad_Main.'
)
NO_UCX_FAIL = (
    'Объекта FAIL с кодом находки нет. Пробный UCX на ящике (и даже на открытом меше, который '
    'ядро замыкает в выпуклую оболочку) даёт пустые findings. Находка at_threshold появляется '
    'только при ровно 15000 треугольниках коллизии — это уже не маленький синтетический кусок. '
    'Пустой меш и нечисло — ошибка ValueError, не pass.'
)


def _load(name, mod):
    if mod in sys.modules and getattr(sys.modules[mod], '__file__', None):
        return sys.modules[mod]
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod] = module
    spec.loader.exec_module(module)
    return module


def cores():
    checks = _load('checks_core.py', 'agr_tools_checks_core')
    suite = _load('suite_core.py', 'agr_tools_suite_core')
    texel = _load('texel_core.py', 'agr_tools_texel')
    atlas = _load('atlas_core.py', 'agr_tools_atlas')
    nudge = _load_nudge()
    ucx = _load('ucx_core.py', 'agr_tools_ucx')
    from twinqa.geometry import ucx_audit as audit
    return checks, suite, texel, atlas, nudge, ucx, audit


def _load_nudge():
    """The button calls the packaged slice name; the source of that slice is dt_ai.geometry.uv_nudge."""
    import dt_ai.geometry.uv_nudge as nudge
    return nudge


def suite_doc():
    return json.loads(SUITE_PATH.read_text(encoding='utf-8'))


def suite_rows():
    return suite_doc()['rows']


def tour_versions():
    """Bases 0.1 .. TOUR_LAST, in plan order. The next AGR Tools version adds its base."""
    found = []
    for item in suite_doc()['versions']:
        found.append(item)
        if item['version'] == TOUR_LAST:
            return found
    raise RuntimeError('tour end {} is not in agr-tools-suite.json'.format(TOUR_LAST))


def bases():
    out = []
    for index, item in enumerate(tour_versions()):
        if index >= len(BASE_COLOURS):
            raise RuntimeError('add a top-view colour for base ' + item['version'])
        out.append({
            'version': item['version'], 'title': item['title_ru'],
            'colour': list(BASE_COLOURS[index]), 'buttons': list(item['rows']),
        })
    return out


def stations():
    """Stations of the tour. Button versions come from agr-tools-suite.json."""
    version_of = {row['id']: row['version'] for row in suite_rows()}
    built = {base['version'] for base in bases()}
    seen = set()
    homes = {}
    out = []
    for spec in STATION_SPECS:
        button = spec['button']
        if button not in version_of:
            raise RuntimeError('station button is not in the suite: ' + button)
        if version_of[button] != spec['version']:
            raise RuntimeError('{} is {} in the suite, station says {}'.format(
                button, version_of[button], spec['version']))
        if spec['version'] not in built:
            raise RuntimeError('station {} has no base'.format(spec['id']))
        if spec['id'] in seen:
            raise RuntimeError('duplicate station ' + spec['id'])
        if not spec['id'].startswith(spec['version'] + '.'):
            raise RuntimeError('station id {} is not under {}'.format(spec['id'], spec['version']))
        tail = spec['id'][len(spec['version']) + 1:]
        if not tail.isdigit():
            raise RuntimeError('station id tail is not a number: ' + spec['id'])
        seen.add(spec['id'])
        for name in spec['homes']:
            if name in homes:
                raise RuntimeError('{} is on {} and {}'.format(name, homes[name], spec['id']))
            homes[name] = spec['id']
        out.append({
            'id': spec['id'], 'version': spec['version'], 'base': spec['version'],
            'button': button, 'homes': list(spec['homes']), 'cluster': bool(spec.get('cluster')),
        })
    for base in bases():
        for button in base['buttons']:
            if not any(item['button'] == button for item in out):
                raise RuntimeError('button {} on base {} has no station'.format(button, base['version']))
    return out


def excluded_name(name):
    text = str(name)
    return text.startswith('_base_') or text.startswith('_label_')


def excluded_node(obj):
    return excluded_name(obj.get('name', '')) or obj.get('layer') in (BASE_LAYER, LABEL_LAYER)


def _version_token(version):
    return version.replace('.', '_')


def fbx_path(stem):
    return FBX_DIR + stem


def _shift(verts, pos, size):
    sx, sy, sz = size
    x, y, z = pos
    out = []
    for a, b, c in verts:
        out.append((x + (a - 0.5) * sx, y + (b - 0.5) * sy, z + c * sz))
    return out


def mesh_of(obj):
    kind = obj['mesh']
    if kind == 'empty':
        return [], []
    if kind == 'quad':
        return _shift(QUAD_V, obj['pos'], obj['size']), list(QUAD_T)
    verts = _shift(CUBE_V, obj['pos'], obj['size'])
    tris = list(CUBE_T)
    if kind == 'open':
        tris = tris[:-2]
    elif kind == 'overlap':
        verts[1] = verts[0]
    elif kind == 'zero':
        # Distinct indices: Max drops a face that repeats one vertex. The span stays
        # under the 0.01 mm zero-edge limit and above object-space float32 noise.
        span = 5e-6
        origin = verts[0]
        verts = list(verts) + [
            origin,
            (origin[0] + span, origin[1], origin[2]),
            (origin[0] + span * 0.5, origin[1] + span * 1e-4, origin[2]),
        ]
        tris = list(tris) + [(8, 9, 10)]
    return verts, tris


def _std(name, opacity=1.0, maps=None, missing=None, cls='Standardmaterial'):
    return {'name': name, 'cls': cls, 'maps': list(maps or []), 'missing': list(missing or []),
            'opacity': opacity}


def materials_of(obj):
    mode = obj.get('mat', 'std')
    name = obj.get('mat_name', 'M_Polygon_001_Main_1')
    if mode == 'none':
        return []
    if mode == 'glass':
        return [_std(name, opacity=obj.get('opacity', 0.5))]
    if mode == 'ray':
        return [_std(name, cls='RaytraceMaterial', opacity=None)]
    if mode == 'missing':
        path = obj['map_path']
        return [_std(name, maps=[path], missing=[path])]
    if mode == 'many':
        return [_std('M_{}{}_001_Main_1'.format(chr(ord('A') + i // 26), chr(ord('A') + i % 26)))
                for i in range(41)]
    return [_std(name)]


def _obj(name, role, zone, pos, size=(2, 2, 2), mesh='box', fbx='0101_Polygon_01.fbx', **kw):
    item = {
        'name': name, 'role': role, 'scene': kw.pop('scene', 'polygon_all'), 'zone': zone,
        'layer': '', 'base': '', 'station': '', 'pos': list(pos), 'size': list(size), 'mesh': mesh, 'fbx': fbx,
        'mat': 'std', 'zero': 0.0, 'superclass': 'geometry', 'cls': 'Editable_Poly',
        'scale': [1.0, 1.0, 1.0], 'parent': None, 'children': 0, 'animated': False,
        'modifiers': [], 'opacity': 1.0,
    }
    item.update(kw)
    return item


def scene_objects():
    """Every node the builder creates. Synthetic; the bench is a box, not the #790 asset."""
    p = 'polygon_all'
    g = '0101_Polygon_Ground.fbx'
    rows = [
        _obj('SM_Polygon_001_Main', 'Main', 'model', (40, 0, -2), (8, 6, 6), mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_001_MainGlass', 'MainGlass', 'model', (40, 8, 1), (3, 0.1, 2.2), mat='glass',
             opacity=0.5, mat_name='M_Polygon_001_MainGlass_1'),
        _obj('SM_Polygon_002_MainGlass', 'MainGlass', 'model', (44, 8, 1), (1, 0.1, 1), mat='glass',
             opacity=0.3, mat_name='M_Polygon_002_MainGlass_1'),
        _obj('SM_Polygon_Ground', 'Ground', 'model', (40, 24, -3), (24, 16, 1), fbx=g,
             mat_name='M_Polygon_Ground_1'),
        _obj('SM_Polygon_Patch_Ground', 'Ground', 'model', (52, 24, -2), (2, 2, 1), fbx=g,
             mat_name='M_Polygon_Ground_1'),
        _obj('SM_Polygon_001_GroundEl', 'GroundEl', 'place', (240, 0, 0), (1.8, 0.5, 0.45), fbx=g,
             mat_name='M_Polygon_001_GroundEl_1'),
        _obj('SM_Polygon_001_Flora', 'Flora', 'place', (244, 0, 0), (1, 1, 3), fbx=g,
             mat_name='M_Polygon_001_Flora_1'),
        _obj('UCX_SM_Polygon_001_Main_001', 'UCX', 'ucx', (120, 0, -1), (4, 3, 3), mat='none'),
        _obj('UCX_SM_Polygon_001_Main_002', 'UCX', 'ucx', (128, 0, -1), (2, 2, 2), mesh='open', mat='none'),
        _obj('UCX_SM_Polygon_001_Main_003', 'UCX', 'ucx', (134, 0, -1), (2, 2, 2),
             mat_name='M_Polygon_001_Main_1'),
        _obj('UCX bad', 'UCX', 'ucx', (140, 0, -1), (2, 2, 2), mat='none'),
        _obj('UCX_SM_Polygon_001_Main_004', 'UCX', 'ucx', (146, 0, -1), (2, 2, 2), mat='none'),
        _obj('UCX_SM_Polygon_001_Main_005', 'UCX', 'ucx', (146.4, 0, -1), (2, 2, 2), mat='none'),
        _obj('SM_Polygon_004_Main', 'Main', 'qa', (280, 0, -0.4), mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_005_Main', 'Main', 'qa', (284, 0, -1), mat_name='M_Polygon_001_Main_1'),
        _obj('Bad Name', 'Main', 'qa', (288, 0, -2), mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_008_Main', 'Main', 'qa', (292, 0, -2), scale=[2.0, 2.0, 2.0],
             mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_009_Main', 'Main', 'qa', (296, 0, -2), mesh='overlap', mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_010_Main', 'Main', 'qa', (300, 0, -2), matid=1001, mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_011_Main', 'Main', 'qa', (304, 0, -2), mesh='zero', mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_012_Main', 'Main', 'qa', (308, 0, -2), mat='glass', opacity=0.5,
             mat_name='M_Polygon_012_MainGlass_1'),
        _obj('SM_Polygon_007_Main', 'Main', 'tex', (80, 0, -2), mat='missing',
             mat_name='M_Polygon_007_Main_1', map_path='C:/x/test-polygon/missing/T_Polygon_007_Main_d_1.png'),
        _obj('SM_Polygon_018_Main', 'Main', 'tex', (86, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_018_Main_1', tex='bad_size'),
        _obj('SM_Polygon_019_Main', 'Main', 'tex', (90, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_019_Main_1', tex='alpha'),
        _obj('SM_Polygon_020_Main', 'Main', 'tex', (94, 0, -2), mat='ray', mat_name='M_Polygon_020_Main_1'),
        _obj('SM_Polygon_013_Main', 'Main', 'tex', (100, 0, -2), fbx='0101_Polygon_02.fbx', mat='many'),
        _obj('SM_Polygon_014_Main', 'Main', 'qa', (312, 4, -2), parent='Helper_Polygon',
             mat_name='M_Polygon_001_Main_1'),
        _obj('Helper_Polygon', 'helper', 'scene', (0, 4, 0), mesh='empty', fbx=None, mat='none',
             superclass='helper', cls='Dummy', children=1),
        _obj('SM_Polygon_015_Main', 'Main', 'qa', (316, 0, -2), modifiers=['Bend'],
             mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_016_Main', 'Main', 'qa', (320, 0, -2), animated=True, mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_017_Main', 'Main', 'qa', (324, 0, -2), mesh='empty', mat_name='M_Polygon_001_Main_1'),
        _obj('SM_Polygon_NudgeOk_Main', 'Main', 'udim', (160, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_NudgeOk_Main_1', uv_periods='none'),
        _obj('SM_Polygon_NudgeBad_Main', 'Main', 'udim', (164, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_NudgeBad_Main_1', uv_periods='1,1', uv_shift=1.0),
        _obj('SM_Polygon_AtlasOk_Main', 'Main', 'atlas', (200, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_AtlasOk_Main_1', atlas='stable'),
        _obj('SM_Polygon_AtlasBad_Main', 'Main', 'atlas', (204, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_AtlasBad_Main_1', atlas='move'),
        _obj('SM_Polygon_TexelOk_Main', 'Main', 'udim', (168, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_TexelOk_Main_1', texel_px=20),
        _obj('SM_Polygon_TexelBad_Main', 'Main', 'udim', (172, 0, -2), (1, 1, 0), mesh='quad',
             mat_name='M_Polygon_TexelBad_Main_1', texel_px=2048),
        _obj('SM_Polygon_Chan_Main', 'Main', 'export', (320, 8, -2), mat_name='M_Polygon_001_Main_1',
             extra_channel=True),
        _obj('Camera_Polygon', 'camera', 'scene', (0, 8, 2), mesh='empty', fbx=None, mat='none',
             superclass='camera', cls='Freecamera'),
        _obj('Light_Polygon', 'light', 'scene', (4, 8, 2), mesh='empty', fbx=None, mat='none',
             superclass='light', cls='Omnilight'),
        _obj('Spline_Polygon', 'shape', 'scene', (8, 8, 0), mesh='empty', fbx=None, mat='none',
             superclass='shape', cls='SplineShape'),
    ]
    rows.append(_obj('SM_Polygon_001_Main', 'Main', 'model', (0, 0, -2), scene='vpm', fbx='SM_Verona.fbx',
                     mat_name='M_Verona_Main_1', pivot=[0, 0, 0]))
    # The VPM pass mesh is SM_Verona_Main; the name above collided. Fix below.
    rows[-1]['name'] = 'SM_Verona_Main'
    rows.append(_obj('SM_Verona_Ground', 'Ground', 'model', (6, 0, 0.5), scene='vpm',
                     fbx='SM_Verona_Ground.fbx', mat_name='M_Verona_Ground_1', pivot=[6, 0, 0.5]))
    rows.append(_obj('SM_VeronaBit_Main', 'Main', 'tex', (3, 0, 0), scene='vpm', fbx='SM_Verona.fbx',
                     mat_name='M_VeronaBit_Main_1', pivot=[3, 0, 0], tex='bit16'))
    good = next(o for o in rows if o['name'] == 'SM_Polygon_001_Main' and o['scene'] == p)
    good['tex'] = 'ok256'
    _apply_layout(rows)
    return rows


def _place_cluster(members, origin_x, origin_y):
    """Pack a station in a row. The two overlapping UCX hulls stay 0.4 m apart."""
    placed = {}
    cursor = origin_x
    for obj in members:
        z = obj['pos'][2]
        if obj['name'] == 'UCX_SM_Polygon_001_Main_005' and 'UCX_SM_Polygon_001_Main_004' in placed:
            anchor = placed['UCX_SM_Polygon_001_Main_004']
            obj['pos'] = [anchor[0] + 0.4, anchor[1], z]
        else:
            obj['pos'] = [cursor, origin_y, z]
            placed[obj['name']] = obj['pos']
            cursor += 6.0
    if not members:
        return 8.0
    return max(obj['pos'][0] for obj in members) - origin_x + 6.0


def _apply_layout(rows):
    """Put polygon_all nodes on version bases. Z is kept. Variant scenes keep their XY."""
    known = {obj['name'] for obj in rows}
    home = {}
    for spec in stations():
        for name in spec['homes']:
            if name not in known:
                raise RuntimeError('station {} names missing object {}'.format(spec['id'], name))
            home[name] = spec
    for obj in rows:
        spec = home.get(obj['name'])
        if spec is None:
            if obj['scene'] == 'polygon_all':
                raise RuntimeError('no station for ' + obj['name'])
            continue
        obj['station'] = spec['id']
        obj['base'] = spec['version']
        obj['zone'] = spec['version']
        obj['layer'] = 'База ' + spec['version']
    by_name = {}
    for obj in rows:
        if obj['scene'] == 'polygon_all':
            by_name.setdefault(obj['name'], []).append(obj)
    x = 0.0
    gap = 14.0
    laid = []
    for base in bases():
        specs = [spec for spec in stations() if spec['version'] == base['version']]
        cursor = x + 6.0
        y_top = 8.0
        label_ys = []
        placed_stations = []
        for spec in specs:
            members = []
            for name in spec['homes']:
                members.extend(obj for obj in by_name.get(name, []) if obj['scene'] == 'polygon_all')
            if spec['cluster'] and members:
                width = _place_cluster(members, cursor, 2.0)
            else:
                for index, obj in enumerate(members):
                    obj['pos'] = [cursor, 2.0 + index * 7.0, obj['pos'][2]]
                width = 8.0
            if members:
                south = min(obj['pos'][1] - obj['size'][1] / 2.0 for obj in members)
                north = max(obj['pos'][1] + obj['size'][1] / 2.0 for obj in members)
                label_pos = [members[0]['pos'][0], south - 1.4, 0.05]
                y_top = max(y_top, north)
            else:
                label_pos = [cursor, 2.0, 0.05]
                y_top = max(y_top, 6.0)
            label_ys.append(label_pos[1])
            placed_stations.append({'id': spec['id'], 'button': spec['button'], 'label_pos': label_pos})
            cursor += max(width, 8.0) + 4.0
        if not specs:
            cursor = x + 22.0
            y_top = 10.0
        minx, maxx = x, cursor + 2.0
        low = min(label_ys) if label_ys else -2.0
        miny, maxy = min(-4.0, low - 1.5), y_top + 3.0
        laid.append({
            'version': base['version'], 'title': base['title'], 'colour': list(base['colour']),
            'buttons': list(base['buttons']),
            'rect_pos': [(minx + maxx) / 2.0, (miny + maxy) / 2.0, -0.04],
            'rect_size': [maxx - minx, maxy - miny, 0.04],
            'label_pos': [minx + 1.0, miny + 0.8, 0.05],
            'stations': placed_stations,
        })
        x = maxx + gap
    return laid


def _layout():
    return _apply_layout(scene_objects())


def _bbox(verts):
    if not verts:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    return (tuple(lo), tuple(hi))


def suite_rows_for(scene):
    rows = []
    for obj in scene_objects():
        if obj['scene'] != scene or scene == 'empty' or excluded_node(obj):
            continue
        verts, tris = mesh_of(obj)
        geo = obj['superclass'] == 'geometry'
        rows.append({
            'key': len(rows) + 1, 'name': obj['name'],
            'fbx': fbx_path(obj['fbx']) if obj.get('fbx') else None,
            'superclass': obj['superclass'], 'cls': obj['cls'],
            'faces': len(tris), 'verts': len(verts),
            'materials': materials_of(obj) if geo else [],
            'parent': obj['parent'], 'children': obj['children'], 'group': False,
            'animated': obj['animated'], 'modifiers': list(obj['modifiers']),
            'layer': obj['layer'], 'scale': tuple(obj['scale']), 'rotation': (0.0, 0.0, 0.0, 1.0),
            'mirror': False, 'bbox': _bbox(verts), 'instances': 1,
            'zero_m': obj['zero'] if geo else None, 'roof_set': False,
            'mesh': {'verts': verts, 'tris': tris},
        })
    return rows


def _entry(name, scene, codes, expect=None):
    codes = sorted(set(codes))
    if expect is None:
        expect = 'fail' if codes else 'pass'
    return {'name': name, 'scene': scene, 'expect': expect, 'codes': codes}


def _mark_known(docs, button, scene, name, bug):
    """Record a live tool bug on one expected row. expect/codes stay the contract."""
    hit = next(obj for obj in docs[button]['objects']
               if obj['scene'] == scene and obj['name'] == name)
    hit['known_bug'] = {
        'id': bug['id'],
        'got_expect': bug['got_expect'],
        'got_codes': sorted(bug.get('got_codes') or []),
    }


def _from_found(scene, rows, found):
    out = []
    for row in rows:
        codes = [item[0] for item in found.get(row['key'], [])]
        out.append(_entry(row['name'], scene, codes))
    return out


def _tool_docs(button, objects, reason=''):
    return {
        'schema': 1, 'button': button, 'tool': PRIMARY.get(button),
        'version': None, 'shipped': button in PRIMARY, 'select': 'named',
        'reason': reason, 'apply_status': APPLY_STATUS.get(button), 'objects': objects,
    }


def _png(width, height, depth=8, color_type=2):
    """Tiny synthetic PNG. color_type 2 = RGB, 6 = RGBA. No ancillary chunks."""
    samples = {2: 3, 6: 4}[color_type]
    if depth == 8:
        pixel = bytes([180, 160, 140] + ([255] if samples == 4 else []))
        row = b'\x00' + pixel * width
    elif depth == 16 and color_type == 2:
        pixel = b''.join(struct.pack('>H', v) for v in (180, 160, 140))
        row = b'\x00' + pixel * width
    else:
        raise ValueError('unsupported png')
    raw = row * height

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', width, height, depth, color_type, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


TEXTURES = {
    'ok256': ('T_Polygon_001_Main_d_1.png', _png(256, 256)),
    'bad_size': ('T_Polygon_018_Main_d_1.png', _png(100, 50)),
    'alpha': ('T_Polygon_019_Main_d_1.png', _png(256, 256, color_type=6)),
    'bit16': ('T_VeronaBit_Main_Diffuse_1.1001.png', _png(256, 256, depth=16)),
}


def _texture_rows(scene, checks):
    rows = []
    for obj in scene_objects():
        if obj['scene'] != scene or obj['superclass'] != 'geometry' or excluded_node(obj):
            continue
        verts, tris = mesh_of(obj)
        maps = []
        if obj.get('tex') in TEXTURES:
            filename, data = TEXTURES[obj['tex']]
            maps.append((filename, data))
        elif obj.get('mat') == 'missing':
            maps.append((obj['map_path'], None))
        uvs = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        faces = [(1, [0, 1, 2]), (2, [0, 2, 3])] if tris else []
        rows.append({'key': len(rows) + 1, 'name': obj['name'],
                     'fbx': fbx_path(obj['fbx']) if obj.get('fbx') else None,
                     'maps': maps, 'uv': (lambda uvs=uvs, faces=faces: (uvs, faces))})
    return rows


def _name_rows(scene):
    rows = []
    for obj in scene_objects():
        if obj['scene'] != scene or obj['superclass'] != 'geometry' or excluded_node(obj):
            continue
        mats = [m['name'] for m in materials_of(obj)]
        maps = []
        if obj.get('tex') in TEXTURES:
            maps.append(TEXTURES[obj['tex']][0])
        elif obj.get('mat') == 'missing':
            maps.append(obj['map_path'])
        rows.append({'key': len(rows) + 1, 'name': obj['name'],
                     'fbx': fbx_path(obj['fbx']) if obj.get('fbx') else None,
                     'materials': mats, 'maps': maps})
    return rows


def _tri_rows(scene):
    rows = []
    for obj in scene_objects():
        if obj['scene'] != scene or obj['superclass'] != 'geometry' or excluded_node(obj):
            continue
        _v, tris = mesh_of(obj)
        item = {'key': len(rows) + 1, 'name': obj['name'],
                'fbx': fbx_path(obj['fbx']) if obj.get('fbx') else None,
                'triangles': len(tris)}
        rows.append(item)
    return rows


def _pivot_rows(scene):
    rows = []
    for obj in scene_objects():
        if obj['scene'] != scene or obj['superclass'] != 'geometry' or excluded_node(obj):
            continue
        pivot = tuple(obj['pivot']) if obj.get('pivot') is not None else (obj['pos'][0], obj['pos'][1], obj['pos'][2])
        rows.append({'key': len(rows) + 1, 'name': obj['name'],
                     'fbx': fbx_path(obj['fbx']) if obj.get('fbx') else None, 'pivot': pivot})
    return rows


def _quad_uv(obj):
    shift = float(obj.get('uv_shift') or 0.0)
    return [(u + shift, v) for u, v in QUAD_UV]


def _atlas_uvs():
    _checks, _suite, _texel, atlas, _nudge, _ucx, _audit = cores()
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    uvs = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]
    mats = {'M_Polygon_AtlasOk_Main_1': {'dissolve': 1.0, 'color': (180, 160, 140)}}
    laid = atlas.pack(verts, uvs, [[0, 1, 2], [0, 2, 3]], [[0, 1, 2], [0, 2, 3]],
                      ['M_Polygon_AtlasOk_Main_1', 'M_Polygon_AtlasOk_Main_1'], mats,
                      mode='oks', size=1024, pad=8, unit_m=1.0)
    return laid['uvs']


def predict_native():
    """Buttons whose result is a mesh finding the cores can score without Max."""
    checks, _suite, texel, atlas, nudge, ucx, _audit = cores()
    out = {}
    nudge_ok = next(o for o in scene_objects() if o['name'] == 'SM_Polygon_NudgeOk_Main')
    nudge_bad = next(o for o in scene_objects() if o['name'] == 'SM_Polygon_NudgeBad_Main')
    objects = []
    for obj, period in ((nudge_ok, None), (nudge_bad, (1.0, 1.0))):
        uv = _quad_uv(obj)
        result = nudge.nudge_repeating_islands(uv, [[0, 1, 2], [0, 2, 3]], [obj['mat_name'], obj['mat_name']],
                                               {obj['mat_name']: period}, target_tile=1001)
        codes = ['tile_move'] if any(island['steps'] != (0, 0) for island in result.islands) else []
        objects.append(_entry(obj['name'], 'polygon_all', codes))
    out['udim.nudge'] = objects

    stable = _atlas_uvs()
    bad_uv = [(u + 0.2, v + 0.2) for u, v in [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]]
    atlas_objects = []
    for name, uv in (('SM_Polygon_AtlasOk_Main', stable), ('SM_Polygon_AtlasBad_Main', bad_uv)):
        mat = name.replace('SM_', 'M_') + '_1' if False else {
            'SM_Polygon_AtlasOk_Main': 'M_Polygon_AtlasOk_Main_1',
            'SM_Polygon_AtlasBad_Main': 'M_Polygon_AtlasBad_Main_1',
        }[name]
        mats = {mat: {'dissolve': 1.0, 'color': (180, 160, 140)}}
        laid = atlas.pack([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], uv,
                          [[0, 1, 2], [0, 2, 3]], [[0, 1, 2], [0, 2, 3]], [mat, mat], mats,
                          mode='oks', size=1024, pad=8, unit_m=1.0)
        moved = laid['uvs'] != [tuple(p) for p in uv] and laid['uvs'] != list(uv)
        # pack returns a list; compare component-wise
        same = all(abs(a - b) < 1e-9 and abs(c - d) < 1e-9 for (a, c), (b, d) in zip(laid['uvs'], uv))
        atlas_objects.append(_entry(name, 'polygon_all', [] if same else ['atlas_cell']))
    out['atlas.npm'] = atlas_objects

    texel_objects = []
    for name, px in (('SM_Polygon_TexelOk_Main', 20), ('SM_Polygon_TexelBad_Main', 2048)):
        payload = {
            'profile': 'NPM',
            'materials': [{'name': name.replace('SM_', 'M_') + '_1', 'map_px': px}],
            'faces': [{'id': '1', 'mesh': name, 'material': name.replace('SM_', 'M_') + '_1',
                       'xyz': [(0, 0, 0), (1, 0, 0), (1, 1, 0)], 'uv': [(0, 0), (1, 0), (1, 1)]},
                      {'id': '2', 'mesh': name, 'material': name.replace('SM_', 'M_') + '_1',
                       'xyz': [(0, 0, 0), (1, 1, 0), (0, 1, 0)], 'uv': [(0, 0), (1, 1), (0, 1)]}],
        }
        # material names are the catalog mat_name, not a rewrite
        mat = next(o['mat_name'] for o in scene_objects() if o['name'] == name)
        payload['materials'][0]['name'] = mat
        for face in payload['faces']:
            face['material'] = mat
        summary = texel.summarize(payload)
        codes = []
        if any(item['status'] != 'pass' for item in summary['faces']):
            codes.append('texel_outside')
        if summary['dropped']:
            codes.append('texel_dropped')
        texel_objects.append(_entry(name, 'polygon_all', codes))
    out['udim.texel'] = texel_objects

    box = next(o for o in scene_objects() if o['name'] == 'SM_Polygon_001_Main' and o['scene'] == 'polygon_all')
    verts, tris = mesh_of(box)
    built = ucx.build(verts, tris, mesh=box['name'])
    out['ucx.build'] = [_entry(box['name'], 'polygon_all', [f['code'] for f in built['findings']])]
    return out


def _geojson_bytes():
    import base64
    from io import BytesIO
    from PIL import Image
    keys = ['address', 'okrug', 'rajon', 'name', 'developer', 'designer', 'cadNum', 'FNO_code', 'FNO_name',
            'ZU_area', 'h_relief', 'h_otn', 'h_abs', 's_obsh', 's_naz', 's_podz', 'spp_gns', 'act_AGR',
            'imageBase64', 'other']
    buf = BytesIO()
    Image.new('RGB', (256, 256), (180, 160, 140)).save(buf, format='JPEG', quality=30)
    props = {key: 'synthetic' for key in keys}
    props['FNO_code'] = '123456'
    props['imageBase64'] = base64.b64encode(buf.getvalue()).decode('ascii')
    valid = {'type': 'FeatureCollection', 'features': [{
        'type': 'ObjectFeature', 'geometry': {'type': 'Point', 'coordinates': [12345.678, 6789.012]},
        'properties': props, 'Glasses': []}]}
    return json.dumps(valid, ensure_ascii=False, indent=1).encode('utf-8')


def predict_all():
    checks, suite, _texel, _atlas, _nudge, _ucx, audit = cores()
    versions = {r['id']: r['version'] for r in suite_rows()}
    docs = {row['id']: _tool_docs(row['id'], [], NOT_SHIPPED if row['id'] not in PRIMARY else '')
            for row in suite_rows()}
    for button, doc in docs.items():
        doc['version'] = versions[button]

    by_scene = {}
    for scene in ('polygon_all', 'vpm'):
        rows = suite_rows_for(scene)
        by_scene[scene] = rows
        for tool, button in suite.PLAN_ROW.items():
            if tool == 'units':
                continue
            found, _d, _s = suite.run(tool, rows, audit)
            docs[button]['objects'].extend(_from_found(scene, rows, found))

    good_units = {'unit_type': 'meters', 'unit_scale': 1.0, 'file_in_gamma': 1.0, 'file_out_gamma': 1.0}
    cm_units = dict(good_units, unit_type='centimeters')
    for scene, payload in (('polygon_all', good_units), ('cm_units', cm_units)):
        findings = suite.units(payload)
        codes = [f['name'] for f in findings if f['status'] != 'pass']
        docs['scene.units']['objects'].append(_entry('__scene__', scene, codes))
    docs['scene.census']['objects'].append(
        {'name': '__scene__', 'scene': 'empty', 'expect': 'error', 'codes': ['empty target set']})

    for scene, maker, fn in (
            ('polygon_all', _name_rows, checks.names_scene),
            ('vpm', _name_rows, checks.names_scene)):
        rows = maker(scene)
        docs['qa.names']['objects'].extend(_from_found(scene, rows, fn(rows)))
    for scene in ('polygon_all', 'vpm'):
        rows = _tri_rows(scene)
        found, _table = checks.triangle_limits(rows)
        docs['qa.tris']['objects'].extend(_from_found(scene, rows, found))
        rows = _texture_rows(scene, checks)
        found, _dropped = checks.textures_scene(rows)
        docs['tex.check']['objects'].extend(_from_found(scene, rows, found))
        rows = _pivot_rows(scene)
        found, _dropped = checks.pivot_findings(rows)
        docs['qa.pivot']['objects'].extend(_from_found(scene, rows, found))

    from twinqa.geojson import geojson_findings
    from twinqa.profiles import load_profiles
    profile = load_profiles().vpm
    valid = _geojson_bytes()
    broken_syntax = b'{this is not json'
    broken_schema = b'{"type": "Feature", "features": []}\n'
    for name, raw in (('valid_oks.geojson', valid), ('broken_syntax.geojson', broken_syntax),
                      ('broken_schema.geojson', broken_schema)):
        findings = geojson_findings(raw, profile, ground=False, glass_names=None)
        codes = sorted({f.name for f in findings if f.status != 'pass'})
        docs['qa.geojson']['objects'].append(_entry(name, 'polygon_all', codes))

    native = predict_native()
    for button, objects in native.items():
        docs[button]['objects'] = objects

    docs['qa.xview']['objects'] = [
        _entry('SM_Polygon_001_Main', 'polygon_all', []),
        _entry('SM_Polygon_009_Main', 'polygon_all', ['overlap_faces', 'overlap_vertices']),
    ]
    docs['qa.matid']['objects'] = [
        _entry('SM_Polygon_001_Main', 'polygon_all', []),
        _entry('SM_Polygon_010_Main', 'polygon_all', ['udim_id']),
    ]
    docs['export.cleanup']['objects'] = [
        _entry('SM_Polygon_001_Main', 'polygon_all', ['clear_user_defined_lines']),
        _entry('SM_Polygon_Chan_Main', 'polygon_all', ['clear_user_defined_lines', 'delete_map_channels']),
    ]
    docs['export.cleanup']['reason'] = NO_CLEANUP_PASS
    docs['export.checked']['objects'] = [
        _entry('SM_Polygon_001_Main', 'polygon_all', ['cleanup']),
    ]
    docs['export.checked']['reason'] = NO_EXPORT_PASS
    # Live Max: usedMaps omits a Bitmaptexture whose file does not exist, so census
    # never receives the missing path. The contract stays fail/missing_map.
    _mark_known(docs, 'scene.census', 'polygon_all', 'SM_Polygon_007_Main', {
        'id': 'census-usedmaps-drops-missing-file',
        'got_expect': 'pass', 'got_codes': [],
    })
    _mark_known(docs, 'qa.preflight', 'polygon_all', 'SM_Polygon_007_Main', {
        'id': 'census-usedmaps-drops-missing-file',
        'got_expect': 'fail', 'got_codes': ['fbx_objects'],
    })
    if not any(o['expect'] == 'fail' for o in docs['ucx.build']['objects']):
        docs['ucx.build']['reason'] = NO_UCX_FAIL
    if not any(o['expect'] == 'pass' for o in docs['atlas.npm']['objects']):
        docs['atlas.npm']['reason'] = NO_ATLAS_PASS

    for doc in docs.values():
        passes = [o for o in doc['objects'] if o['expect'] == 'pass']
        fails = [o for o in doc['objects'] if o['expect'] == 'fail']
        if doc['shipped'] and not (passes and fails) and not doc['reason'].strip():
            raise RuntimeError('shipped button without pass+fail or reason: ' + doc['button'])
    _annotate_places(docs)
    return docs


def _annotate_places(docs):
    by_button = {}
    for spec in stations():
        by_button.setdefault(spec['button'], []).append(spec['id'])
    version_of = {row['id']: row['version'] for row in suite_rows()}
    built = {base['version'] for base in bases()}
    for button, doc in docs.items():
        version = version_of[button]
        ids = by_button.get(button, [])
        doc['base'] = version if version in built else None
        doc['station'] = ids[0] if ids else None
        doc['stations'] = ids


def _expect_phrase(doc, names):
    bits = []
    wanted = list(names)
    if not wanted:
        for kind in ('pass', 'fail'):
            hit = next((obj['name'] for obj in doc['objects'] if obj['expect'] == kind), None)
            if hit:
                wanted.append(hit)
    for name in wanted[:3]:
        hit = next((obj for obj in doc['objects'] if obj['name'] == name), None)
        if hit is None:
            continue
        if hit['expect'] == 'pass':
            bits.append('pass')
        elif hit['codes']:
            bits.append(hit['expect'] + ' ' + ','.join(hit['codes']))
        else:
            bits.append(hit['expect'])
    if doc.get('reason') and not any(obj['expect'] == 'pass' for obj in doc['objects']):
        bits.append('PASS нет')
    if doc.get('reason') and not any(obj['expect'] == 'fail' for obj in doc['objects']):
        bits.append('FAIL нет')
    out = []
    for bit in bits:
        if bit not in out:
            out.append(bit)
    return ' / '.join(out) if out else 'см. expected'


def _station_caption(spec, doc, label_ru):
    names = [name for name in spec['homes'] if any(obj['name'] == name for obj in doc['objects'])]
    if not names:
        for kind in ('pass', 'fail'):
            hit = next((obj['name'] for obj in doc['objects'] if obj['expect'] == kind), None)
            if hit and hit not in names:
                names.append(hit)
    shown = ', '.join(names[:3]) if names else spec['button']
    return 'Станция {}: {} - нажми {} -> ожидаешь {}'.format(
        spec['id'], shown, label_ru, _expect_phrase(doc, names))


def _base_caption(base, labels):
    names = [labels[button] for button in base['buttons'] if button in labels]
    buttons = ', '.join(names) if names else 'нет'
    return 'База {} — {}, кнопки: {}'.format(base['version'], base['title'], buttons)


def _fixture(name, role, layer, pos, size, mesh, cls, text, colour):
    return {
        'name': name, 'scene': 'polygon_all', 'role': role, 'layer': layer, 'zone': layer,
        'base': '', 'station': '', 'mesh': mesh, 'pos': list(pos), 'size': list(size),
        'fbx': None, 'mat': 'none', 'mat_name': None, 'superclass': 'shape' if cls == 'Text' else 'geometry',
        'cls': cls, 'scale': [1.0, 1.0, 1.0], 'parent': None, 'children': 0, 'animated': False,
        'modifiers': [], 'opacity': 1.0, 'tex': None, 'map_path': None, 'matid': None,
        'uv_periods': None, 'uv_shift': None, 'atlas': None, 'texel_px': None,
        'extra_channel': False, 'pivot': None, 'text': text, 'zero': 0.0, 'colour': colour,
        'AGR_TEST': 'fixture', 'synthetic': True,
    }


def fixture_objects(docs):
    """Ground rectangles and Russian captions. Not checked and not exported."""
    labels = {row['id']: row['label_ru'] for row in suite_rows()}
    laid = _layout()
    out = []
    for base in laid:
        token = _version_token(base['version'])
        out.append(_fixture(
            '_base_' + token, 'base', BASE_LAYER, base['rect_pos'], base['rect_size'],
            'box', 'Editable_Poly', None, base['colour']))
        out.append(_fixture(
            '_label_base_' + token, 'label', LABEL_LAYER, base['label_pos'], (1, 1, 0),
            'empty', 'Text', _base_caption(base, labels), None))
        for spec in base['stations']:
            doc = docs[spec['button']]
            full = next(item for item in stations() if item['id'] == spec['id'])
            out.append(_fixture(
                '_label_' + _version_token(spec['id']), 'label', LABEL_LAYER, spec['label_pos'],
                (1, 1, 0), 'empty', 'Text',
                _station_caption(full, doc, labels[spec['button']]), None))
    return out


def agr_test_of(obj, docs):
    parts = []
    if obj.get('station'):
        parts.append('station=' + obj['station'])
    for button, doc in docs.items():
        for entry in doc['objects']:
            if entry['name'] == obj['name'] and entry['scene'] == obj['scene']:
                codes = ','.join(entry['codes']) if entry['codes'] else entry['expect']
                parts.append('{}={}'.format(button, codes if entry['expect'] == 'fail' else 'pass'))
    return ';'.join(parts) if parts else 'label'


def _catalog_row(obj, agr_test):
    return {
        'name': obj['name'], 'scene': obj['scene'], 'role': obj['role'], 'layer': obj['layer'],
        'zone': obj['zone'], 'base': obj.get('base') or '', 'station': obj.get('station') or '',
        'mesh': obj['mesh'], 'pos': obj['pos'], 'size': obj['size'],
        'fbx': obj['fbx'], 'mat': obj['mat'], 'mat_name': obj.get('mat_name'),
        'superclass': obj['superclass'], 'cls': obj['cls'], 'scale': obj['scale'],
        'parent': obj['parent'], 'children': obj['children'], 'animated': obj['animated'],
        'modifiers': obj['modifiers'], 'opacity': obj.get('opacity'), 'tex': obj.get('tex'),
        'map_path': obj.get('map_path'), 'matid': obj.get('matid'), 'uv_periods': obj.get('uv_periods'),
        'uv_shift': obj.get('uv_shift'), 'atlas': obj.get('atlas'), 'texel_px': obj.get('texel_px'),
        'extra_channel': obj.get('extra_channel', False), 'pivot': obj.get('pivot'),
        'text': obj.get('text'), 'colour': obj.get('colour'), 'zero': obj['zero'],
        'AGR_TEST': agr_test, 'synthetic': True,
    }


def catalog(docs):
    objects = [_catalog_row(obj, agr_test_of(obj, docs)) for obj in scene_objects()]
    objects.extend(fixture_objects(docs))
    return {'schema': 1, 'synthetic': True, 'address': 'Polygon',
            'note': 'Synthetic polygon. The Verona bench is a box silhouette, not the client #790 model. '
                    'Bases are one coloured ground rectangle per AGR Tools version; stations sit inside.',
            'objects': objects}


def bases_document(docs):
    labels = {row['id']: row['label_ru'] for row in suite_rows()}
    body = []
    for base in bases():
        block = []
        for spec in stations():
            if spec['version'] != base['version']:
                continue
            doc = docs[spec['button']]
            block.append({
                'id': spec['id'], 'button': spec['button'], 'label_ru': labels[spec['button']],
                'expected': 'expected/{}.json'.format(spec['button']),
                'reason': doc.get('reason') or '',
            })
        body.append({
            'version': base['version'], 'title': base['title'], 'colour': base['colour'],
            'buttons': base['buttons'], 'stations': block,
        })
    return {'schema': 1, 'tour_last': TOUR_LAST, 'bases': body}


def scene_specs():
    return {
        'cm_units': {'schema': 1, 'scene': 'cm_units', 'synthetic': True, 'units': 'centimeters',
                     'note': 'Нельзя совместить со сценой в метрах. Ожидание scene.units: fail system_unit.'},
        'empty': {'schema': 1, 'scene': 'empty', 'synthetic': True, 'units': 'meters', 'objects': [],
                  'note': 'Пустая сцена. Проверки объектов дают ошибку empty target set, не pass.'},
        'vpm': {'schema': 1, 'scene': 'vpm', 'synthetic': True, 'units': 'meters',
                'note': 'Вариант ВПМ: пивот и лимит треугольников Ground без AGR_SITE_AREA_HA. Не NPM.'},
    }


def load_expected(button_id):
    path = EXPECTED / (button_id + '.json')
    if not path.is_file():
        raise KeyError('unmapped button: ' + button_id)
    return json.loads(path.read_text(encoding='utf-8'))


def _nonfinite(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_nonfinite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_nonfinite(v) for v in value)
    return False


def _mismatch(kind, name, detail):
    return {'kind': kind, 'name': name, 'detail': detail}


def _object_codes(obj):
    findings = obj.get('findings')
    if not isinstance(findings, list):
        return None
    codes = []
    for finding in findings:
        if isinstance(finding, dict) and finding.get('code'):
            codes.append(str(finding['code']))
    return sorted(set(codes))


def _scene_codes(report):
    plan = report.get('plan') if isinstance(report, dict) else None
    findings = plan.get('findings') if isinstance(plan, dict) else None
    if not isinstance(findings, list) or not findings:
        return None
    if any(isinstance(f, dict) and f.get('status') == 'not_run' for f in findings):
        return 'not_run'
    codes = []
    for finding in findings:
        if not isinstance(finding, dict) or 'status' not in finding:
            return 'bad'
        if finding['status'] != 'pass':
            codes.append(str(finding.get('name')))
    return sorted(set(codes))


def _without_fixtures(report):
    """Base rectangles and captions are not check results."""
    if not isinstance(report, dict):
        return report
    objects = report.get('objects')
    if not isinstance(objects, list):
        return report
    kept = [obj for obj in objects if not excluded_name(obj.get('name'))]
    if len(kept) == len(objects):
        return report
    clone = dict(report)
    clone['objects'] = kept
    return clone


def compare_report(expected_objects, report):
    """Mismatches only. NaN/Inf, empty, missing, unmapped, not_run and a claimed pass never match.

    Objects named `_base_` / `_label_` are dropped before the diff, so a check that
    happened to see a ground rectangle does not become a result.
    """
    report = _without_fixtures(report)
    if _nonfinite(report):
        return [_mismatch('non_finite', '', 'NaN or Inf in the report')]
    if not isinstance(report, dict) or not report:
        return [_mismatch('empty', '', 'empty report')]
    if report.get('status') == 'error':
        err = str(report.get('error', ''))
        out = []
        for obj in expected_objects:
            if obj['expect'] != 'error' or any(code not in err for code in obj['codes']):
                out.append(_mismatch('error', obj['name'], err or 'error'))
        return out
    scene_codes = _scene_codes(report)
    if scene_codes == 'not_run':
        return [_mismatch('not_run', '__scene__', 'status not_run')]
    objects = report.get('objects')
    if scene_codes is None and (not isinstance(objects, list) or not objects):
        return [_mismatch('empty', '', 'empty report')]
    actual = {}
    if isinstance(objects, list) and objects:
        for obj in objects:
            actual[str(obj.get('name'))] = _object_codes(obj)
    elif isinstance(scene_codes, list):
        actual['__scene__'] = scene_codes
    out = []
    claimed = report.get('status') == 'pass' and any(codes for codes in actual.values())
    if claimed:
        out.append(_mismatch('claimed_pass', '', 'status pass with findings'))
    expected_names = {obj['name'] for obj in expected_objects}
    for name, codes in actual.items():
        if name not in expected_names:
            out.append(_mismatch('unmapped', name, 'unmapped object ' + name))
        elif codes is None:
            out.append(_mismatch('empty', name, 'object without findings'))
    for obj in expected_objects:
        codes = actual.get(obj['name'])
        if codes is None:
            if obj['name'] not in actual:
                out.append(_mismatch('missing', obj['name'], 'missing expected object ' + obj['name']))
            continue
        derived = 'fail' if codes else 'pass'
        bug = obj.get('known_bug') or {}
        bug_codes = sorted(bug.get('got_codes') or [])
        if bug.get('id') and derived == bug.get('got_expect') and codes == bug_codes:
            continue
        if obj['expect'] != derived or codes != sorted(obj['codes']):
            out.append(_mismatch('code', obj['name'],
                                 'expected {} {} got {} {}'.format(obj['expect'], obj['codes'], derived, codes)))
        if 'at_threshold' in codes and obj['expect'] == 'pass':
            out.append(_mismatch('at_threshold', obj['name'], 'at_threshold is not a pass'))
    return out


def _inside(path, root):
    if path == root:
        return True
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def check_paths(input_path, output_path, report_path, temp_path):
    """Refuse before any write. Output, report and temp must not resolve to the input tree or each other."""
    labels = (('input', input_path), ('output', output_path), ('report', report_path), ('temp', temp_path))
    paths = {label: Path(value).resolve() for label, value in labels}
    seen = {}
    for label, path in paths.items():
        key = os.path.normcase(str(path))
        if key in seen:
            raise SystemExit('{} and {} are the same file: {}'.format(label, seen[key], path))
        seen[key] = label
    root = paths['input']
    for label in ('output', 'report', 'temp'):
        if _inside(paths[label], root):
            raise SystemExit('{} resolves to an input: {}'.format(label, paths[label]))


def user_bundle(appdata):
    """The operator's installed AGR Tools. Tests pass a temp root, never the real %APPDATA%."""
    return Path(appdata) / 'Autodesk' / 'ApplicationPlugins' / 'AGR-Tools.bundle'


def _snapshot_tree(root):
    files = {}
    if root.is_file():
        files[''] = root.read_bytes()
        return files
    for path in sorted(root.rglob('*')):
        if path.is_file():
            files[str(path.relative_to(root)).replace('\\', '/')] = path.read_bytes()
    return files


def _remove_path(path):
    """Remove a replacement we created at the bundle path. Never called on the aside copy."""
    if path.is_file() or path.is_symlink():
        path.unlink()
        return
    for child in sorted(path.rglob('*'), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()


class preserve_user_bundle:
    """Move AGR-Tools.bundle aside for a test install and put the same bytes back.

    The runner does not install the bundle. Anything that does must use this, so the
    copy in %APPDATA%\\Autodesk\\ApplicationPlugins is restored in finally and is never
    deleted. A replacement written at the original path during the block is removed
    only so the aside copy can take the name again.
    """

    def __init__(self, appdata):
        self.root = user_bundle(appdata)
        self.aside = self.root.with_name(self.root.name + '.polygon-aside')
        self.snap = None
        self.moved = False

    def __enter__(self):
        if self.aside.exists():
            raise RuntimeError('bundle aside path already exists: ' + str(self.aside))
        if self.root.exists():
            self.snap = _snapshot_tree(self.root)
            self.root.rename(self.aside)
            self.moved = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.moved:
            return False
        try:
            if self.root.exists():
                _remove_path(self.root)
            self.aside.rename(self.root)
            if _snapshot_tree(self.root) != self.snap:
                raise RuntimeError('AGR-Tools.bundle restore is not byte-identical')
        finally:
            self.moved = False
        return False


def group_runs(jobs, mismatches):
    """jobs: [(button, scene), ...]. Rows sit under their base and station."""
    bad = {(item.get('button'), item.get('scene'), item.get('name')) for item in mismatches}
    grouped = []
    for base in bases():
        block = []
        for spec in stations():
            if spec['version'] != base['version']:
                continue
            rows = []
            for button, scene in jobs:
                if button != spec['button']:
                    continue
                doc = load_expected(button)
                for obj in doc['objects']:
                    if obj['scene'] != scene:
                        continue
                    failed = (button, scene, obj['name']) in bad or (button, scene, '') in bad
                    rows.append({
                        'button': button, 'scene': scene, 'name': obj['name'],
                        'expected': '{} {}'.format(obj['expect'], ','.join(obj['codes'])).strip(),
                        'result': 'НЕ OK' if failed else 'OK', 'ok': not failed,
                    })
            block.append({'id': spec['id'], 'button': spec['button'], 'rows': rows})
        grouped.append({'version': base['version'], 'title': base['title'], 'stations': block})
    return grouped


def render_table(grouped, mismatches):
    lines = ['база\tстанция\tкнопка\tсцена\tобъект\tожидалось\tитог']
    for base in grouped:
        lines.append('База {}\t\t\t\t\t{}'.format(base['version'], base['title']))
        if not base['stations']:
            lines.append('\t—\tкнопок нет\t\t\t')
        for spec in base['stations']:
            if not spec['rows']:
                lines.append('\t{}\t{}\t\t\t'.format(spec['id'], spec['button']))
                continue
            for row in spec['rows']:
                lines.append('\t{}\t{}\t{}\t{}\t{}\t{}'.format(
                    spec['id'], row['button'], row['scene'], row['name'], row['expected'], row['result']))
    for item in mismatches:
        if item.get('name') in ('', None) or item.get('kind') in (
                'unmapped', 'empty', 'non_finite', 'error', 'apply'):
            lines.append('\t\t{}\t{}\t{}\t{}\tНЕ OK'.format(
                item.get('button'), item.get('scene'), item.get('name') or '—', item.get('detail')))
    return '\n'.join(lines) + '\n'


def write_tree():
    """Write expected/, catalog, scene specs, geojson and the texture spec. No Max, no PNG in git."""
    docs = predict_all()
    EXPECTED.mkdir(parents=True, exist_ok=True)
    for button, doc in docs.items():
        (EXPECTED / (button + '.json')).write_text(
            json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (POLY / 'bases.json').write_text(
        json.dumps(bases_document(docs), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (POLY / 'catalog.json').write_text(
        json.dumps(catalog(docs), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    scenes = POLY / 'scenes'
    scenes.mkdir(parents=True, exist_ok=True)
    for name, doc in scene_specs().items():
        (scenes / (name + '.json')).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    geo = POLY / 'geojson'
    geo.mkdir(parents=True, exist_ok=True)
    (geo / 'valid_oks.geojson').write_bytes(_geojson_bytes())
    (geo / 'broken_syntax.geojson').write_text('{this is not json\n', encoding='utf-8')
    (geo / 'broken_schema.geojson').write_text('{"type": "Feature", "features": []}\n', encoding='utf-8')
    spec = {key: {'file': filename, 'bytes': len(data)} for key, (filename, data) in TEXTURES.items()}
    (POLY / 'textures').mkdir(parents=True, exist_ok=True)
    (POLY / 'textures' / 'spec.json').write_text(
        json.dumps({'schema': 1, 'synthetic': True, 'cases': spec,
                    'note': 'PNG bytes are written by generate.py into the output folder, not into git.'},
                   ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return docs


def stage_tools(dest, root=None):
    """Copy agr_tools sources and the generated slices into dest/agr_tools.

    runtime.py loads hygiene_core.py, uv_nudge_core.py and ucx_audit_core.py from its
    own directory. Those slices are produced at bundle build time and are not in the
    checkout. The copy is the runner's private folder. The operator's AGR-Tools.bundle
    under %APPDATA%\\Autodesk\\ApplicationPlugins is never read or written.
    """
    import importlib.util
    root = Path(root or POLY.parent).resolve()
    dest = Path(dest).resolve()
    appdata = os.environ.get('APPDATA')
    if appdata:
        installed = Path(appdata) / 'Autodesk' / 'ApplicationPlugins'
        if _inside(dest, installed.resolve()):
            raise SystemExit('stage resolves to the installed AGR-Tools.bundle: ' + str(dest))
    package = root / 'adapters' / 'max' / 'agr_tools'
    builder_path = root / 'tools' / 'max' / 'build_agr_tools.py'
    folder = dest / 'agr_tools'
    folder.mkdir(parents=True, exist_ok=True)
    for path in sorted(package.glob('*.py')):
        (folder / path.name).write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    spec = importlib.util.spec_from_file_location('agr_polygon_tools_build', builder_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (folder / 'hygiene_core.py').write_bytes(mod.hygiene_slice())
    (folder / 'uv_nudge_core.py').write_bytes(mod.nudge_slice())
    (folder / 'ucx_audit_core.py').write_bytes(mod.audit_slice())
    return folder


def generate_outputs(out_dir):
    """Write PNG and ASCII FBX into out_dir. Refuses when out_dir is inside the polygon sources."""
    out = Path(out_dir).resolve()
    check_paths(POLY, out, out / 'report.json', out / 'temp')
    (out / 'textures').mkdir(parents=True, exist_ok=True)
    (out / 'fbx').mkdir(parents=True, exist_ok=True)
    for _key, (filename, data) in TEXTURES.items():
        (out / 'textures' / filename).write_bytes(data)
    (out / 'fbx' / 'reference_box.fbx').write_text(ascii_fbx(), encoding='utf-8')
    (out / 'fbx' / 'broken_truncated.fbx').write_text('FBX', encoding='utf-8')
    return out


def ascii_fbx():
    return (
        '; FBX 7.4.0 project file\n'
        '; synthetic AGR test-polygon reference, not a client model\n'
        'FBXHeaderExtension:  {\n'
        '\tFBXHeaderVersion: 1003\n'
        '\tFBXVersion: 7400\n'
        '}\n'
        'Documents:  {\n'
        '\tCount: 1\n'
        '}\n'
    )


if __name__ == '__main__':
    write_tree()
    print('wrote', len(list(EXPECTED.glob('*.json'))), 'expected files')
