"""KPP1 lattice line list from the Revit openings/zones census (#1609 restart, BM-00, Artem 2026-11-21 dec. 2-3).

Pattern: n/a | new-case: tests of jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py `lines` (was line_list.py).
"""
import copy
import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('line_list_1609', ROOT / 'jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py')
ll = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ll)
SCRIPT = ROOT / 'jobs/KPP1/lattice-1609/hooks/kpp1_lattice.py'

BANDS = [{'z0': -1.0, 'z1': 0.9, 'finish': 'plinth'}, {'z0': 0.9, 'z1': 2.7, 'finish': 'grey'},
         {'z0': 2.7, 'z1': 7.1, 'finish': 'blue'}, {'z0': 7.1, 'z1': 9.0, 'finish': 'top'}]


def wall(name, f, u0, u1, z0, z1, off=0.0):
    """Wall bbox on facade f (KPP1 frame: x -0.33..27.33, y -0.33..11.33); off > 0 = outside the plane."""
    if f == 'S':
        return {'name': name, 'min': [u0, -0.33 - off, z0], 'max': [u1, -0.22 - off, z1]}
    if f == 'N':
        return {'name': name, 'min': [u0, 11.22 + off, z0], 'max': [u1, 11.33 + off, z1]}
    if f == 'E':
        return {'name': name, 'min': [27.22 + off, u0, z0], 'max': [27.33 + off, u1, z1]}
    return {'name': name, 'min': [-0.33 - off, u0, z0], 'max': [-0.22 - off, u1, z1]}


def base(extra_walls=(), spec=None):
    walls = []
    for f, L in (('S', 27.33), ('N', 27.33), ('W', 11.33), ('E', 11.33)):
        walls += [wall('plinth %s_%s' % (f, 'a' * 7), f, -0.33, L, -0.72, 0.9),
                  wall('slice1 %s_%s' % (f, 'b' * 7), f, -0.33, L, 0.9, 2.7),
                  wall('slice2 %s_%s' % (f, 'c' * 7), f, -0.33, L, 2.7, 7.1),
                  wall('slice3 %s_%s' % (f, 'd' * 7), f, -0.33, L, 7.1, 8.1),
                  wall('slice4 %s_%s' % (f, 'e' * 7), f, -0.33, L, 8.1, 8.65)]
    walls += list(extra_walls)
    sp = spec or {f: {'surrounds': [], 'doors': [], 'portals': [], 'features': [], 'grilles': []} for f in 'WSNE'}
    return sp, walls


def kept_z(res):
    return [r['z'] for r in res['levels'] if r['kept']]


def kept_u(res, f):
    return [r['u'] for r in res['facades'][f]['stations'] if r['kept']]


def test_openings_and_finish_lines():
    sp, w = base()
    sp['S']['surrounds'].append({'id': 1, 'rect': [2.0, 5.0, 1.125, 3.075]})
    sp['S']['doors'].append({'name': 'door', 'rect': [8.0, 9.0, 0.0, 2.1]})
    res = ll.plan(sp, w, bands=BANDS)
    assert kept_z(res) == [0.0, 0.9, 1.125, 2.1, 2.7, 3.075, 7.1, 8.65]
    assert [d['value'] for d in res['dropped']] == [8.1]  # stacked-wall split inside one finish = texture
    assert kept_u(res, 'S') == [-0.33, 2.0, 5.0, 8.0, 9.0, 27.33]
    assert kept_u(res, 'W') == [-0.33, 11.33]


def test_facade_e_in_scope_its_door_levels_are_global_rings():
    """Artem 2026-11-21: every level is a closed ring around W, S, N AND E; E openings make lines too."""
    sp, w = base()
    sp['E']['doors'].append({'name': 'door E', 'rect': [5.68, 6.98, 3.9, 6.0]})
    res = ll.plan(sp, w, bands=BANDS)
    assert 3.9 in kept_z(res) and 6.0 in kept_z(res)
    assert kept_u(res, 'E') == [-0.33, 5.68, 6.98, 11.33]
    assert res['facades']['E']['u_axis'] == 'y' and res['facades']['E']['plane'] == 27.33
    assert not any('facade E' in i['reason'] for i in res['ignored'])
    assert set(res['summary']['stations_kept']) == {'W', 'S', 'N', 'E'}


def test_without_bands_wall_instances_are_zones():
    sp, w = base()
    res = ll.plan(sp, w)
    assert 8.1 in kept_z(res)


def test_snap_moves_smaller_opening_edge_and_reports_it():
    sp, w = base()
    sp['S']['surrounds'].append({'id': 7, 'rect': [0.305, 5.315, 4.775, 6.725]})
    sp['S']['doors'].append({'name': 'door', 'rect': [0.4, 1.6, 0.0, 2.1]})
    res = ll.plan(sp, w, bands=BANDS)
    assert 0.4 not in kept_u(res, 'S') and 0.305 in kept_u(res, 'S')
    mv = res['facades']['S']['moved']
    assert len(mv) == 1 and mv[0]['from'] == 0.4 and mv[0]['to'] == 0.305 and mv[0]['delta_m'] == pytest.approx(-0.095)
    door = [o for o in res['facades']['S']['openings'] if o['kind'] == 'door'][0]
    assert door['rect'] == [0.4, 1.6, 0.0, 2.1] and door['rect_lattice'][0] == 0.305


def test_exactly_at_snap_merges_and_just_above_does_not():
    sp, w = base()
    sp['S']['surrounds'].append({'id': 1, 'rect': [3.0, 6.0, 4.0, 6.0]})
    sp['S']['doors'].append({'name': 'd', 'rect': [3.1, 4.0, 0.0, 2.1]})  # exactly 0.10 from 3.0
    assert 3.1 not in kept_u(ll.plan(sp, w, bands=BANDS), 'S')
    sp['S']['doors'][0]['rect'][0] = 3.1001
    assert 3.1001 in kept_u(ll.plan(sp, w, bands=BANDS), 'S')


def test_neighbour_clusters_never_end_closer_than_snap():
    # chain 0.0(opening big) .. 0.1 .. 0.15: first cluster {2.0, 2.1} -> 2.1 (largest), next 2.15 -> merge
    sp, w = base()
    sp['S']['surrounds'].append({'id': 1, 'rect': [2.1, 6.0, 1.0, 3.0]})
    sp['S']['doors'].append({'name': 'a', 'rect': [2.0, 2.05, 0.0, 0.5]})  # tiny -> would collapse
    with pytest.raises(ValueError, match='collapses'):
        ll.plan(sp, w, bands=BANDS)
    sp['S']['doors'][0]['rect'] = [2.0, 3.5, 0.0, 0.5]
    sp['S']['grilles'] = []
    sp['S']['surrounds'].append({'id': 2, 'rect': [2.25, 2.9, 4.0, 5.0]})
    res = ll.plan(sp, w, bands=BANDS)
    us = kept_u(res, 'S')
    assert all(b - a > 0.1 for a, b in zip(us, us[1:])), us


def test_reason_rule_short_zone_is_texture_exactly_at_threshold_kept():
    sp, w = base([wall('panel S_ffffff1', 'S', 10.0, 11.0, 1.2, 2.2)])  # 1.0 m patch: borders change < 1.5
    res = ll.plan(sp, w)
    assert 10.0 not in kept_u(res, 'S') and 1.2 not in kept_z(res)
    sp, w = base([wall('panel S_ffffff1', 'S', 10.0, 11.5, 1.2, 2.7)])  # exactly 1.5 m: kept
    res = ll.plan(sp, w)
    assert 10.0 in kept_u(res, 'S') and 1.2 in kept_z(res)


def test_corner_post_gap_is_not_a_station():
    sp, w = base()
    for o in w:
        if o['name'].startswith('slice2 S'):
            o['max'][0] = 27.22  # 11 cm short: corner post
    res = ll.plan(sp, w, bands=BANDS)
    assert 27.22 not in kept_u(res, 'S')
    z = [z for z in res['facades']['S']['zones'] if z['name'].startswith('slice2')][0]
    assert 'extended' in z
    for o in w:
        if o['name'].startswith('slice2 S'):
            o['max'][0] = 27.1  # 23 cm: a real zone border, not a post gap
    res = ll.plan(sp, w)
    assert 27.1 in kept_u(res, 'S')


def test_outside_walls_and_frames_are_not_body():
    sp, w = base([wall('canopy S_1234567', 'S', 7.6, 11.4, 2.7, 3.3, off=1.06)])
    sp['S']['portals'].append({'id': 9, 'rect': [8.0, 11.0, 0.9, 2.7]})
    sp['S']['grilles'].append([1.0, 1.4, 3.0, 3.4])
    res = ll.plan(sp, w, bands=BANDS)
    kinds = sorted(n['kind'] for n in res['facades']['S']['not_body'])
    assert kinds == ['grille', 'portal', 'wall']
    assert 7.6 not in kept_u(res, 'S') and 8.0 not in kept_u(res, 'S') and 3.3 not in kept_z(res)


def test_every_wall_is_accounted():
    sp, w = base([wall('canopy S_1234567', 'S', 7.6, 11.4, 2.7, 3.3, off=1.06),
                  {'name': 'east_abcdef0', 'min': [27.0, 2.0, 0.0], 'max': [27.33, 3.0, 1.0]}])
    res = ll.plan(sp, w, bands=BANDS)
    named = {z['name'] for F in res['facades'].values() for z in F['zones']}
    named |= {n['name'] for F in res['facades'].values() for n in F['not_body'] if n['kind'] == 'wall'}
    named |= {i['what'] for i in res['ignored']}
    assert named == {o['name'] for o in w}


@pytest.mark.parametrize('mut, msg', [
    (lambda sp, w: sp.clear(), 'empty'),
    (lambda sp, w: w.clear(), 'empty'),
    (lambda sp, w: sp.pop('N'), 'missing'),
    (lambda sp, w: sp.pop('E'), 'facade E missing'),
    (lambda sp, w: sp['S'].update(bays=[]), 'unknown keys'),
    (lambda sp, w: sp.update(X={}), 'unknown facade'),
    (lambda sp, w: sp['S']['surrounds'].append({'id': 1, 'rect': [1.0, float('nan'), 1.0, 2.0]}), 'finite'),
    (lambda sp, w: sp['S']['surrounds'].append({'id': 1, 'rect': [1.0, float('inf'), 1.0, 2.0]}), 'finite'),
    (lambda sp, w: sp['S']['surrounds'].append({'id': 1, 'rect': [2.0, 1.0, 1.0, 2.0]}), 'reversed'),
    (lambda sp, w: sp['S']['doors'].append({'name': 'd', 'rect': [1.0, 2.0, 1.0]}), 'expected'),
    (lambda sp, w: sp['S']['surrounds'].append({'id': 1, 'rect': [26.0, 28.5, 1.0, 2.0]}), 'outside the body'),
    (lambda sp, w: w.append(dict(w[0])), 'duplicate'),
    (lambda sp, w: w[0].update(min=[0.0, -0.33, float('nan')]), 'finite'),
    (lambda sp, w: [w.remove(o) for o in list(w) if o['name'][-9] == 'W' or o['name'].split()[1][0] == 'W'],
     'no wall on facade W'),
])
def test_fail_closed_inputs(mut, msg):
    sp, w = base()
    mut(sp, w)
    with pytest.raises(ValueError, match=msg):
        ll.plan(sp, w, bands=BANDS)


@pytest.mark.parametrize('kw, msg', [
    ({'snap': 0.0}, 'snap'), ({'snap': -0.1}, 'snap'), ({'snap': float('nan')}, 'finite'),
    ({'min_reason': -1.0}, 'min_reason'), ({'bands': []}, 'empty'),
    ({'bands': [{'z0': 0, 'z1': 1, 'finish': 'a'}, {'z0': 1.5, 'z1': 9, 'finish': 'b'}]}, 'contiguous'),
    ({'bands': [{'z0': 1.0, 'z1': 9, 'finish': 'b'}]}, 'no finish band'),
    ({'bands': [{'z0': 0, 'z1': 9, 'finish': ''}]}, 'finish name'),
])
def test_fail_closed_params(kw, msg):
    sp, w = base()
    with pytest.raises(ValueError, match=msg):
        ll.plan(sp, w, **kw)


def test_probe_random_facades_invariants():
    """Generated probe: 300 seeds. Opening edges end on kept lines, lines > snap apart, inputs not mutated."""
    rnd = random.Random(1609)
    n_ok = 0
    for seed in range(300):
        sp, w = base()
        for f, L in (('S', 27.33), ('N', 27.33), ('W', 11.33), ('E', 11.33)):
            u = -0.33 + rnd.uniform(0.2, 1.0)
            while u < L - 2.5:
                wd = rnd.uniform(0.6, 2.0)
                kind = rnd.choice(['door', 'surround', 'surround'])
                z0, z1 = (0.0, 2.1) if kind == 'door' else (round(rnd.uniform(0.95, 1.3), 3), round(rnd.uniform(2.8, 3.1), 3))
                r = [round(u, 3), round(u + wd, 3), z0, z1]
                if kind == 'door':
                    sp[f]['doors'].append({'name': 'd', 'rect': r})
                else:
                    sp[f]['surrounds'].append({'id': seed * 100 + len(sp[f]['surrounds']), 'rect': r})
                u += wd + rnd.uniform(0.12, 2.0)
        before = copy.deepcopy((sp, w))
        res = ll.plan(sp, w, bands=BANDS)
        assert (sp, w) == before
        zs = kept_z(res)
        assert all(b - a > 0.1 for a, b in zip(zs, zs[1:]))
        for f in 'WSNE':
            us = kept_u(res, f)
            assert all(b - a > 0.1 for a, b in zip(us, us[1:]))
            for o in res['facades'][f]['openings']:
                r = o['rect_lattice']
                assert r[0] in us and r[1] in us and r[2] in zs and r[3] in zs, (seed, f, o)
                tag = '%s %s' % (o['kind'], o['id'])
                mv = {m['edge']: m for m in res['facades'][f]['moved'] if m['opening'] == tag}
                for k, (a, b) in enumerate(zip(r, o['rect'])):
                    e = ('u0', 'u1', 'z0', 'z1')[k]
                    assert abs(a - b) < 1e-9 or (e in mv and abs(mv[e]['to'] - a) < 1e-9
                                                 and abs(mv[e]['from'] - b) < 1e-9), (seed, f, tag, e)
        over = sum(abs(m['delta_m']) > 0.1 + 1e-6 for F in res['facades'].values() for m in F['moved'])
        assert res['summary']['moves_over_snap'] == over
        n_ok += 1
    assert n_ok == 300


def test_cli_atomic_and_refuses_alias(tmp_path):
    sp, w = base()
    a, b, bd = tmp_path / 'spec.json', tmp_path / 'walls.json', tmp_path / 'bands.json'
    a.write_text(json.dumps(sp), encoding='utf-8')
    b.write_text(json.dumps(w), encoding='utf-8')
    bd.write_text(json.dumps({'bands': BANDS}), encoding='utf-8')
    snap = {p: p.read_bytes() for p in (a, b, bd)}
    for out in (a, b, bd):
        r = subprocess.run([sys.executable, str(SCRIPT), 'lines', str(a), str(b), str(out), '--bands', str(bd)],
                           capture_output=True, text=True)
        assert r.returncode != 0 and 'aliases' in (r.stderr + r.stdout)
    assert {p: p.read_bytes() for p in (a, b, bd)} == snap
    out = tmp_path / 'out.json'
    r = subprocess.run([sys.executable, str(SCRIPT), 'lines', str(a), str(b), str(out), '--bands', str(bd)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text(encoding='utf-8'))
    assert d['params']['zone_class'] == 'finish band' and len(d['inputs']) == 3
    assert not (tmp_path / 'out.json.partial').exists()
    assert math.isclose(d['summary']['levels_kept'], 5)
