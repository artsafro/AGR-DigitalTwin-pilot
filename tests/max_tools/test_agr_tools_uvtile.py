"""new-case: AGR Tools 0.9 (#979) branch B: udim.slots and udim.matid_unwrap cores (uvtile_core.py), plain pytest.

udim.slots: acceptance of #979 §4 (gap 1003, 101 maps, slots 1/2/4, clean set). Names are read by names_core (E1).
udim.matid_unwrap: each defect of docs/experiments/udim.matid_unwrap.md (L06, jobs 20261105-125541-261291c9,
20261105-125724-29647441) is RED on a behaviour model of `Maf Tools.mcr` (sha256 df1a3a3e…fa05; written from the
measurements, no team code, #853) and GREEN on uvtile_core. The L06 MAF (MatID 1, 2, 7, 12, 40) is rebuilt as boxes.
"""
import importlib.util
import math
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


uv = _load('uvtile_core.py', 'agr_tools_uvtile_core_t')


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


# ---- udim.slots ---------------------------------------------------------------------------------------------
def files(addr, mp, slot, tiles, ground=False):
    g = '_Ground' if ground else ''
    return ['C:/maps/T_{}{}_{}_{}.{}.png'.format(addr, g, mp, slot, t) for t in tiles]


def codes_of(plan):
    return {name: sorted({c for c, _ in f}) for _, name, f in plan['entries']}


def test_parse_by_names_core_grammar():
    p = uv.parse_texture('C:/x/T_Tverskaya_12_Diffuse_2.1007.png')
    assert (p['model'], p['address'], p['map'], p['slot'], p['udim']) == ('vpm', 'Tverskaya_12', 'Diffuse', 2, 1007)
    g = uv.parse_texture('T_Addr_Ground_ERM_1.1001.png')
    assert g['ground'] and g['map'] == 'ERM'
    n = uv.parse_texture('T_Addr_001_Main_d_1.png')
    assert (n['model'], n['oks'], n['type'], n['map']) == ('npm', '001', 'Main', 'd')
    assert uv.parse_texture('T_Addr_Diffuse_9.1001.png')['slot'] == 9
    for bad in ('Wood_diffuse.png', 'T_Addr_Diffuse_1.png', 'T_Addr_Albedo_1.1001.png', 'T_Addr_Diffuse_1.1101.png'):
        assert isinstance(uv.parse_texture(bad), str), bad


def test_slots_acceptance():
    clean = files('A', 'Diffuse', 1, range(1001, 1006)) + files('A', 'ERM', 1, range(1001, 1006)) + \
        files('A', 'Diffuse', 2, [1001])
    gap = files('B', 'Diffuse', 1, [1001, 1002, 1004, 1005])
    over = ['C:/m/T_C_{}_1.{}.png'.format(mp, t) for mp in ('Diffuse', 'ERM', 'Normal') for t in range(1001, 1035)]
    slots = files('D', 'Diffuse', 1, [1001]) + files('D', 'Diffuse', 2, [1001]) + files('D', 'Diffuse', 4, [1001])
    eight = files('E', 'Diffuse', 1, [1001]) + [f for s in range(2, 9) for f in files('E', 'Diffuse', s, [1001])]
    plan = uv.slots_plan([
        {'key': 1, 'name': 'SM_A_Main', 'files': clean},
        {'key': 2, 'name': 'SM_B_Main', 'files': gap},
        {'key': 3, 'name': 'SM_C_Main', 'files': over},
        {'key': 4, 'name': 'SM_D_Main', 'files': slots},
        {'key': 5, 'name': 'SM_E_Main', 'files': eight},
        {'key': 6, 'name': 'SM_F_Main', 'files': ['C:/m/wood.png']},
    ])
    got = codes_of(plan)
    assert got == {'SM_A_Main': [], 'SM_B_Main': ['udim_gap'], 'SM_C_Main': ['maps_over_100'],
                   'SM_D_Main': ['slot_gap'], 'SM_E_Main': ['slot_over_7'], 'SM_F_Main': ['name_unparsed']}
    detail = [d for _, n, f in plan['entries'] if n == 'SM_B_Main' for _, d in f][0]
    assert 'miss 1003' in detail


def test_slots_empty_input_is_an_error():
    with pytest.raises(ValueError):
        uv.slots_plan([{'key': 1, 'name': 'SM_A_Main', 'files': []}])


# ---- udim.matid_unwrap: synthetic MAF --------------------------------------------------------------------------
def box(mesh, size, origin, mid, scale=1.0):
    sx, sy, sz = (s * scale for s in size)
    ox, oy, oz = (o * scale for o in origin)
    base = len(mesh['vertices'])
    for z in (0, sz):
        for x, y in ((0, 0), (sx, 0), (sx, sy), (0, sy)):
            mesh['vertices'].append((ox + x, oy + y, oz + z))
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for q in quads:
        mesh['faces'].append([base + i for i in q])
        mesh['ids'].append(mid)


def maf(scale=1.0):
    m = {'vertices': [], 'faces': [], 'ids': []}
    for k, (mid, size) in enumerate(zip((1, 2, 7, 12, 40), ((0.5, 0.5, 0.8), (1.2, 0.4, 0.4), (0.3, 0.3, 2.0),
                                                            (2.0, 1.0, 0.1), (0.8, 0.8, 0.8)))):
        box(m, size, (k * 3.0, 0, 0), mid, scale)
    return m


def maf_model(mesh):
    """Maf Tools as measured: every ID normalised into its tile with a 0.02 UV margin (no common density); the
    packer stacks islands in one column with gap 0.005 UV across UDIM borders."""
    groups, _ = uv.unwrap_groups(mesh, 1.0)
    dens = {}
    for mid, isl in groups.items():
        rects = [(i['w'], i['h']) for i in isl]
        side = math.sqrt(sum(w * h for w, h in rects)) * 1.6
        scale = (1 - 2 * 0.02) / side
        dens[mid] = scale * 1024
    column, y = [], 0.0
    for mid, isl in sorted(groups.items()):
        for i in isl:
            s = dens[mid] / 1024
            column.append((mid, y, y + i['h'] * s))
            y += i['h'] * s + 0.005
    return dens, column


def spread(values):
    values = list(values)
    return (max(values) - min(values)) / max(values)


def test_density_is_one_px_per_m_for_every_id():
    """L06 defect 2: per-ID normalisation, density x2 between IDs."""
    mesh = maf()
    plan = uv.unwrap_plan(mesh, 1.0)
    red_green(lambda s: s <= 0.05,
              lambda: spread(maf_model(mesh)[0].values()),
              lambda: spread(r['px_per_m_after'] for r in plan['rows']))
    for r in plan['rows']:
        assert abs(r['px_per_m_after'] - plan['px_per_m']) <= uv.DENSITY_TOL * plan['px_per_m']


def test_every_id_in_its_own_tile_inside_borders_no_overlap():
    """L06 defect 4: the packer crosses UDIM borders and loses ID -> tile."""
    mesh = maf()
    plan = uv.unwrap_plan(mesh, 1.0)

    def model_inside():
        _, column = maf_model(mesh)
        return all(math.floor(y0) == math.floor(y1 - 1e-12) for _, y0, y1 in column)
    red_green(lambda ok: ok, model_inside,
              lambda: plan['ok'] and all(not r['outside_tile'] for r in plan['rows']))
    assert {r['id']: r['tiles_after'] for r in plan['rows']} == {1: [1001], 2: [1002], 7: [1007], 12: [1012], 40: [1040]}
    assert uv.overlaps(plan['uvs'], plan['face_uvs']) == []
    assert [c for c, _, _ in plan['findings']] == []


def test_padding_at_least_8_px_between_islands_and_borders():
    mesh = maf()
    plan = uv.unwrap_plan(mesh, 1.0, map_px=1024, pad_px=8)
    gap = 8 / 1024.0
    by_id = {}
    for f, mid in enumerate(mesh['ids']):
        by_id.setdefault(mid, []).append(f)
    for mid, faces in by_id.items():
        u0, v0 = uv.tile_origin(uv.tile_of_id(mid))
        pts = [plan['uvs'][i] for f in faces for i in plan['face_uvs'][f]]
        assert min(p[0] for p in pts) >= u0 + gap - 1e-9 and max(p[0] for p in pts) <= u0 + 1 - gap + 1e-9
        assert min(p[1] for p in pts) >= v0 + gap - 1e-9 and max(p[1] for p in pts) <= v0 + 1 - gap + 1e-9
    with pytest.raises(ValueError):
        uv.unwrap_plan(mesh, 1.0, pad_px=6)


def test_metres_and_centimetres_give_the_same_px_per_m():
    m = uv.unwrap_plan(maf(1.0), 1.0, px_per_m=200.0)
    cm = uv.unwrap_plan(maf(100.0), 0.01, px_per_m=200.0)
    assert m['ok'] and cm['ok']
    for a, b in zip(m['rows'], cm['rows']):
        assert abs(a['px_per_m_after'] - b['px_per_m_after']) <= 0.01 * a['px_per_m_after']
        assert abs(a['px_per_m_after'] - 200.0) <= 0.02 * 200.0


def test_overflow_is_a_finding_with_the_calculation_and_no_layout():
    plan = uv.unwrap_plan(maf(), 1.0, px_per_m=5000.0)
    assert not plan['ok'] and plan['uvs'] is None
    over = [d for c, _, d in plan['findings'] if c == 'tile_overflow']
    assert over and 'fits up to' in over[0] and 'px/m' in over[0]


def test_ids_outside_1_100_are_refused():
    mesh = maf()
    mesh['ids'] = [101 if i == 40 else i for i in mesh['ids']]
    plan = uv.unwrap_plan(mesh, 1.0)
    assert [c for c, _, _ in plan['findings']] == ['id_out_of_range'] and plan['uvs'] is None


def test_5000_polygons_under_5_seconds():
    m = {'vertices': [], 'faces': [], 'ids': []}
    n = 50
    for j in range(n + 1):
        for i in range(n + 1):
            m['vertices'].append((i * 0.1, j * 0.1, math.sin(i * 0.3) * 0.05))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            m['faces'].append([a, a + 1, a + n + 2, a + n + 1])
            m['ids'].append(1 + (i * 5) // n)
    for k in range(2500):  # second sheet -> 5000 polygons
        f = m['faces'][k]
        m['faces'].append([v for v in reversed(f)])
        m['ids'].append(12)
    t0 = time.time()
    plan = uv.unwrap_plan(m, 1.0)
    assert time.time() - t0 < 5.0
    assert plan['ok'], plan['findings']
