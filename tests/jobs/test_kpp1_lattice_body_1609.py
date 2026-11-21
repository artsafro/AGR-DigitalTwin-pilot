"""KPP1 lattice body input + check (#1609 step 2, BM-00; Artem 2026-11-21: every level a closed ring)."""
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/KPP1/lattice-1609'
sys.path.insert(0, str(D))


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_1609', D / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


li = _load('lattice_input')
lc = _load('lattice_check')


def line_list(extra_open=()):
    ext = {'S': [-0.33, 27.33], 'N': [-0.33, 27.33], 'W': [-0.33, 11.33], 'E': [-0.33, 11.33]}
    plane = {'S': -0.33, 'N': 11.33, 'W': -0.33, 'E': 27.33}
    F = {}
    for f in 'SNWE':
        u0, u1 = ext[f]
        st = [u0, u1]
        ops = []
        for g, r in extra_open:
            if g == f:
                st += r[:2]
                ops.append({'kind': 'door', 'id': len(ops), 'rect': r, 'rect_lattice': r})
        F[f] = {'plane': plane[f], 'extent': [u0, u1, 0.0, 8.65], 'u_axis': 'x' if f in 'SN' else 'y',
                'stations': [{'u': u, 'kept': True} for u in sorted(st)], 'openings': ops}
    return {'levels': [{'z': z, 'kept': True} for z in (0.0, 2.1, 8.65)], 'facades': F}


def test_ring_perimeter_and_side_order():
    lat = li.build(line_list([('E', [5.0, 6.0, 0.0, 2.1]), ('W', [2.0, 3.0, 0.0, 2.1])]))
    assert lat['perimeter'] == pytest.approx(2 * (27.66 + 11.66))
    assert lat['corners_s'] == [0.0, 27.66, 39.32, 66.98]
    assert 27.66 + 5.33 in [pytest.approx(s) for s in lat['stations_s']]  # E u = y up from S
    w = [o for o in lat['openings'] if o['facade'] == 'W'][0]  # W runs y down: u 2..3 -> s from N end
    assert w['s0'] == pytest.approx(66.98 + 11.33 - 3.0) and w['s1'] == pytest.approx(66.98 + 11.33 - 2.0)
    assert lat['summary']['per_side'] == {'S': 2, 'E': 4, 'N': 2, 'W': 4}


def test_shift_moves_ring_only():
    a, b = li.build(line_list()), li.build(line_list(), (-14.655, -5.355))
    assert b['rings'][0]['xy'][0] == [pytest.approx(-14.985), pytest.approx(-5.685)]
    assert a['stations_s'] == b['stations_s'] and a['levels'] == b['levels']


@pytest.mark.parametrize('mut, msg', [
    (lambda d: d['facades'].pop('E'), 'missing'),
    (lambda d: d['facades'].update(X={}), 'unknown facade'),
    (lambda d: d['facades']['S'].update(plane=float('nan')), 'finite'),
    (lambda d: d['facades']['S']['extent'].__setitem__(1, 20.0), 'does not span'),
    (lambda d: d['facades']['S']['extent'].__setitem__(3, 7.0), 'differs from the levels'),
    (lambda d: d['facades']['S']['stations'].append({'u': 40.0, 'kept': True}), 'outside its side'),
    (lambda d: d.update(levels=[{'z': 0.0, 'kept': True}]), 'levels'),
    (lambda d: d['facades']['S']['openings'].append({'id': 9, 'rect_lattice': [3.0, 4.0, 0.0, 1.0]}), 'not on kept'),
    (lambda d: d['facades']['S']['openings'].append({'id': 9, 'rect_lattice': [3.0, 4.0, 0.0, 2.1]}), 'not a station'),
])
def test_input_fail_closed(mut, msg):
    d = line_list()
    mut(d)
    with pytest.raises(ValueError, match=msg):
        li.build(d)


def box(lat, cut_level=None, diag=False, drop_side=None):
    """Unit lattice body: one quad per cell at depth 0 (optionally a level missing on one side, a diagonal split)."""
    segs, P = lc.ring_frame(lat)
    S = list(lat['stations_s'])
    Z = list(lat['levels'])
    V, faces, key = [], [], {}

    def at(s):
        k = max(i for i, g in enumerate(segs) if g[0] <= s + 1e-9)
        s0, L, p, t, n = segs[k]
        return p + t * (s - s0)

    def v(s, z):
        q = at(s % P)
        k = (round(q[0], 4), round(q[1], 4), round(z, 4))
        if k not in key:
            key[k] = len(V)
            V.append([q[0], q[1], z])
        return key[k]
    St = S + [P]
    for i in range(len(S)):
        side = max(k for k, g in enumerate(segs) if g[0] <= St[i] + 1e-9)
        if drop_side == side:
            continue
        zs = [z for z in Z if not (cut_level is not None and side == 0 and abs(z - cut_level) < 1e-9)]
        for j in range(len(zs) - 1):
            a, b, c, d = v(St[i], zs[j]), v(St[i + 1], zs[j]), v(St[i + 1], zs[j + 1]), v(St[i], zs[j + 1])
            if diag and i == 0 and j == 0:
                faces += [[a, b, c], [a, c, d]]
            else:
                faces.append([a, b, c, d])
    fn = [len(f) for f in faces]
    return np.array(V, float), np.array(fn), np.array([x for f in faces for x in f])


def test_check_closed_box_all_rings_and_stations():
    lat = li.build(line_list([('S', [5.0, 6.0, 0.0, 2.1])]))
    r = lc.check(*box(lat), lat)
    sm = r['summary']
    assert sm['levels_closed'] == sm['levels'] == 3 and sm['stations_through'] == sm['stations']
    assert sm['cells_with_defects'] == 0 and sm['tris'] == 0


def test_check_level_dying_at_a_corner_is_open_and_t_vertices_flagged():
    lat = li.build(line_list())
    r = lc.check(*box(lat, cut_level=2.1), lat)
    lv = {x['z']: x for x in r['levels']}
    assert not lv[2.1]['closed'] and lv[2.1]['gaps_s'] == [[0.0, 27.66]]
    assert lv[0.0]['closed'] and lv[8.65]['closed']
    assert r['summary']['t_vertices'] >= 1 and r['summary']['cells_with_defects'] >= 1


def test_check_missing_facade_breaks_every_ring_and_diagonal_is_a_defect():
    lat = li.build(line_list())
    r = lc.check(*box(lat, drop_side=1), lat)
    assert r['summary']['levels_closed'] == 0
    r = lc.check(*box(lat, diag=True), lat)
    assert r['summary']['tris'] == 2 and r['summary']['diagonal_edges'] == 1 and r['summary']['cells_with_defects'] == 1


def test_check_probe_random_lattices_closed():
    """Generated probe: 60 random line lists; a lattice-built box always closes every ring and station."""
    rnd = random.Random(1609)
    for seed in range(60):
        ops = []
        for f, L in (('S', 27.33), ('E', 11.33), ('N', 27.33), ('W', 11.33)):
            u = -0.33 + rnd.uniform(0.3, 2.0)
            while u < L - 2.0:
                w = rnd.uniform(0.5, 1.5)
                ops.append((f, [round(u, 3), round(u + w, 3), 0.0, 2.1]))
                u += w + rnd.uniform(0.3, 3.0)
        lat = li.build(line_list(ops))
        sm = lc.check(*box(lat), lat)['summary']
        assert sm['levels_closed'] == sm['levels'] and sm['stations_through'] == sm['stations'], seed
        assert sm['cells_with_defects'] == 0, seed


@pytest.mark.parametrize('bad', ['empty', 'nan', 'far'])
def test_check_fail_closed(bad):
    lat = li.build(line_list())
    V, fn, fi = box(lat)
    if bad == 'empty':
        V, fn, fi = np.zeros((0, 3)), np.array([], int), np.array([], int)
    elif bad == 'nan':
        V[0, 0] = np.nan
    else:
        V = V + [0.0, 0.0, 100.0]
    with pytest.raises(ValueError):
        lc.check(V, fn, fi, lat)


def test_cli_refuses_alias_and_writes_atomically(tmp_path):
    src = tmp_path / 'll.json'
    src.write_text(json.dumps(line_list()), encoding='utf-8')
    before = src.read_bytes()
    r = subprocess.run([sys.executable, str(D / 'lattice_input.py'), str(src), str(src)], capture_output=True, text=True)
    assert r.returncode != 0 and 'aliases' in r.stdout + r.stderr and src.read_bytes() == before
    out = tmp_path / 'lat.json'
    r = subprocess.run([sys.executable, str(D / 'lattice_input.py'), str(src), str(out), '--shift', '1', '2'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text(encoding='utf-8'))['shift'] == [1.0, 2.0]
    assert not (tmp_path / 'lat.json.partial').exists()
