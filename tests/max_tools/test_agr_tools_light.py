"""new-case: AGR Tools 0.9 `light.check` (#979, branch D): light_core judged on plain rows, no pymxs.

Every defect named for the button (issue #979 §18, lab 0.9 L05 docs/experiments/light.check.md, team-audit
T04/agr_max_check_37 and T05/light_metr) has a test that is RED on a model of the source behaviour and GREEN on
light_core. The source models below are written from the measured behaviour (no source code copied, #853):
GeoAGR Light Manager `GeoAGR.ms:56368-56414` / `:56442-56458`; agr_max_check_37.ms runLightCheck (SHA256
ead3866924bfa3bf9efe54619072e2ce810141bc8b7b914b5169f2ff600e59a2); Light_Metr.ms (SHA256
6a51ed409bb4c42eeb6eccb75fe0cfaabf1566b9438bcc717dd346e9b75e6af5).
"""
import ast
import importlib.util
import itertools
import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = sys.modules.get('agr_tools_edit_core') or _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
lc = _load(PKG / 'light_core.py', 'agr_tools_light_core_t')
OPTS = lc.light_options(None)
_ids = itertools.count(100)


# ---- scene rows ------------------------------------------------------------------------------------------
def scene(units='meters', scale=1.0):
    """A light file: one root Dummy at the origin and the lights added to it (positions in metres)."""
    s = types.SimpleNamespace(unit_m=lc.metres_per_unit(units, scale), lights=[], helpers=[])
    s.root = helper(s, 'Addr_Root')
    return s


def helper(s, name, pos=(0, 0, 0), parent=None, cls='Dummy'):
    row = {'handle': next(_ids), 'name': name, 'cls': cls, 'pos': [v / s.unit_m for v in pos],
           'parent': parent, 'hidden': False, 'frozen': False}
    s.helpers.append(row)
    return row['handle']


def light(s, name, cls, pos, parent='root', hidden=False, frozen=False):
    row = {'handle': next(_ids), 'name': name, 'cls': cls, 'pos': [v / s.unit_m for v in pos],
           'parent': s.root if parent == 'root' else parent, 'hidden': hidden, 'frozen': frozen}
    s.lights.append(row)
    return row['handle']


def run(s, opts=OPTS, ref=None):
    found, pairs, summary = lc.check(s.lights, s.helpers, s.unit_m, opts, ref)
    report = lc.light_report(ec, s.lights, s.helpers, found, pairs, summary, opts, 'state')
    return report


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


def spots_at(s, d, n=2, cls='freeSpot', kind='Spot', start=1):
    return [light(s, 'Addr_{}_{:03d}'.format(kind, start + i), cls, (i * d, 0, 2)) for i in range(n)]


# ---- source models (measured behaviour, not code) ---------------------------------------------------------
def geoagr_distance_pairs(lights, unit_m):
    """GeoAGR Check Distances GeoAGR.ms:56368-56414: thresholds 1.5 / 5.0 compared with SYSTEM units (lab L05:
    a centimetre scene misses every 1-4.9 m violation); only the first 250 of Add Selected are in the list."""
    listed = [r for r in lights][:250]
    valid = [r for r in listed if lc.kind_of(r['cls'])]
    out = []
    for a, b in itertools.combinations(valid, 2):
        lim = 1.5 if lc.kind_of(a['cls']) == lc.kind_of(b['cls']) == 'spot' else 5.0
        if lc._dist(a['pos'], b['pos']) < lim:  # system units, no metres
            out.append((a['name'], b['name']))
    return out


def light_metr_pairs(lights, unit_m, d_text='1.5', locale='ru-RU'):
    """Light_Metr.ms :39-41: D = units.decodeValue (D + "m"); on ru-RU the dot is not a decimal separator and
    "1.5m" decodes to 1.0 (T05/light_metr, measured Max 2024 and 2026). One threshold for every pair."""
    d = float(d_text) if locale == 'en-US' else float(d_text.split('.')[0])
    return [(a['name'], b['name']) for a, b in itertools.combinations(lights, 2)
            if lc._dist(a['pos'], b['pos']) * unit_m < d]


def check37_pairs(lights, unit_m):
    """agr_max_check_37.ms runLightCheck :1568-1584: Omni-Omni >= 5 and Spot-Spot >= 1.5 only (no Omni-Spot)."""
    out = []
    for kind, lim in (('omni', 5.0), ('spot', 1.5)):
        grp = [r for r in lights if lc.kind_of(r['cls']) == kind]
        out += [(a['name'], b['name']) for a, b in itertools.combinations(grp, 2) if lc._dist(a['pos'], b['pos']) < lim]
    return out


def check37_roots(helpers):
    """runLightCheck :1554: roots = every helper without parent, a light target (Targetobject) included."""
    return [h['name'] for h in helpers if h['parent'] is None]


def check37_number_ok(name):
    """checkHighLightName :456-462: number of an Omni/Spot must be 001-050."""
    return 1 <= int(name[-3:]) <= 50


def pair_names(report):
    return {tuple(sorted((p['a'], p['b']))) for p in report['plan']['pairs']}


# ---- distances: metres, strict «<», boundaries ------------------------------------------------------------
@pytest.mark.parametrize('units,scale', [('meters', 1.0), ('centimeters', 1.0), ('millimeters', 1.0),
                                         ('inches', 1.0), ('meters', 0.01)])
def test_spot_spot_boundaries_are_the_same_in_every_unit(units, scale):
    s = scene(units, scale)
    for i, d in enumerate((1.0, 1.49, 1.5, 1.51)):
        light(s, 'Addr_Spot_{:03d}'.format(2 * i + 1), 'freeSpot', (100.0 * i, 0, 2))
        light(s, 'Addr_Spot_{:03d}'.format(2 * i + 2), 'targetSpot', (100.0 * i + d, 0, 2))
    r = run(s)
    bad = {name for name, c in codes(r).items() if 'light_spot_distance' in c}
    assert bad == {'Addr_Spot_001', 'Addr_Spot_002', 'Addr_Spot_003', 'Addr_Spot_004'}
    assert [p['d_m'] for p in r['plan']['pairs']] == [1.0, 1.49]
    assert r['status'] == 'fail'


@pytest.mark.parametrize('units', ['meters', 'centimeters'])
def test_omni_any_boundaries(units):
    s = scene(units)
    light(s, 'Addr_Omni_001', 'Omnilight', (0, 0, 3))
    light(s, 'Addr_Spot_001', 'freeSpot', (4.9, 0, 3))      # Omni-Spot 4.9 -> violation
    light(s, 'Addr_Omni_002', 'Omnilight', (100, 0, 3))
    light(s, 'Addr_Omni_003', 'Omnilight', (105, 0, 3))     # Omni-Omni 5.0 -> norm
    light(s, 'Addr_Omni_004', 'Omnilight', (200, 0, 3))
    light(s, 'Addr_Omni_005', 'Omnilight', (204.9, 0, 3))   # Omni-Omni 4.9 -> violation
    r = run(s)
    assert pair_names(r) == {('Addr_Omni_001', 'Addr_Spot_001'), ('Addr_Omni_004', 'Addr_Omni_005')}
    assert all(p['code'] == 'light_omni_distance' and p['min_m'] == 5.0 for p in r['plan']['pairs'])
    assert codes(r)['Addr_Omni_002'] == codes(r)['Addr_Omni_003'] == []


def test_red_geoagr_thresholds_in_system_units_miss_a_centimetre_scene():
    s = scene('centimeters')
    spots_at(s, 1.0)  # 100 cm apart
    assert geoagr_distance_pairs(s.lights, s.unit_m) == []  # RED: lab L05, «100 см → норма (пропуск)»
    assert pair_names(run(s)) == {('Addr_Spot_001', 'Addr_Spot_002')}


def test_red_light_metr_decode_value_on_ru_ru_misses_1_2_m():
    s = scene()
    spots_at(s, 1.2)
    assert light_metr_pairs(s.lights, s.unit_m, '1.5', 'ru-RU') == []  # RED: T05, decodeValue "1.5m" = 1.0
    assert light_metr_pairs(s.lights, s.unit_m, '1.5', 'en-US') != []  # the locale changed the verdict
    assert pair_names(run(s)) == {('Addr_Spot_001', 'Addr_Spot_002')}


def test_core_never_parses_a_unit_string():
    for name in ('light_core.py', 'light_max.py'):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert 'decodeValue' not in attrs, name
    glue = {n.attr for n in ast.walk(ast.parse((PKG / 'light_max.py').read_text(encoding='utf-8')))
            if isinstance(n, ast.Attribute)}
    assert {'SystemScale', 'SystemType'} <= glue


def test_metres_per_unit_from_type_and_scale():
    assert lc.metres_per_unit('#centimeters', 1.0) == 0.01
    assert lc.metres_per_unit('meters', 0.01) == 0.01
    assert lc.metres_per_unit('inches', 2.0) == pytest.approx(0.0508)
    for bad in (('parsecs', 1.0), ('meters', 0.0), ('meters', float('nan')), ('meters', True)):
        with pytest.raises(ValueError):
            lc.metres_per_unit(*bad)


def test_target_spot_is_measured_at_the_light_three_d_and_world_positions():
    s = scene()
    light(s, 'Addr_Spot_001', 'targetSpot', (0, 0, 2))
    light(s, 'Addr_Spot_002', 'targetSpot', (2.0, 0, 2))     # sources 2 m: norm (targets are not rows)
    light(s, 'Addr_Spot_003', 'freeSpot', (50, 0, 2))
    light(s, 'Addr_Spot_004', 'freeSpot', (50, 0, 3))        # vertical 1.0 m: 3D -> violation
    r = run(s)
    assert pair_names(r) == {('Addr_Spot_003', 'Addr_Spot_004')}


def test_three_spots_one_metre_apart_give_exactly_two_pairs():
    s = scene()
    spots_at(s, 1.0, n=3)
    r = run(s)
    assert pair_names(r) == {('Addr_Spot_001', 'Addr_Spot_002'), ('Addr_Spot_002', 'Addr_Spot_003')}
    assert r['plan']['summary']['pairs_checked'] == 3


# ---- types ----------------------------------------------------------------------------------------------
def test_invalid_types_are_reported_and_omni_spot_pairs_still_checked():
    s = scene()
    light(s, 'Addr_Omni_001', 'Omnilight', (0, 0, 3))
    light(s, 'Addr_Omni_002', 'Omnilight', (1, 0, 3))
    for i, cls in enumerate(('Free_Light', 'Directionallight', 'Skylight', 'VRayLight')):
        light(s, 'Addr_Photo_{}'.format(i), cls, (0.5, 0.1 * i, 3))
    r = run(s)
    c = codes(r)
    assert all(c['Addr_Photo_{}'.format(i)] == ['light_type'] for i in range(4))
    assert pair_names(r) == {('Addr_Omni_001', 'Addr_Omni_002')}  # the invalid ones never cancel the pair check
    assert r['plan']['summary']['invalid_type'] == 4 and r['plan']['summary']['lights'] == 6


# ---- count and no 250 truncation --------------------------------------------------------------------------
def test_250_is_the_limit_and_251_fails_on_the_extra_light():
    s = scene()
    for i in range(250):
        light(s, 'Addr_Omni_{:03d}'.format(i + 1), 'Omnilight', (10.0 * (i % 20), 10.0 * (i // 20), 3))
    assert run(s)['status'] == 'pass'
    light(s, 'Addr_Omni_251', 'Omnilight', (500, 500, 3))
    r = run(s)
    assert [n for n, c in codes(r).items() if c] == ['Addr_Omni_251'] and codes(r)['Addr_Omni_251'] == ['light_count']
    assert r['plan']['summary']['lights'] == 251 and r['status'] == 'fail'


def test_red_geoagr_add_selected_truncates_at_250_and_misses_later_pairs():
    s = scene()
    for i in range(258):
        light(s, 'Addr_Omni_{:03d}'.format(i + 1), 'Omnilight', (10.0 * (i % 20), 10.0 * (i // 20), 3))
    light(s, 'Addr_Spot_001', 'freeSpot', (1000, 0, 2))
    light(s, 'Addr_Spot_002', 'freeSpot', (1001, 0, 2))     # light no. 260: violating pair after the cap
    assert geoagr_distance_pairs(s.lights, s.unit_m) == []  # RED: lab L05, «Add Selected при 254 → 250, молча»
    r = run(s)
    assert ('Addr_Spot_001', 'Addr_Spot_002') in pair_names(r)
    assert r['plan']['summary']['pairs_checked'] == 260 * 259 // 2


def test_hidden_lights_count_and_hidden_offenders_are_not_selected():
    s = scene()
    light(s, 'Addr_Spot_001', 'freeSpot', (0, 0, 2))
    light(s, 'Addr_Spot_002', 'freeSpot', (1, 0, 2), hidden=True)
    light(s, 'Addr_Spot_003', 'freeSpot', (0, 30, 2), frozen=True)
    r = run(s)
    names = [o['name'] for o in r['objects']]
    assert 'Addr_Spot_002' not in names and 'Addr_Spot_003' not in names
    assert codes(r)['Addr_Spot_001'] == ['light_spot_distance']
    assert [(a['item'], a['flags'], a['codes']) for a in r['plan']['ambiguous']] == [
        ('Addr_Spot_002', ['hidden'], ['light_spot_distance'])]
    assert r['plan']['summary']['lights'] == 3


# ---- root and pivot (VPM-2.15-8 / 9.b) --------------------------------------------------------------------
def test_light_without_root_and_parent_not_a_dummy():
    s = scene()
    mesh = helper(s, 'Addr_Lamp', cls='Point')
    nested = helper(s, 'Addr_Sub', parent=s.root)
    light(s, 'Addr_Omni_001', 'Omnilight', (0, 0, 3), parent=None)
    light(s, 'Addr_Omni_002', 'Omnilight', (20, 0, 3), parent=mesh)
    light(s, 'Addr_Omni_003', 'Omnilight', (40, 0, 3), parent=nested)
    light(s, 'Addr_Omni_004', 'Omnilight', (60, 0, 3))
    c = codes(run(s))
    assert c['Addr_Omni_001'] == c['Addr_Omni_002'] == c['Addr_Omni_003'] == ['light_no_root']
    assert c['Addr_Omni_004'] == [] and c['Addr_Root'] == []


def test_two_roots_and_root_pivot_off_the_reference():
    s = scene()
    other = helper(s, 'Addr2_Root', pos=(3, 0, 0))
    light(s, 'Addr_Omni_001', 'Omnilight', (0, 0, 3))
    light(s, 'Addr2_Omni_001', 'Omnilight', (20, 0, 3), parent=other)
    c = codes(run(s))
    assert c['Addr_Root'] == ['light_root_many']
    assert c['Addr2_Root'] == ['light_root_many', 'light_root_pivot']


def test_root_pivot_against_a_reference_object_in_metres():
    s = scene('centimeters')
    s.helpers[0]['pos'] = [1000.0, 0.0, 0.0]  # root at 10 m
    light(s, 'Addr_Omni_001', 'Omnilight', (12, 0, 3))
    assert codes(run(s))['Addr_Root'] == ['light_root_pivot']                       # origin reference
    assert codes(run(s, lc.light_options({'reference': 'SM_Addr_Main'}), ref=[1000.0, 0.0, 0.05]))['Addr_Root'] == []
    assert codes(run(s, lc.light_options({'reference_point': [10.0, 0.0, 0.0]})))['Addr_Root'] == []


def test_red_check37_counts_a_light_target_as_a_second_root():
    s = scene()
    light(s, 'Addr_Spot_001', 'targetSpot', (0, 0, 3))
    target = s.helpers + [{'handle': 999, 'name': 'Addr_Spot_001.Target', 'cls': 'Targetobject', 'pos': [0, 0, 0],
                           'parent': None, 'hidden': False, 'frozen': False}]
    assert len(check37_roots(target)) == 2  # RED: «ровно 1 корневой helper» fails on every Target Spot file
    assert codes(run(s))['Addr_Root'] == []  # the glue reads only the parents of the lights as helpers


# ---- names: masks, no 050 cap --------------------------------------------------------------------------
def test_red_check37_number_cap_050_is_gone():
    s = scene()
    light(s, 'Addr_Omni_051', 'Omnilight', (0, 0, 3))
    assert not check37_number_ok('Addr_Omni_051')  # RED: T04 measured FP on Addr_Omni_051
    assert codes(run(s))['Addr_Omni_051'] == []


def test_name_masks_and_type_mismatch():
    s = scene()
    light(s, 'Addr_Spot_001', 'Omnilight', (0, 0, 3))
    light(s, 'Addr_Omni_000', 'Omnilight', (20, 0, 3))
    light(s, 'lamp', 'freeSpot', (40, 0, 3))
    c = codes(run(s))
    assert c == {'Addr_Root': [], 'Addr_Spot_001': ['light_name'], 'Addr_Omni_000': ['light_name'],
                 'lamp': ['light_name']}
    g = scene()
    g.helpers[0]['name'] = 'Addr_Ground_Root'
    light(g, 'Addr_Ground_Spot_001', 'freeSpot', (0, 0, 3))
    assert codes(run(g, lc.light_options({'ground': True}))) == {'Addr_Ground_Root': [], 'Addr_Ground_Spot_001': []}


def test_red_check37_never_checks_omni_spot_pairs():
    s = scene()
    light(s, 'Addr_Omni_001', 'Omnilight', (0, 0, 3))
    light(s, 'Addr_Spot_001', 'freeSpot', (4.9, 0, 3))
    assert check37_pairs(s.lights, s.unit_m) == []  # RED: Omni ↔ any is 5 m (GeoAGR.ms:56401), check37 skips it
    assert pair_names(run(s)) == {('Addr_Omni_001', 'Addr_Spot_001')}


# ---- report contract ------------------------------------------------------------------------------------
def test_report_is_a_select_preview_with_every_pair_in_metres_and_utf8():
    s = scene('centimeters')
    spots_at(s, 1.0)
    r = run(s)
    assert r['tool'] == 'light.check' and r['plan']['mode'] == 'preview' and r['plan']['read_only']
    assert r['plan']['pairs'] == [{'a': 'Addr_Spot_001', 'b': 'Addr_Spot_002', 'kinds': ['spot', 'spot'],
                                   'd_m': 1.0, 'min_m': 1.5, 'code': 'light_spot_distance'}]
    assert r['plan']['units'] == 'm' and r['plan']['thresholds_m'] == {'omni_any': 5.0, 'spot_spot': 1.5,
                                                                       'strict': '<'}
    text = json.dumps(r, ensure_ascii=False)
    assert 'м < 1.5 м' in text and json.loads(text.encode('utf-8').decode('utf-8')) == r
    ec.validate_report(r)
    offenders = [o['handle'] for o in r['objects'] if o['findings']]
    assert len(offenders) == 2


def test_empty_light_set_is_an_error_not_a_pass():
    s = scene()
    with pytest.raises(ValueError, match='no lights'):
        run(s)


def test_options_are_validated():
    for bad in ({'nope': 1}, {'reference': ''}, {'reference_point': [0, 0]}, {'ground': 'yes'},
                {'reference': 'A', 'reference_point': [0, 0, 0]}, {'reference_point': [0, 0, math.inf]}):
        with pytest.raises(ValueError):
            lc.light_options(bad)


def test_glue_never_recolours_or_moves():
    src = (PKG / 'light_max.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    stores = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)]
    assert stores == []  # Light_Metr set wirecolor outside undo (T05); the check assigns nothing
    assert 'select' not in {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
