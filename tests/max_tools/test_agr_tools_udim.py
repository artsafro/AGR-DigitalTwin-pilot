"""new-case: AGR Tools 0.8 (#908) branch C: udim.ids_to_udims core (udim_core.py), plain pytest.

Each defect of docs/experiments/udim.ids_to_udims.md (L02, job 20261104-230526-0211c2c4) is RED on a behaviour
model of GeoAGR IDs->UDIMs (`GeoAGR.ms:35920-36001`, written from the measurements, no GeoAGR code, #853) and
GREEN on udim_core. The acceptance scene of L02 is rebuilt as plain meshes.
"""
import importlib.util
import math
import sys
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


uc = _load('udim_core.py', 'agr_tools_udim_core_t')
ec = _load('edit_core.py', 'agr_tools_edit_core_udim_t')


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


class Mesh:
    """Quads with their own 3D rectangle and UV rectangle; optional shared UV corners."""

    def __init__(self):
        self.m = {'vertices': [], 'uvs': [], 'faces': [], 'face_uvs': [], 'ids': []}

    def quad(self, mid, x, y, w, h, u, v, uw, vh, z=0.0):
        m = self.m
        b = len(m['vertices'])
        m['vertices'] += [(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)]
        t = len(m['uvs'])
        m['uvs'] += [(u, v), (u + uw, v), (u + uw, v + vh), (u, v + vh)]
        m['faces'].append([b, b + 1, b + 2, b + 3])
        m['face_uvs'].append([t, t + 1, t + 2, t + 3])
        m['ids'].append(mid)
        return self


def acceptance():
    """L02: IDs 1, 2 (two islands, one outside 0..1), 7 non-square, 11, 25, 101, zero-extent 5; object 2 has ID 4."""
    a = (Mesh().quad(1, 0, 0, 1, 1, 0.1, 0.1, 0.3, 0.3)
         .quad(2, 2, 0, 1, 1, 0.0, 0.0, 0.2, 0.2).quad(2, 4, 0, 1, 1, 1.5, 1.2, 0.2, 0.2)
         .quad(7, 0, 3, 4, 1, 0.2, 0.2, 0.8, 0.2).quad(11, 0, 5, 1, 1, 0.5, 0.5, 0.1, 0.1)
         .quad(25, 0, 7, 2, 2, 0.3, 0.3, 0.4, 0.4).quad(101, 0, 9, 1, 1, 0.6, 0.6, 0.2, 0.2)
         .quad(5, 0, 11, 1, 1, 0.4, 0.4, 0.0, 0.0)).m
    b = Mesh().quad(4, 0, 0, 2, 1, 0.0, 0.0, 0.5, 0.25).m
    return [a, b]


def tiles_ok(mesh_after, ids=None):
    bad = uc.readback_outside(mesh_after)
    if ids is not None:
        bad = [f for f in bad if mesh_after['ids'][f - 1] in ids]
    return not bad


# ---- source behaviour model (L02 measurements) ------------------------------------------------------------
def source_layout(meshes, scale=0.95):
    """First object only; IDs 1..100 fitted per ID to `scale` and centred in 1000+ID; ID > 100 untouched;
    a zero-extent group divides by zero (NaN)."""
    out = [dict(m, uvs=list(m['uvs'])) for m in meshes]
    m = out[0]
    for mid in sorted(set(m['ids'])):
        if mid > 100:
            continue
        faces = [f for f, i in enumerate(m['ids']) if i == mid]
        idx = sorted({i for f in faces for i in m['face_uvs'][f]})
        us = [m['uvs'][i][0] for i in idx]
        vs = [m['uvs'][i][1] for i in idx]
        ext = max(max(us) - min(us), max(vs) - min(vs))
        s = scale / ext if ext else float('nan')
        cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
        u0, v0 = (mid - 1) % 10, (mid - 1) // 10
        for i in idx:
            u, v = m['uvs'][i]
            m['uvs'][i] = ((u - cu) * s + u0 + 0.5, (v - cv) * s + v0 + 0.5)
    return out


def impl_layout(meshes, mode='fit', scale=0.95):
    scales = uc.plan_scales(meshes, mode, scale)
    out = []
    for mi, m in enumerate(meshes):
        uvs, fuv = uc.layout(m, scales, mi)
        out.append(dict(m, uvs=uvs, face_uvs=fuv))
    return out, scales


# ---- regressions ---------------------------------------------------------------------------------------------
def test_d1_every_selected_object_is_laid_out():
    meshes = acceptance()
    red_green(lambda out: tiles_ok(out[1]), lambda: source_layout(meshes), lambda: impl_layout(meshes)[0])


def test_d2_ids_outside_1_100_are_refused_and_reported():
    meshes = acceptance()
    # the source keeps ID 101 silently in tile 1001, on top of ID 1 (no record of the refusal)
    src = source_layout(meshes)[0]
    assert uc.face_tile(src['uvs'], src['face_uvs'][6]) == 1001
    out, scales = impl_layout(meshes)
    assert scales[(0, 101)]['status'] == 'rejected' and '101' in scales[(0, 101)]['reason']
    rows = {r['id']: r for r in uc.id_rows(meshes[0], scales, 0, after=(out[0]['uvs'], out[0]['face_uvs']))}
    assert rows[101]['status'] == 'rejected' and rows[101]['sits_in'] == [1001] and rows[101]['tile'] is None
    assert out[0]['uvs'][out[0]['face_uvs'][6][0]] == meshes[0]['uvs'][meshes[0]['face_uvs'][6][0]]  # UVs kept
    with pytest.raises(ValueError):
        uc.tile_of_id(0)
    with pytest.raises(ValueError):
        uc.tile_of_id(101)


def test_d3_zero_extent_group_is_skipped_without_nan():
    meshes = acceptance()
    def finite(out):
        return all(math.isfinite(c) for m in out for p in m['uvs'] for c in p)
    red_green(finite, lambda: source_layout(meshes), lambda: impl_layout(meshes)[0])
    _, scales = impl_layout(meshes)
    assert scales[(0, 5)]['status'] == 'zero_extent' and 'zero extent' in scales[(0, 5)]['reason']
    _, tex = impl_layout(meshes, 'texel')
    assert tex[(0, 5)]['status'] == 'zero_extent'


def test_d4_texel_mode_keeps_one_uv_to_3d_ratio_within_1_percent():
    meshes = acceptance()
    a = meshes[0]  # without the zero-extent ID 5 (the source turns it into NaN, see D3)
    meshes[0] = {k: (v[:-1] if k in ('faces', 'face_uvs', 'ids') else v) for k, v in a.items()}

    def spread(out):
        rows = []
        for mi, (m, o) in enumerate(zip(meshes, out)):
            g = uc.measure(o)
            rows += [g[mid]['uv_area'] / g[mid]['area3'] for mid in g if 1 <= mid <= 100 and mid != 5]
        return (max(rows) - min(rows)) / max(rows)
    red_green(lambda out: spread(out) <= 0.01, lambda: source_layout(meshes)[:1] + impl_layout(meshes)[0][1:],
              lambda: impl_layout(meshes, 'texel')[0])
    out, scales = impl_layout(meshes, 'texel')
    assert tiles_ok(out[0], set(range(1, 101)) - {5}) and tiles_ok(out[1])
    # the limiting ID fills `scale` of its tile, no group exceeds it
    for (mi, mid), s in scales.items():
        if s['status'] == 'placed':
            b = uc.measure(out[mi])[mid]['bbox']
            assert max(b[2] - b[0], b[3] - b[1]) <= 0.95 + 1e-9


def test_d6_shared_uv_vertices_are_split_per_id():
    m = Mesh().quad(1, 0, 0, 1, 1, 0.0, 0.0, 0.5, 0.5).quad(2, 1, 0, 1, 1, 0.5, 0.0, 0.5, 0.5).m
    m['face_uvs'][1] = [1, 4, 5, 2]  # share the edge of face 1
    out, _ = impl_layout([m])
    assert tiles_ok(out[0]) and len(out[0]['uvs']) > len(set(i for f in m['face_uvs'] for i in f)) - 1
    assert uc.face_tile(out[0]['uvs'], out[0]['face_uvs'][0]) == 1001
    assert uc.face_tile(out[0]['uvs'], out[0]['face_uvs'][1]) == 1002


def test_acceptance_fit_mode_every_face_inside_its_tile():
    meshes = acceptance()
    out, scales = impl_layout(meshes)
    for mi, m in enumerate(out):
        rows = uc.id_rows(meshes[mi], scales, mi, after=(m['uvs'], m['face_uvs']))
        for r in rows:
            if r['status'] == 'placed':
                assert r['outside_tile'] == [] and r['tile'] == 1000 + r['id']
    assert {k[1] for k, s in scales.items() if s['status'] == 'placed'} == {1, 2, 4, 7, 11, 25}
    m = out[0]
    t = {mid: uc.face_tile(m['uvs'], m['face_uvs'][f]) for f, mid in enumerate(m['ids'])}
    assert t[1] == 1001 and t[2] == 1002 and t[7] == 1007 and t[11] == 1011 and t[25] == 1025
    # aspect kept: ID 7 stays 4:1 (0.8 x 0.2) and is fitted to 0.95 on its long side
    b = uc.measure(m)[7]['bbox']
    assert math.isclose(b[2] - b[0], 0.95) and math.isclose(b[3] - b[1], 0.95 / 4)


def test_tile_numbering_is_standard_udim():
    assert uc.tile_origin(1001) == (0, 0) and uc.tile_origin(1010) == (9, 0) and uc.tile_origin(1011) == (0, 1)
    assert uc.tile_of_uv(9.5, 9.5) == 1100 and uc.tile_of_uv(10.2, 0.1) is None and uc.tile_of_uv(-0.1, 0.5) is None


def test_options_and_input_are_checked():
    meshes = acceptance()
    for bad in (0, -1, 1.5, True, 'x'):
        with pytest.raises(ValueError):
            uc.plan_scales(meshes, 'fit', bad)
    with pytest.raises(ValueError):
        uc.plan_scales(meshes, 'pack')
    broken = dict(meshes[1], uvs=[(float('nan'), 0.0)] + meshes[1]['uvs'][1:])
    with pytest.raises(ValueError):
        uc.measure(broken)


def test_report_rows_fit_the_edit_contract():
    meshes = acceptance()
    out, scales = impl_layout(meshes, 'texel')
    rows = uc.id_rows(meshes[0], scales, 0, after=(out[0]['uvs'], out[0]['face_uvs']))
    rep = ec.report('udim.ids_to_udims', 'preview', [ec.entry(1, 'Obj', [ec.finding('udim_id_out_of_range', [7])])],
                    done=[r for r in rows if r['status'] == 'placed'], skipped_=[ec.skipped('Obj ID 101', 'outside 1..100')],
                    state_hash=ec.fingerprint(meshes), extra={'per_object': rows})
    assert rep['status'] == 'fail' and ec.check_preview('udim.ids_to_udims', rep) is rep
    assert uc.texel_spread(rows) <= 0.01


def test_glue_module_loads_without_pymxs():
    um = _load('udim_max.py', 'agr_tools_udim_max_t')
    assert callable(um.udim_ids_to_udims) and um.LAYER == 'AGR_export_udim'
