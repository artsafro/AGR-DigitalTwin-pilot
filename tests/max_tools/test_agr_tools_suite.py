"""new-case: AGR Tools 0.7.0 pre-delivery checks, «Путь» roadmap, rail data, GUIDE and MCP tools (#860)."""
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


checks = _load('checks_core.py', 'agr_tools_checks_core')
core = _load('suite_core.py', 'agr_tools_suite_core_test')
roadmap = _load('roadmap.py', 'agr_tools_roadmap_test')
model = _load('ui_model.py', 'agr_tools_ui_model_suite_test')
runtime = _load('runtime.py', 'agr_runtime_suite_test')
from twinqa.geometry import ucx_audit as audit  # noqa: E402

CUBE_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
CUBE_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
          (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
STD = {'name': 'M_A_001_Main_1', 'cls': 'Standardmaterial', 'maps': ['d.png'], 'missing': [], 'opacity': 1.0}
NPM_FBX = 'C:/out/0101_Addr_01.fbx'
NPM_GROUND = 'C:/out/0101_Addr_Ground.fbx'


def obj(key, name='SM_Addr_001_Main', fbx=NPM_FBX, **kw):
    r = {'key': key, 'name': name, 'fbx': fbx, 'superclass': 'geometry', 'cls': 'Editable_Poly', 'faces': 12,
         'verts': 8, 'materials': [dict(STD)], 'parent': None, 'children': 0, 'group': False, 'animated': False,
         'modifiers': [], 'layer': '0', 'scale': (1.0, 1.0, 1.0), 'rotation': (0.0, 0.0, 0.0, 1.0),
         'mirror': False, 'bbox': ((0, 0, -2), (1, 1, 1)), 'instances': 1, 'zero_m': 0.0, 'roof_set': False,
         'mesh': {'verts': [(x, y, z - 2.0) for x, y, z in CUBE_V], 'tris': list(CUBE_T)}}
    r.update(kw)
    return r


def codes(found, key):
    return sorted(c for c, _, _ in found.get(key, []))


METRE_SCENE = {'unit_type': 'meters', 'unit_scale': 1.0, 'file_in_gamma': 1.0, 'file_out_gamma': 1.0,
               'path': 'C:/s.max'}


def report_of(tool, rows, scene=None):
    f, d, s = core.run(tool, rows, audit, scene=dict(scene or METRE_SCENE))
    return core.report(tool, rows, f, d, s)


# ---- thresholds pinned to the locked standards ------------------------------------------------------
def test_thresholds_pinned_to_standards():
    npm = yaml.safe_load((ROOT / 'standards/NPM_STANDARD.yaml').read_text(encoding='utf-8'))
    vpm = yaml.safe_load((ROOT / 'standards/VPM_STANDARD.yaml').read_text(encoding='utf-8'))
    assert core.PERIMETER_DROP_M == npm['geometry']['ground_perimeter_extrude_down_m_min'] \
        == vpm['geometry']['oks_perimeter_extrude_down_m_min'] == vpm['geometry']['ground_perimeter_extrude_down_m_min']
    assert core.OKS_FBX_MAX + 1 == npm['archive']['fbx_total']['max']
    assert core.OKS_OPAQUE_OBJECTS_MAX == npm['geometry']['oks_opaque_objects_max']
    assert core.OKS_TRANSPARENT_OBJECTS_MAX == npm['geometry']['oks_transparent_objects_max']
    assert core.GLASS_MATERIALS_MAX == npm['materials']['transparent_materials_max'] == vpm['materials']['glass_slots_max']
    assert core.GLASS_OPACITY == npm['materials']['transparent_material_opacity']
    sets = npm['materials']['texture_sets_per_oks']
    assert core.ROOF_EXTRA_SETS == sets['with_usable_roof_max'] - sets['default_max']
    assert npm['units']['linear'] == vpm['units']['linear'] == 'meter' and core.SYSTEM_UNIT == 'meters'


def test_every_check_is_a_plan_row_of_version_07():
    suite = roadmap.load_file(SUITE)
    rows07 = {r['id'] for r in suite['rows'] if r['version'] == '0.7'}
    assert set(core.PLAN_ROW.values()) == rows07 and len(core.TOOLS) == 12
    assert set(runtime.CHECKS_070) == set(core.TOOLS)
    for r in suite['rows']:
        if r['id'] in rows07:
            assert r['mode'] == 'read'  # 0.7 is read-only by plan


# ---- each check: clean pass + named failure -----------------------------------------------------------
def test_clean_scene_passes_every_object_check():
    rows = [obj(1), obj(2, 'SM_Addr_Ground', NPM_GROUND)]
    for tool in core.PREFLIGHT + ('preflight',):
        rep = report_of(tool, rows)
        assert rep['status'] == 'pass', (tool, rep)
        assert [o['handle'] for o in rep['objects']] == [1, 2]


def test_units_cm_scene_fails_d5():
    """D-regression D5 (texel 100x off in a cm scene): a centimetre scene fails, metres pass."""
    good = {'unit_type': 'meters', 'unit_scale': 1.0, 'file_in_gamma': 1.0, 'file_out_gamma': 1.0}
    rep = core.scene_report('units', 'C:/s.max', core.units(good))
    assert rep['status'] == 'pass'
    bad = dict(good, unit_type='centimeters')
    rep = core.scene_report('units', 'C:/s.max', core.units(bad))
    assert rep['status'] == 'fail'
    assert [f['name'] for f in rep['plan']['findings'] if f['status'] == 'fail'] == ['system_unit']
    for value in (float('nan'), float('inf'), None, '1.0', 0.01):
        rep = core.scene_report('units', 'C:/s.max', core.units(dict(good, unit_scale=value)))
        assert rep['status'] == 'fail', value


def test_perimeter_drop_short_exact_missing_zero():
    f, _, _ = core.perimeter_drop([obj(1), obj(2, zero_m=-1.5), obj(3, zero_m=-1.0), obj(4, zero_m=None),
                                   obj(5, zero_m=float('nan')), obj(6, fbx=None)])
    assert codes(f, 1) == []
    assert codes(f, 2) == ['drop_short']
    assert codes(f, 3) == ['at_threshold']        # exactly 1 m: never a silent pass
    assert codes(f, 4) == codes(f, 5) == ['drop_unmeasurable']  # no default ±0.000
    assert codes(f, 6) == ['fbx_unmapped']


GLASS = dict(STD, name='M_Glass_1', maps=[], opacity=0.5)


def _kinds_scene():
    """Main + MainGlass + Ground + GroundEl + Flora; only Main/Ground are dropped below ±0.000."""
    def up(z0, z1):
        return {'verts': [(x, y, z0 + z * (z1 - z0)) for x, y, z in CUBE_V], 'tris': list(CUBE_T)}
    return [obj(1),
            obj(2, 'SM_Addr_001_MainGlass', materials=[dict(GLASS)], mesh=up(3, 6), bbox=((0, 0, 3), (1, 1, 6))),
            obj(3, 'SM_Addr_Ground', NPM_GROUND),
            obj(4, 'SM_Addr_001_GroundEl', NPM_GROUND, mesh=up(0, 1), bbox=((0, 0, 0), (1, 1, 1))),
            obj(5, 'SM_Addr_001_Flora', NPM_GROUND, mesh=up(0, 5), bbox=((0, 0, 0), (1, 1, 5)))]


def test_perimeter_drop_only_main_and_ground():
    """Review P1 (PR #881): MainGlass/GroundEl/Flora above ±0.000 are not perimeter meshes, no drop_short."""
    f, _, s = core.perimeter_drop(_kinds_scene())
    assert {k: codes(f, k) for k in range(1, 6)} == {1: [], 2: [], 3: [], 4: [], 5: []}
    assert [n['kind'] for n in s['not_applicable']] == ['MainGlass', 'GroundEl', 'Flora']
    # a short Main/Ground is still caught next to them, and missing ±0.000 on a glass mesh is not a finding
    rows = _kinds_scene()
    rows[0]['zero_m'] = -1.5
    rows[2]['zero_m'] = -1.0
    rows[1]['zero_m'] = None
    f, _, _ = core.perimeter_drop(rows)
    assert {k: codes(f, k) for k in range(1, 6)} == {1: ['drop_short'], 2: [], 3: ['at_threshold'], 4: [], 5: []}


NON_PERIMETER = ('MainGlass', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora')


def test_perimeter_drop_unknown_suffix_is_a_finding():
    """#884: SM_Addr_001_Main_1 / SM_Addr_main are kind_unknown, not a silent skip."""
    for name in ('SM_Addr_001_Main_1', 'SM_Addr_main'):
        f, _, s = core.perimeter_drop([obj(1, name, zero_m=-0.2)])
        assert codes(f, 1) == ['kind_unknown'], name
        assert s['not_applicable'] == []
        rep = report_of('perimeter_drop', [obj(1, name, zero_m=-0.2)])
        assert rep['status'] == 'fail' and rep['objects'][0]['findings'][0]['code'] == 'kind_unknown'
    rows = [obj(1, 'SM_Addr_001_Main_1', zero_m=-0.2), obj(2, 'SM_Addr_Ground', NPM_GROUND)]
    pre = report_of('preflight', rows)
    assert codes_of(pre, 'SM_Addr_001_Main_1') == ['kind_unknown']
    assert pre['plan']['summary']['checks']['perimeter_drop'] == 'fail'
    known = [obj(i + 1, 'SM_Addr_001_' + kind, zero_m=-0.2) for i, kind in enumerate(NON_PERIMETER)]
    f, _, s = core.perimeter_drop(known)
    assert {k: codes(f, k) for k in range(1, len(known) + 1)} == {k: [] for k in range(1, len(known) + 1)}
    assert [n['kind'] for n in s['not_applicable']] == list(NON_PERIMETER)


def codes_of(rep, name):
    hit = next(o for o in rep['objects'] if o['name'] == name)
    return sorted(f['code'] for f in hit['findings'])


def test_unknown_suffix_probe_fail_closed():
    """Every unknown-suffix mesh yields kind_unknown; known non-perimeter kinds never do.

    Empty, partial, non-string, NaN/inf and exactly-1 m input fail or error, never pass.
    """
    rnd = random.Random(884)
    names = [
        'SM_Addr_001_Main_1', 'SM_Addr_main', 'SM_Addr_MAIN', 'SM_Addr_MainGlass_1',
        '', ' ', '1', 'Main_1', 'ground', 'SM_Addr_001_Mai', None, 0, 1.5,
        'SM_Addr_001_Main\t', '___',
    ]
    tokens = list(NON_PERIMETER) + ['Main', 'Ground', 'main', 'MAIN', '1', 'x', 'Glass', '']
    for _ in range(240):
        parts = [rnd.choice(('SM', 'XX', 'A', '')) for _ in range(rnd.randint(1, 4))]
        parts.append(rnd.choice(tokens) + rnd.choice(('', '1', 'x', '_')))
        name = '_'.join(parts)
        if isinstance(name, str) and name.upper().startswith('UCX_'):
            name = 'Z' + name
        last = name.split('_')[-1] if name else ''
        if last in checks.NPM_TYPES:
            name += 'Z'
        names.append(name)
    zeros = (0.0, -0.2, -1.0, -1.5, None, float('nan'), float('inf'), float('-inf'))
    rows, unknown_keys = [], []
    for i, name in enumerate(names):
        row = obj(i + 1, 'placeholder', zero_m=zeros[i % len(zeros)])
        row['name'] = name
        if i % 17 == 0:
            row['mesh'] = {'verts': [], 'tris': []}
        if i % 19 == 0:
            row['mesh'] = {'verts': [(0, 0, float('nan'))], 'tris': []}
        if i % 23 == 0:
            row.pop('mesh')
        rows.append(row)
        unknown_keys.append(i + 1)
    known_keys = []
    for kind in NON_PERIMETER:
        for z in zeros:
            key = len(rows) + 1
            rows.append(obj(key, 'SM_Addr_001_' + kind, zero_m=z))
            known_keys.append(key)
    ucx_key = len(rows) + 1
    rows.append(obj(ucx_key, 'UCX_SM_Addr_Main_001', zero_m=float('nan')))
    cam_key = ucx_key + 1
    rows.append(obj(cam_key, 'NotAMesh', superclass='camera', cls='Freecamera', faces=0, materials=[],
                    mesh={'verts': [], 'tris': []}, zero_m=None))
    f, _, s = core.perimeter_drop(rows)
    for key in unknown_keys:
        assert codes(f, key) == ['kind_unknown'], (key, rows[key - 1]['name'])
    for key in known_keys:
        assert 'kind_unknown' not in codes(f, key) and codes(f, key) == []
    assert codes(f, ucx_key) == [] and codes(f, cam_key) == []
    assert [n['kind'] for n in s['not_applicable']] == [rows[k - 1]['name'].split('_')[-1] for k in known_keys]
    assert 'unknown suffix' not in {n['kind'] for n in s['not_applicable']}
    rep = report_of('perimeter_drop', [obj(1, 'SM_Addr_001_Main_1', zero_m=-1.0)])
    assert rep['status'] == 'fail' and codes_of(rep, 'SM_Addr_001_Main_1') == ['kind_unknown']
    with pytest.raises(ValueError):
        core.perimeter_drop([])
    with pytest.raises(ValueError):
        core.perimeter_drop([obj(1), obj(1)])
    partial = obj(1)
    partial.pop('mesh')
    with pytest.raises(ValueError):
        core.perimeter_drop([partial])
    assert len(unknown_keys) + len(known_keys) == 255 + 40


def test_preflight_passes_valid_scene_with_every_kind():
    rep = report_of('preflight', _kinds_scene())
    assert rep['status'] == 'pass', [(o['name'], o['findings']) for o in rep['objects'] if o['findings']]


def test_material_type_names_corona_and_subs():
    corona = {'name': 'M_bad', 'cls': 'CoronaPhysicalMtl', 'maps': [], 'missing': [], 'opacity': None}
    multi = {'name': 'Multi', 'cls': 'Multimaterial', 'maps': [], 'missing': [], 'opacity': None}
    f, _, _ = core.material_type([obj(1), obj(2, materials=[multi, dict(STD), corona]), obj(3, materials=[])])
    assert codes(f, 1) == []
    assert f[2] == [('mat_class', 'M_bad: CoronaPhysicalMtl', ())]
    assert codes(f, 3) == ['mat_none']


def test_ucx_audit_open_material_name_intersection():
    ucx = [(x * 0.5, y * 0.5, z * 0.5) for x, y, z in CUBE_V]
    shifted = [(x * 0.5 + 0.25, y * 0.5, z * 0.5) for x, y, z in CUBE_V]
    rows = [obj(1, 'SM_Addr_Main', 'C:/o/SM_Addr.fbx'),
            obj(2, 'UCX_SM_Addr_Main_001', 'C:/o/SM_Addr.fbx', materials=[], mesh={'verts': ucx, 'tris': CUBE_T}),
            obj(3, 'UCX_SM_Addr_Main_002', 'C:/o/SM_Addr.fbx', materials=[], mesh={'verts': shifted, 'tris': CUBE_T}),
            obj(4, 'UCX_SM_Addr_Main_003', 'C:/o/SM_Addr.fbx', materials=[dict(STD)],
                mesh={'verts': [(x + 5, y, z) for x, y, z in ucx], 'tris': CUBE_T[:-1]}),
            obj(5, 'UCX_SM_Addr Main_004', 'C:/o/SM_Addr.fbx', materials=[],
                mesh={'verts': [(x + 9, y, z) for x, y, z in ucx], 'tris': CUBE_T})]
    f, _, s = core.ucx_audit(rows, audit)
    assert s['ucx_objects'] == 4
    assert codes(f, 1) == []
    assert codes(f, 2) == codes(f, 3) == ['ucx_intersect']
    assert codes(f, 4) == ['ucx_material', 'ucx_open']
    assert codes(f, 5) == ['ucx_name']  # full name with a space is kept and judged (ucx_check.exe cut it)


def test_sets_count_limits_and_roof():
    def mats(n):
        return [dict(STD, name='M_{}'.format(i)) for i in range(n)]
    f, _, s = core.sets_count([obj(1, materials=mats(41))])
    assert codes(f, 1) == ['sets_limit']
    f, _, _ = core.sets_count([obj(1, materials=mats(41), roof_set=True)])
    assert codes(f, 1) == []
    f, _, _ = core.sets_count([obj(1, materials=mats(40))])
    assert codes(f, 1) == []
    f, _, _ = core.sets_count([obj(1, 'SM_Addr_001_GroundEl', NPM_GROUND, materials=mats(2)),
                               obj(2, 'SM_Addr_Ground', NPM_GROUND, materials=mats(20))])
    assert codes(f, 1) == ['sets_limit'] and codes(f, 2) == []
    glass = dict(STD, name='M_Glass', maps=[])
    f, _, _ = core.sets_count([obj(1, materials=mats(40) + [glass])])
    assert codes(f, 1) == []  # glass is not a texture set


def test_fbx_split_count_objects_ground_numbering():
    rows = [obj(i, 'SM_Addr_{:03d}_Main'.format(i), 'C:/o/0101_Addr_01.fbx') for i in range(1, 22)]
    f, _, _ = core.fbx_split(rows)
    assert all('fbx_objects' in codes(f, i) and 'fbx_ground_missing' in codes(f, i) for i in range(1, 22))
    rows = [obj(1, fbx='C:/o/0101_Addr_01.fbx'), obj(2, fbx='C:/o/0101_Addr_03.fbx'),
            obj(3, 'SM_Addr_Ground', NPM_GROUND), obj(4, fbx='C:/o/whatever.fbx')]
    f, _, _ = core.fbx_split(rows)
    assert codes(f, 1) == codes(f, 2) == ['fbx_numbering'] and codes(f, 3) == []
    assert codes(f, 4) == ['fbx_unmapped']


def test_glass_d2_mainglass_reached_and_d3_no_maps_passes():
    """D-regressions: D2 (MainGlass branch unreachable) and D3 («no textures» fired on every material)."""
    g = {'name': 'M_Addr_001_MainGlass_1', 'cls': 'Standardmaterial', 'maps': [], 'missing': [], 'opacity': 0.5}
    rows = [obj(1, 'SM_Addr_001_MainGlass', materials=[g]), obj(2, 'SM_Addr_Ground', NPM_GROUND)]
    f, _, s = core.glass(rows)
    assert codes(f, 1) == []                      # D3: an empty usedMaps array is "no maps"
    assert s['glass'][0]['objects'] == 1          # D2: the MainGlass object is checked, not taken for Main
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=[dict(g, maps=['x.png'], opacity=0.3)])])
    assert codes(f, 1) == ['glass_maps', 'glass_opacity']
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_Main', materials=[dict(STD), g])])
    assert codes(f, 1) == ['glass_not_separate']
    many = [dict(g, name='M_G{}'.format(i)) for i in range(8)]
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=many)])
    assert codes(f, 1) == ['glass_materials']
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=[dict(g, opacity=float('nan'))])])
    assert codes(f, 1) == ['glass_opacity']


def test_glass_opaque_material_on_glass_mesh():
    """Probe: MainGlass with a real glass material and an opaque sibling must name that sibling."""
    glass = {'name': 'M_Glass', 'cls': 'Standardmaterial', 'maps': [], 'missing': [], 'opacity': 0.5}
    brick = {'name': 'M_Brick', 'cls': 'Standardmaterial', 'maps': ['b.png'], 'missing': [], 'opacity': 1.0}
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=[glass, brick])])
    assert f[1] == [('glass_opaque_material', 'непрозрачный материал на стекле: M_Brick', ())]
    # a *Glass mesh with no glass material at all still checks every non-multi material
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=[brick])])
    assert codes(f, 1) == ['glass_maps', 'glass_opacity']


def test_glass_token_opacity_and_sets_count_probe():
    """Glass is an exact name token or opacity < 1 - tol. Fiberglass is an opaque set. NaN, inf and
    opacity exactly at the threshold never count as glass."""
    glass_names = ['Glass', 'M_Glass', 'M_Glass_01', 'GLASS', 'a.glass.b', 'x-Glass-y', 'glass',
                   'M_A_MainGlass_1', 'M_A_GroundGlass_1', 'M_A_GroundElGlass_1', 'mainglass']
    opaque_names = ['M_Fiberglass_Panel', 'Fiberglass', 'stainedglass', 'glassy',
                    'hourglass', 'M_Brick', 'glass2', '2glass']
    threshold = 1.0 - core.OPACITY_TOL
    below = math.nextafter(threshold, 0.0)
    by_opacity = (0.0, 0.5, below)
    not_by_opacity = (threshold, 1.0, float('nan'), float('inf'), float('-inf'), None)

    def mat(name, opacity, maps=()):
        return {'name': name, 'cls': 'Standardmaterial', 'maps': list(maps), 'missing': [], 'opacity': opacity}

    def forty():
        return [dict(STD, name='M_{}'.format(i)) for i in range(40)]

    for name in glass_names:
        assert core._is_glass_material(mat(name, 1.0)), name
        f, _, _ = core.glass([obj(1, 'SM_Addr_001_Main', materials=[mat(name, 1.0)])])
        assert codes(f, 1) == ['glass_not_separate'], name
        for op in not_by_opacity:
            assert core._is_glass_material(mat(name, op)), (name, op)
            f, _, _ = core.sets_count([obj(1, materials=forty() + [mat(name, op)])])
            assert codes(f, 1) == [], (name, op)  # token still keeps it out of the opaque sets

    for name in opaque_names:
        for op in not_by_opacity:
            assert not core._is_glass_material(mat(name, op)), (name, op)
        for op in by_opacity:
            assert core._is_glass_material(mat(name, op)), (name, op)

    fiber = mat('M_Fiberglass_Panel', 1.0, maps=['f.png'])
    f, _, _ = core.sets_count([obj(1, materials=forty() + [fiber])])
    assert codes(f, 1) == ['sets_limit']  # name is not glass, so it is an opaque set
    f, _, _ = core.glass([obj(1, 'SM_Addr_001_Main', materials=[fiber])])
    assert codes(f, 1) == []
    f, _, _ = core.sets_count([obj(1, materials=forty() + [mat('M_Fiberglass_Panel', 0.5)])])
    assert codes(f, 1) == []  # opacity still makes it glass, so it is not a set
    f, _, _ = core.sets_count([obj(1, materials=forty() + [mat('Glass', 1.0)])])
    assert codes(f, 1) == []
    f, _, _ = core.sets_count([obj(1, materials=forty() + [mat('M_Glass', 1.0)])])
    assert codes(f, 1) == []

    real = mat('M_Glass', 0.5)
    for name in opaque_names:
        for op in (float('nan'), float('inf'), float('-inf'), threshold):
            f, _, _ = core.sets_count([obj(1, materials=forty() + [mat(name, op)])])
            assert codes(f, 1) == ['sets_limit'], (name, op)
            f, _, _ = core.glass([obj(1, 'SM_Addr_001_MainGlass', materials=[real, mat(name, op)])])
            assert codes(f, 1) == ['glass_opaque_material'], (name, op)
            assert name in f[1][0][1], (name, op)


def test_scene_hygiene_d7_rules_always_on():
    rows = [obj(1, superclass='camera', cls='Physical', faces=0), obj(2, animated=True), obj(3, parent='X'),
            obj(4, group=True), obj(5, faces=0), obj(6, modifiers=['TurboSmooth']), obj(7, children=2),
            obj(8, superclass='light', cls='Omnilight', faces=0), obj(9)]
    f, _, _ = core.scene_hygiene(rows)
    assert [codes(f, i) for i in range(1, 10)] == [
        ['hyg_non_mesh'], ['hyg_animation'], ['hyg_hierarchy'], ['hyg_group'], ['hyg_empty'],
        ['hyg_modifier'], ['hyg_hierarchy'], ['hyg_non_mesh'], []]


def test_xform_scale_rotation_mirror_parent_nan():
    s45 = math.sin(math.radians(22.5))
    rows = [obj(1), obj(2, scale=(1.0, 2.0, 1.0)), obj(3, rotation=(0.0, 0.0, s45, math.cos(math.radians(22.5)))),
            obj(4, mirror=True, scale=(-1.0, 1.0, 1.0)), obj(5, parent='P'), obj(6, scale=(float('nan'), 1, 1)),
            obj(7, rotation=(0.0, 0.0, 0.0, -1.0))]
    f, _, _ = core.xform(rows)
    assert [codes(f, i) for i in range(1, 8)] == [[], ['xform_scale'], ['xform_rotation'], ['xform_mirror'],
                                                  ['xform_parent'], ['xform_unmeasurable'], []]


def test_zero_area_faces_edges_isolated():
    v = list(CUBE_V) + [(0.5, 0.5, 0.5), (2, 2, 2), (2, 2, 2 + 1e-7)]
    t = list(CUBE_T) + [(8, 8, 9), (9, 10, 8)]
    f, _, _ = core.zero_area([obj(1, mesh={'verts': v, 'tris': t}), obj(2),
                              obj(3, mesh={'verts': [(0, 0, float('inf'))], 'tris': []}),
                              obj(4, mesh={'verts': CUBE_V, 'tris': [(0, 1, 99)]})])
    assert codes(f, 1) == ['zero_area_face', 'zero_length_edge']
    assert [ids for c, _, ids in f[1] if c == 'zero_area_face'] == [(13,)]
    assert codes(f, 2) == []
    assert codes(f, 3) == ['zero_unmeasurable'] and codes(f, 4) == ['zero_unmeasurable']
    v2 = list(CUBE_V) + [(5, 5, 5)]
    f, _, _ = core.zero_area([obj(1, mesh={'verts': v2, 'tris': CUBE_T})])
    assert codes(f, 1) == ['isolated_vertex']


def test_non_mesh_objects_are_hygiene_findings_only():
    """Native smoke regression (Max 2026): a camera with AGR_EXPORT_PATH gave drop_unmeasurable and mat_none."""
    cam = obj(9, 'Camera_Leftover', superclass='camera', cls='Freecamera', faces=0, materials=[],
              mesh={'verts': [], 'tris': []}, zero_m=None)
    rows = [obj(1), obj(2, 'SM_Addr_Ground', NPM_GROUND), cam]
    for tool in ('perimeter_drop', 'material_type', 'sets_count', 'glass', 'fbx_split', 'zero_area', 'ucx_audit'):
        f, _, _ = core.run(tool, rows, audit)
        assert codes(f, 9) == [], tool
    f, _, _ = core.scene_hygiene(rows)
    assert codes(f, 9) == ['hyg_non_mesh']


def test_census_summary_and_missing_maps():
    m = dict(STD, maps=['a.png', 'b.png'], missing=['b.png'])
    f, d, s = core.census([obj(1, materials=[m], instances=2), obj(2, superclass='camera', materials=[]),
                           obj(3, bbox=((float('nan'), 0, 0), (1, 1, 1)))])
    assert codes(f, 1) == ['missing_map'] and s['missing_maps'] == ['b.png']
    assert s['by_class'] == {'camera': 1, 'geometry': 2} and s['instanced_objects'] == 1
    assert d == [{'name': 'SM_Addr_001_Main', 'reason': 'bbox not finite'}]


def test_preflight_one_table_prefixed_and_status_per_check():
    rows = [obj(1, scale=(2.0, 2.0, 2.0)), obj(2, 'SM_Addr_Ground', NPM_GROUND)]
    rep = report_of('preflight', rows)
    assert rep['status'] == 'fail' and rep['plan']['summary']['checks']['xform'] == 'fail'
    assert rep['objects'][0]['findings'][0]['detail'].startswith('qa.xform: ')
    assert sum(1 for v in rep['plan']['summary']['checks'].values() if v == 'pass') == len(core.PREFLIGHT)  # + units


# ---- qa.preflight includes scene.units (#882) -----------------------------------------------------------
def test_preflight_includes_scene_units_d5():
    """#882 / D5: a centimetre scene with clean objects fails preflight on a scene-level scene.units row."""
    rows = [obj(1), obj(2, 'SM_Addr_Ground', NPM_GROUND)]
    ok = report_of('preflight', rows)
    assert ok['status'] == 'pass' and ok['plan']['summary']['checks']['units'] == 'pass'
    assert set(ok['plan']['summary']['checks']) == set(core.PREFLIGHT) | {'units'}
    assert [f['name'] for f in ok['plan']['findings']] == [
        'scene.units: ' + n for n in ('system_unit', 'system_scale', 'file_in_gamma', 'file_out_gamma')]
    cm = report_of('preflight', rows, dict(METRE_SCENE, unit_type='centimeters'))
    assert cm['status'] == 'fail' and cm['plan']['summary']['checks']['units'] == 'fail'
    assert all(not o['findings'] for o in cm['objects'])  # objects are clean: only the scene row fails
    assert cm['plan']['path'] == 'C:/s.max'
    table = model.rows(runtime.parse_report(json.dumps(cm)))
    bad = [r for r in table if not r.ok]
    assert [(r.name, r.code) for r in bad] == [('s.max', 'scene.units: system_unit')]
    assert 'centimeters' in bad[0].detail and len([r for r in table if r.ok]) == 2


def test_preflight_without_scene_raises():
    """Fail-closed: preflight never runs (or passes) without the scene units."""
    for scene in (None, 'C:/s.max', [], 0):
        with pytest.raises(ValueError):
            core.run('preflight', [obj(1)], audit, scene=scene)
    with pytest.raises(ValueError):
        core.run('preflight', [obj(1)], audit)


def test_preflight_report_scene_rows_are_validated():
    cm = report_of('preflight', [obj(1)], dict(METRE_SCENE, unit_scale=0.01))
    with pytest.raises(ValueError):
        core.validate_report(dict(cm, status='pass'))  # claimed pass over a failing units row
    for mutate in (lambda r: r['plan'].pop('findings'), lambda r: r['plan'].pop('path'),
                   lambda r: r['plan'].__setitem__('findings', []),
                   lambda r: r['plan']['summary']['checks'].pop('units'),
                   lambda r: r['plan']['summary']['checks'].__setitem__('units', 'pass'),
                   lambda r: r['plan']['findings'][1].__setitem__('status', 'not_run'),
                   lambda r: r['plan']['findings'][1].pop('observed')):
        bad = json.loads(json.dumps(cm))
        mutate(bad)
        with pytest.raises(ValueError):
            core.validate_report(bad)
    xf = report_of('xform', [obj(1)])
    with pytest.raises(ValueError):  # object checks keep the 0.7 plan shape (no scene rows)
        core.validate_report(dict(xf, plan=dict(xf['plan'], path='x', findings=[])))


def test_preflight_status_includes_units_bruteforce():
    """invariant: preflight fails iff an object finding or a scene.units item fails; units pass iff the
    standalone scene.units check passes (400 cases, NaN/inf/None/missing/at-threshold values)."""
    rnd = random.Random(882)
    values = {'unit_type': ['meters', 'centimeters', 'millimeters', None, ''],
              'unit_scale': [1.0, 0.01, 100.0, float('nan'), float('inf'), None, 1.0 + 1e-9, 1.0 + 2e-9],
              'file_in_gamma': [1.0, 2.2, float('nan'), None, 1.0 + 1e-6, 1.0 + 2e-6],
              'file_out_gamma': [1.0, 2.2, float('-inf'), None]}
    seen = set()
    for case in range(400):
        scene = {k: rnd.choice(v) for k, v in values.items()}
        if rnd.random() < 0.4:
            scene = dict(METRE_SCENE)
        scene['path'] = 'C:/s.max'
        if rnd.random() < 0.1:
            scene.pop(rnd.choice(list(values)))
        rows = [obj(k + 1, scale=(rnd.choice([1.0, 1.0, 1.0, 2.0]),) * 3) for k in range(rnd.randint(1, 4))]
        rows.append(obj(len(rows) + 1, 'SM_Addr_Ground', NPM_GROUND))
        f, d, s = core.run('preflight', rows, audit, scene=scene)
        rep = core.report('preflight', rows, f, d, s)
        units_ok = all(x['status'] == 'pass' for x in core.units(scene))
        assert rep['plan']['summary']['checks']['units'] == ('pass' if units_ok else 'fail'), case
        obj_bad = any(o['findings'] for o in rep['objects'])
        assert rep['status'] == ('fail' if obj_bad or not units_ok else 'pass'), case
        assert runtime.parse_report(json.dumps(rep)) == rep
        seen.add((units_ok, obj_bad))
    assert seen == {(True, True), (True, False), (False, True), (False, False)}


def test_suite_max_passes_scene_units_to_preflight(monkeypatch):
    """The Max glue reads the scene units for preflight (fake runtime, no pymxs)."""
    import types
    sm = _load('suite_max.py', 'agr_tools_suite_max_test882')
    rt = types.SimpleNamespace(units=types.SimpleNamespace(SystemType='centimeters', SystemScale=1.0),
                               fileInGamma=1.0, fileOutGamma=1.0, maxFilePath='C:/w/', maxFileName='a.max',
                               select=lambda nodes: None)
    monkeypatch.setattr(sm, '_rt', lambda: rt)
    monkeypatch.setattr(sm, 'targets', lambda agr, nodes: ['n1'])
    monkeypatch.setattr(sm, '_row', lambda agr, glue, n, scale: obj(1))
    agr = types.SimpleNamespace(_unit_m=lambda: 1.0, _load_core=lambda *a: audit)
    rep = sm.run(agr, None, core, 'preflight')
    assert rep['status'] == 'fail' and rep['plan']['summary']['checks']['units'] == 'fail'
    assert rep['plan']['path'].endswith('a.max')


# ---- fail-closed contract -----------------------------------------------------------------------------
@pytest.mark.parametrize('tool', [t for t in core.TOOLS if t != 'units'])
def test_empty_duplicate_partial_rows_raise(tool):
    with pytest.raises(ValueError):
        core.run(tool, [], audit, scene=dict(METRE_SCENE))
    with pytest.raises(ValueError):
        core.run(tool, [obj(1), obj(1)], audit, scene=dict(METRE_SCENE))
    partial = obj(1)
    for field in ('materials', 'mesh', 'superclass', 'faces', 'instances', 'animated', 'modifiers', 'mirror'):
        partial.pop(field)
    if tool != 'fbx_split':  # fbx_split reads only key/name/fbx
        with pytest.raises(ValueError):
            core.run(tool, [partial], audit, scene=dict(METRE_SCENE))


def test_unknown_check_and_bad_reports_raise():
    with pytest.raises(KeyError):
        core.run('nope', [obj(1)], audit)
    rep = report_of('xform', [obj(1, scale=(2, 2, 2))])
    with pytest.raises(ValueError):
        core.validate_report(dict(rep, status='pass'))  # claimed pass with findings
    bad = json.loads(json.dumps(rep))
    bad['objects'][0]['findings'][0]['code'] = 'invented'
    with pytest.raises(ValueError):
        core.validate_report(bad)
    with pytest.raises(ValueError):
        core.validate_report(dict(rep, objects=[]))
    with pytest.raises(ValueError):
        core.scene_report('units', 'x', [])
    assert runtime.parse_report(json.dumps(rep)) == rep  # runtime routes 0.7 tools to suite_core


def test_every_input_row_ends_in_the_report_bruteforce():
    """invariant: every input object is in the report exactly once, in order, status derived (200 cases)."""
    rnd = random.Random(860)
    for case in range(200):
        n = rnd.randint(1, 12)
        rows = []
        for k in range(n):
            rows.append(obj(k + 1, scale=(rnd.choice([1.0, 1.0, 2.0]),) * 3, parent=rnd.choice([None, None, 'P']),
                            zero_m=rnd.choice([0.0, -1.0, -3.0, None]), animated=rnd.random() < 0.2))
        tool = rnd.choice(core.PREFLIGHT + ('preflight',))
        rep = report_of(tool, rows)
        assert [o['handle'] for o in rep['objects']] == [r['key'] for r in rows], case
        assert rep['status'] == ('fail' if any(o['findings'] for o in rep['objects']) else 'pass')


def test_glue_never_edits_the_scene_d6():
    """D6: the 0.7 glue reads snapshots only; no reset, collapse, convert, delete of nodes, save or export."""
    text = (PKG / 'suite_max.py').read_text(encoding='utf-8')
    for banned in ('resetXForm', 'collapseStack', 'convertTo', 'saveMaxFile', 'exportFile', 'maxOps.CollapseNode',
                   'addModifier', 'deleteModifier'):
        assert banned not in text, banned
    assert text.count('rt.delete(') == 2 and text.count('rt.snapshotAsMesh(') == 2  # only the in-memory snapshots


# ---- «Путь» / rail / GUIDE --------------------------------------------------------------------------
def test_suite_json_validates_and_rejects_gaps():
    suite = roadmap.load_file(SUITE)
    assert [b['id'] for b in suite['blocks']] == ['scene', 'model', 'tex', 'ucx', 'udim', 'atlas', 'place', 'qa',
                                                 'export', 'light']
    broken = json.loads(SUITE.read_text(encoding='utf-8'))
    del broken['blocks'][3]['when_ru']
    with pytest.raises(ValueError, match='when_ru'):
        roadmap.load(json.dumps(broken))
    broken = json.loads(SUITE.read_text(encoding='utf-8'))
    broken['rows'][0]['block'] = 'nowhere'
    with pytest.raises(ValueError, match='nowhere'):
        roadmap.load(json.dumps(broken))
    broken = json.loads(SUITE.read_text(encoding='utf-8'))
    broken['rows'].append(dict(broken['rows'][0]))
    with pytest.raises(ValueError, match='duplicate'):
        roadmap.load(json.dumps(broken))


def test_flow_tooltips_and_cards_from_json():
    suite = roadmap.load_file(SUITE)
    nodes = roadmap.flow(suite, model.VERSION)
    assert [n['number'] for n in nodes] == list(range(10))
    assert sum(n['total'] for n in nodes) == len(suite['rows']) == 97  # 90 + 7 new rows of the team-scripts audit
    assert sum(n['done'] for n in nodes) == 13 + 12 + 13  # 0.1-0.5 + 0.7 + 0.8
    for r in suite['rows']:
        tip = roadmap.tooltip(suite, r)
        assert r['does_ru'] in tip and r['reqs'] in tip and 'Когда:' in tip
        c = roadmap.card(suite, r, model.VERSION)
        assert set(c) == {'title', 'what', 'when', 'input', 'result', 'mode', 'reqs', 'state', 'block', 'related',
                          'why'}
        assert c['state'] == ('есть в этой версии' if roadmap.vkey(r['version']) <= roadmap.vkey(model.VERSION)
                              else 'в версии ' + r['version'])
    assert roadmap.vkey('1.x') > roadmap.vkey('1.0') > roadmap.vkey('0.9') > roadmap.vkey('0.7.0')


def test_live_status_and_next_step_fail_closed():
    suite = roadmap.load_file(SUITE)
    status = roadmap.live_status(suite, {}, model.VERSION)
    assert status['scene'] == 'not_run' and status['light'] == 'planned' and status['place'] == 'planned'
    assert status['export'] == 'no_checks'  # cleanup/export ship as actions, not read-only checks
    assert roadmap.next_step(suite, status) == ('0 Сцена и источник: запустить проверки', 'scene')
    ok = {'schema': 1, 'status': 'pass'}
    reports = {'scene.census': ok, 'scene.units': ok}
    status = roadmap.live_status(suite, reports, model.VERSION)
    assert status['scene'] == 'ok' and roadmap.next_step(suite, status)[1] == 'model'
    for bad in ({'status': 'review'}, {'status': 'fail'}, {}, None, 'pass'):
        st = roadmap.live_status(suite, {'scene.census': ok, 'scene.units': bad}, model.VERSION)
        assert st['scene'] == 'errors', bad
    every = {r['id']: ok for r in suite['rows']}
    st = roadmap.live_status(suite, every, model.VERSION)
    assert roadmap.next_step(suite, st)[1] is None


def test_rail_maps_every_action_to_a_plan_row_and_greys_the_rest():
    suite = roadmap.load_file(SUITE)
    assert set(model.ROW) == set(model.BY_ID)
    rail = model.rail(suite['blocks'], suite['rows'])
    assert [b['id'] for b, _, _ in rail] == [b['id'] for b in suite['blocks']]
    done_rows = {model.row_of(a.id) for _, done, _ in rail for a in done}
    planned = [r for _, _, p in rail for r in p]
    assert len(done_rows) + len(planned) == 97
    assert all(roadmap.vkey(r['version']) > roadmap.vkey(model.VERSION) for r in planned)
    with pytest.raises(KeyError):
        model.row_of('nope')


@pytest.mark.parametrize('theme,window,base,text', [
    ('Dark', (68, 68, 68), (43, 43, 43), (220, 220, 220)),
    ('Light', (239, 239, 239), (255, 255, 255), (0, 0, 0)),
    ('Max2026Light', (197, 197, 197), (230, 230, 230), (20, 20, 20))])
def test_block_accents_contrast_against_window_and_base(theme, window, base, text):
    suite = roadmap.load_file(SUITE)
    seen = set()
    for b in suite['blocks']:
        c = model.block_accent(b['hue'], window, base, text)
        assert model.contrast(c, window) >= 3.0 and model.contrast(c, base) >= 3.0, (theme, b['id'])
        seen.add(c)
    assert len(seen) == 10
    with pytest.raises(ValueError):
        model.block_accent(400, window, base, text)
    with pytest.raises(ValueError):
        model.block_accent(212, (160, 160, 160), (60, 60, 60), (255, 255, 255))  # unreachable -> error


def test_guide_regeneration_gives_no_diff():
    proc = subprocess.run([sys.executable, str(ROOT / 'tools/max/build_agr_guide.py'), '--check'],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_report_memory_roundtrip(tmp_path):
    rep = report_of('xform', [obj(1)])
    path = runtime.remember(rep, str(tmp_path))
    assert Path(path).name == 'xform.json' and not Path(path + '.partial').exists()
    (tmp_path / 'broken.json').write_text('{', encoding='utf-8')
    assert runtime.last_reports(str(tmp_path)) == {'xform': rep}
    assert runtime.reports_dir('C:/a/b.max') == runtime.reports_dir('C:/a/B.max') if sys.platform == 'win32' else True


# ---- MCP -------------------------------------------------------------------------------------------------
# ---- #886 usedMaps drops a Bitmaptexture whose file is absent ---------------------------------------
class _Tok:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class _Arr(list):
    @property
    def count(self):
        return len(self)


class _MapNode:
    def __init__(self, handle, kind, name, filename=None, subtex=(), submtls=(), opacity=100.0):
        self.handle = handle
        self.kind = kind
        self.name = name
        self.filename = filename
        self.fileName = filename
        self.subtex = list(subtex)
        self.submtls = list(submtls)
        self.opacity = opacity
        self.cls = None  # filled once the runtime tokens exist


class _Rt:
    """usedMaps returns only bitmap files that exist. Absent Bitmaptexture.fileName values are omitted."""

    def __init__(self):
        self.undefined = object()
        self.Bitmaptexture = _Tok('Bitmaptexture')
        self.Multimaterial = _Tok('Multimaterial')
        self.Standardmaterial = _Tok('Standardmaterial')
        self.PhysicalMaterial = _Tok('PhysicalMaterial')
        self.Mix = _Tok('Mix')
        self.mapPaths = self

    def classOf(self, node):
        if getattr(node, 'bad_class', False):
            raise RuntimeError('classOf failed')
        return node.cls

    def getHandleByAnim(self, node):
        if getattr(node, 'bad_handle', False):
            raise RuntimeError('no handle')
        return node.handle

    def isProperty(self, node, prop):
        if getattr(node, 'bad_file', False):
            raise RuntimeError('unreadable ' + prop)
        return prop in ('filename', 'fileName') and node.cls == self.Bitmaptexture

    def getProperty(self, node, prop):
        if getattr(node, 'bad_file', False):
            raise RuntimeError('unreadable ' + prop)
        return getattr(node, prop)

    def getNumSubMtls(self, node):
        return len(node.submtls)

    def getSubMtl(self, node, index):
        return node.submtls[index - 1]

    def getNumSubTexmaps(self, node):
        if getattr(node, 'bad_tex', False):
            raise RuntimeError('texmaps unreadable')
        return len(node.subtex)

    def getSubTexmap(self, node, index):
        child = node.subtex[index - 1]
        if child == 'odd':
            raise RuntimeError('odd subtex')
        return child

    def getFullFilePath(self, path):
        return ''

    def usedMaps(self, node):
        if getattr(node, 'bad_used', False):
            raise RuntimeError('usedMaps failed')
        if getattr(node, 'odd_used', False):
            return _Arr([None])
        found = []

        def walk(n, seen):
            if n is None or n == self.undefined or n == 'odd':
                return
            if n.handle in seen:
                return
            seen.add(n.handle)
            if n.cls == self.Bitmaptexture and n.filename and os.path.isfile(n.filename):
                if n.filename not in found:
                    found.append(n.filename)
            for child in n.subtex:
                walk(child, seen)

        if not getattr(node, 'drop_present', False):
            walk(node, set())
        return _Arr(found)


def _bind_runtime():
    sm = _load('suite_max.py', 'agr_suite_max_886')
    cm = _load('checks_max.py', 'agr_checks_max_886')
    rt = _Rt()
    sm._rt = lambda: rt
    cm._rt = lambda: rt
    return sm, cm, rt


def _as_kind(rt, node):
    node.cls = getattr(rt, node.kind)
    for child in list(node.subtex) + list(node.submtls):
        if isinstance(child, _MapNode):
            _as_kind(rt, child)
    return node


def _witness_scene(tmp_path):
    """One present bitmap (usedMaps keeps it) and the polygon's absent bitmap (usedMaps drops it)."""
    sm, glue, rt = _bind_runtime()
    present = tmp_path / 'T_Polygon_007_Main_d_2.png'
    present.write_bytes(b'png')
    absent = 'C:/x/test-polygon/missing/T_Polygon_007_Main_d_1.png'
    assert not os.path.isfile(absent)
    ok = _MapNode(2, 'Bitmaptexture', 'T_ok', filename=str(present))
    gone = _MapNode(3, 'Bitmaptexture', 'T_Polygon_007_Main_d_1', filename=absent)
    mat = _MapNode(1, 'Standardmaterial', 'M_Polygon_007_Main_1', subtex=[ok, gone])
    _as_kind(rt, mat)
    node = _MapNode(10, 'Standardmaterial', 'SM_Polygon_007_Main')
    node.material = mat
    return sm, glue, node, str(present), absent


def test_census_reports_bitmap_file_usedmaps_drops(tmp_path):
    """#886: usedMaps omits Bitmaptexture fileName when the file is absent; missing_map still fires."""
    sm, glue, node, present, absent = _witness_scene(tmp_path)
    mats = sm._materials(node, glue)
    assert [m['name'] for m in mats] == ['M_Polygon_007_Main_1']
    assert mats[0]['maps'] == [present, absent]
    assert mats[0]['missing'] == [absent]
    row = obj(1, 'SM_Polygon_007_Main', materials=mats)
    found, _, summary = core.census([row])
    assert codes(found, 1) == ['missing_map']
    assert summary['missing_maps'] == [absent]
    assert [d for _, d, _ in found[1]] == ['нет файла: ' + absent]
    rep = report_of('preflight', [row])
    assert rep['status'] == 'fail'
    assert 'missing_map' in [f['code'] for f in rep['objects'][0]['findings']]


def _random_material(rnd, rt, tmp_path, seq, absent, present):
    """A Standardmaterial, or a Multimaterial of them. Bitmaps sit in slots or under a Mix."""

    def bitmap(want_absent):
        seq[0] += 1
        handle = seq[0]
        if want_absent:
            path = str(tmp_path / 'missing' / 'T_{}.png'.format(handle))
            absent.add(path)
        else:
            path = str(tmp_path / 'present' / 'T_{}.png'.format(handle))
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b'x')
            present.add(path)
        return _MapNode(handle, 'Bitmaptexture', 'Map_{}'.format(handle), filename=path)

    def standard():
        slots = []
        for _ in range(rnd.randint(0, 5)):
            roll = rnd.randrange(5)
            if roll == 0:
                slots.append(None)  # empty slot
            elif roll == 1:
                slots.append(bitmap(True))
            elif roll == 2:
                slots.append(bitmap(False))
            else:
                kids = [bitmap(rnd.random() < 0.6) for _ in range(rnd.randint(1, 3))]
                if kids and rnd.random() < 0.3:
                    kids.append(kids[0])  # same Bitmaptexture twice
                seq[0] += 1
                slots.append(_MapNode(seq[0], 'Mix', 'Mix_{}'.format(seq[0]), subtex=kids))
        slots.append(bitmap(True))  # every material has one absent file: an empty usedMaps result cannot pass
        seq[0] += 1
        mat = _MapNode(seq[0], 'Standardmaterial', 'M_{}'.format(seq[0]), subtex=slots, opacity=100.0)
        if rnd.random() < 0.5:
            mat.drop_present = True  # usedMaps returns nothing; the file check still decides
        return mat

    if rnd.random() < 0.5:
        subs = [standard() for _ in range(rnd.randint(1, 4))]
        seq[0] += 1
        top = _MapNode(seq[0], 'Multimaterial', 'Multi_{}'.format(seq[0]), submtls=subs)
    else:
        top = standard()
    return _as_kind(rt, top)


def test_absent_bitmaps_land_in_missing_once_probe(tmp_path):
    """Probe: every absent Bitmaptexture path is in `missing` once; no present path is."""
    sm, glue, rt = _bind_runtime()
    rnd = random.Random(886)
    for case in range(60):
        absent, present = set(), set()
        mat = _random_material(rnd, rt, tmp_path / str(case), [0], absent, present)
        node = _MapNode(0, 'Standardmaterial', 'SM')
        node.material = mat
        mats = sm._materials(node, glue)
        listed = []
        for m in mats:
            assert m['missing'] == list(dict.fromkeys(m['missing']))
            assert set(m['missing']).isdisjoint(present)
            if m['cls'] == 'Multimaterial':
                assert m['maps'] == [] and m['missing'] == []
            listed.extend(m['missing'])
        found, _, summary = core.census([obj(1, materials=mats)])
        assert set(listed) == absent, case
        assert summary['missing_maps'] == sorted(absent)
        assert len(found.get(1, [])) == len(absent)
        assert len({d for _, d, _ in found.get(1, [])}) == len(absent)
        assert absent  # each trial has a missing file, so an empty usedMaps result cannot pass


def test_odd_maps_and_unmapped_materials_fail_closed_probe(tmp_path):
    """Probe: a broken texmap or a material that cannot be read raises, naming it; it does not pass."""
    sm, glue, rt = _bind_runtime()
    rnd = random.Random(8861)
    for case in range(40):
        absent, present = set(), set()
        mat = _random_material(rnd, rt, tmp_path / str(case), [0], absent, present)
        node = _MapNode(0, 'Standardmaterial', 'SM')
        node.material = mat
        bitmaps = []

        def collect(n, seen):
            if not isinstance(n, _MapNode) or n.handle in seen:
                return
            seen.add(n.handle)
            if n.kind == 'Bitmaptexture':
                bitmaps.append(n)
            for child in n.subtex + n.submtls:
                collect(child, seen)

        collect(mat, set())
        target = rnd.choice(bitmaps)
        fault = rnd.choice(('bad_file', 'odd', 'bad_tex', 'bad_used', 'odd_used', 'empty_glue'))
        if fault == 'bad_file':
            target.bad_file = True
            name = target.name
        elif fault == 'odd':
            owners = [mat]
            def owners_of(n):
                for child in n.subtex:
                    if child is target or (isinstance(child, _MapNode) and target in getattr(child, 'subtex', [])):
                        owners.append(n)
                    if isinstance(child, _MapNode):
                        owners_of(child)
            owners_of(mat)
            host = rnd.choice([o for o in owners if isinstance(o, _MapNode)])
            host.subtex = list(host.subtex) + ['odd']
            name = host.name
        elif fault == 'bad_tex':
            mat.bad_tex = True
            name = mat.name
        elif fault == 'bad_used':
            mat.bad_used = True
            name = mat.name
        elif fault == 'odd_used':
            mat.odd_used = True
            name = mat.name
        else:
            class Empty:
                def _materials(self, material):
                    return []

                def _resolve(self, path):
                    return path
            glue_i = Empty()
            with pytest.raises(ValueError, match=mat.name):
                sm._materials(node, glue_i)
            continue
        with pytest.raises(ValueError, match=name):
            sm._materials(node, glue)


def test_census_map_fields_fail_closed_and_report_once_probe():
    """Probe: odd map entries and a material without map fields raise, naming it; duplicates once."""
    rnd = random.Random(8862)
    for case in range(40):
        paths = ['missing_{}_{}.png'.format(case, i) for i in range(rnd.randint(1, 5))]
        dup = paths + list(reversed(paths))
        present = ['ok_{}_{}.png'.format(case, i) for i in range(rnd.randint(0, 3))]
        row_m = dict(STD, name='M_case_{}'.format(case), maps=present + paths, missing=dup)
        found, _, summary = core.census([obj(1, materials=[row_m, dict(row_m)]),
                                         obj(2, materials=[dict(row_m)])])
        assert summary['missing_maps'] == sorted(paths)
        assert len(found[1]) == len(paths) and len(found[2]) == len(paths)
        odd = rnd.choice([None, '', '  ', 3, b'x.png'])
        broken = dict(STD, name='M_odd_{}'.format(case), maps=[odd], missing=[])
        with pytest.raises(ValueError, match='M_odd_{}'.format(case)):
            core.census([obj(1, materials=[broken])])
        unnamed = {'cls': 'Standardmaterial', 'opacity': 1.0}
        with pytest.raises(ValueError, match='unmapped material'):
            core.census([obj(1, materials=[unnamed])])


def test_mcp_registers_the_12_checks_read_only():
    from agr_mcp import tools
    from agr_mcp.max_side import max_bridge
    cat = tools.catalog()
    names = [n for n, _ in tools.CHECKS_070]
    assert len(names) == 12 and set(names) <= set(tools.PHASE0) and set(names) <= set(cat)
    for n in names:
        assert cat[n].read_only and not cat[n].destructive
    assert set(max_bridge.CHECKS_070) == set(names)
    assert set(max_bridge.CHECKS_070.values()) == set(core.TOOLS)
    suite = roadmap.load_file(SUITE)
    for n, tool in max_bridge.CHECKS_070.items():
        r = roadmap.row(suite, core.PLAN_ROW[tool])
        assert n == 'agr_' + r['id'].replace('.', '_') and r['mcp'] == 'yes'
