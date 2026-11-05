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


# ---- #979 rework: «keep the layout» (UDIM Tool v9.2 idea, T02/udim_tool_v92 card) ---------------------------
# Team script `UDIM_Tool_new.mzp` sha256 ded25b7f71c9f717971d7ac70756a38f7baf198f846063045a7996ddae96e1cd: ideas
# only (#853). The model below is written from the T02 measurements and notes (clamp D2, V7, V8), not its code.
def source_v92_keep(m):
    """v9.2 ID -> UDIM All: per map vertex its faces (IDs 1..100 only, V8) are grouped by target tile; each group
    takes the offset of its FIRST face (V7), offset = target origin - origin of the CLAMPED centroid tile (D2)."""
    uvs = [tuple(p) for p in m['uvs']]
    fuv = [list(f) for f in m['face_uvs']]

    def clamp_origin(idx):
        cu = sum(uvs[i][0] for i in idx) / len(idx)
        cv = sum(uvs[i][1] for i in idx) / len(idx)
        t = min(max(1001 + math.floor(cu) + 10 * math.floor(cv), 1001), 1100)
        return uc.tile_origin(t)
    offsets = {}
    for f, mid in enumerate(m['ids']):
        if 1 <= mid <= 100:
            o = clamp_origin(m['face_uvs'][f])
            t = uc.tile_origin(1000 + mid)
            offsets[f] = (t[0] - o[0], t[1] - o[1], 1000 + mid)
    vert_faces = {}
    for f in offsets:
        for i in m['face_uvs'][f]:
            vert_faces.setdefault(i, []).append(f)
    new = list(uvs)
    for i, faces in vert_faces.items():
        groups = {}
        for f in faces:
            groups.setdefault(offsets[f][2], []).append(f)
        for k, (tile, members) in enumerate(groups.items()):
            du, dv, _ = offsets[members[0]]
            p = (uvs[i][0] + du, uvs[i][1] + dv)
            if k == 0:
                new[i] = p
            else:
                new.append(p)
                for f in members:
                    fuv[f] = [len(new) - 1 if j == i else j for j in fuv[f]]
    return dict(m, uvs=new, face_uvs=fuv)


def keep(meshes):
    return impl_layout(meshes, mode='keep')


def face_uv(m, f):
    return [tuple(round(c, 9) for c in m['uvs'][i]) for i in m['face_uvs'][f]]


def fractions_kept(before, after, faces):
    """Every corner moved by the same whole-tile offset per face: the layout inside the tile is unchanged."""
    for f in faces:
        d = {(round(a[0] - b[0], 9), round(a[1] - b[1], 9)) for a, b in zip(face_uv(after, f), face_uv(before, f))}
        if len(d) != 1 or any(abs(x - round(x)) > 1e-9 for x in next(iter(d))):
            return False
    return True


def test_e2_d9_negative_uvs_floor_not_clamp():
    """T02: the clamp 1001..1100 shifts a layout with negative UVs by one tile (v9.2 neguv: cons 0)."""
    m = Mesh().quad(3, 0, 0, 1, 1, -0.8, 0.2, 0.6, 0.6).quad(3, 1, 0, 1, 1, -0.9, -0.7, 0.3, 0.3).m
    red_green(lambda out: tiles_ok(out) and fractions_kept(m, out, [0, 1]),
              lambda: source_v92_keep(m), lambda: keep([m])[0][0])
    out = keep([m])[0][0]
    assert face_uv(out, 0)[0] == (2.2, 0.2) and face_uv(out, 1)[0] == (2.1, 0.3)  # floor(-0.8) = -1


def test_e2_d10_v7_result_does_not_depend_on_face_order():
    """T02 V7: a vertex shared by faces in two cells with one target takes the first face's offset."""
    a = [(0.5, 0.2), (1.0, 0.2), (1.0, 0.8), (0.5, 0.8)]
    b = [(1.0, 0.2), (1.5, 0.2), (1.5, 0.8), (1.0, 0.8)]

    def mesh(order):
        uvs = [(0.5, 0.2), (1.0, 0.2), (1.0, 0.8), (0.5, 0.8), (1.5, 0.2), (1.5, 0.8)]
        faces = {'a': [0, 1, 2, 3], 'b': [1, 4, 5, 2]}
        return {'vertices': [(x, y, 0.0) for x, y in uvs], 'uvs': uvs, 'faces': [faces[k] for k in order],
                'face_uvs': [faces[k] for k in order], 'ids': [2, 2]}
    assert [mesh('ab')['uvs'][i] for i in mesh('ab')['face_uvs'][0]] == a
    assert [mesh('ab')['uvs'][i] for i in mesh('ab')['face_uvs'][1]] == b

    def same(fn):
        x, y = fn(mesh('ab')), fn(mesh('ba'))
        return sorted(face_uv(x, f) for f in range(2)) == sorted(face_uv(y, f) for f in range(2)) and tiles_ok(x)
    red_green(same, lambda: source_v92_keep, lambda: (lambda m: keep([m])[0][0]))
    out = keep([mesh('ab')])[0][0]
    assert face_uv(out, 0) == [(1.5, 0.2), (2.0, 0.2), (2.0, 0.8), (1.5, 0.8)]
    assert face_uv(out, 1) == b  # already in tile 1002: offset 0, its own copy of the shared corners


def test_e2_d13_v8_id_over_100_keeps_its_shared_uv_vertices():
    uvs = [(0.2, 0.2), (0.6, 0.2), (0.6, 0.6), (0.2, 0.6), (0.9, 0.2), (0.9, 0.6)]
    m = {'vertices': [(x, y, 0.0) for x, y in uvs], 'uvs': uvs, 'faces': [[0, 1, 2, 3], [1, 4, 5, 2]],
         'face_uvs': [[0, 1, 2, 3], [1, 4, 5, 2]], 'ids': [3, 101]}
    red_green(lambda out: face_uv(out, 1) == face_uv(m, 1), lambda: source_v92_keep(m), lambda: keep([m])[0][0])
    out, scales = keep([m])
    assert scales[(0, 101)]['status'] == 'rejected' and tiles_ok(out[0], ids={3})


def test_e2_d11_face_across_a_tile_line_refuses_its_id():
    m = Mesh().quad(4, 0, 0, 1, 1, 0.8, 0.2, 0.4, 0.4).quad(6, 1, 0, 1, 1, 0.1, 0.1, 0.2, 0.2).m
    out, scales = keep([m])
    s = scales[(0, 4)]
    assert s['status'] == 'straddles' and s['faces'] == [1] and 'cross a tile line' in s['reason']
    assert face_uv(out[0], 0) == face_uv(m, 0) and tiles_ok(out[0], ids={6})
    rows = uc.id_rows(m, scales, 0)
    assert [r['status'] for r in rows] == ['straddles', 'placed']


def plane50(seed=7):
    """50 x 50 quads split into 5000 triangles, planar UVs u = x/10 - 2, v = y/10 - 1 (negative UVs included,
    tile lines on grid lines), random IDs 1..100 per quad."""
    import random
    rnd = random.Random(seed)
    m = {'vertices': [], 'uvs': [], 'faces': [], 'face_uvs': [], 'ids': []}
    for j in range(51):
        for i in range(51):
            m['vertices'].append((float(i), float(j), 0.0))
            m['uvs'].append((i / 10.0 - 2.0, j / 10.0 - 1.0))
    for j in range(50):
        for i in range(50):
            a, b, c, d = j * 51 + i, j * 51 + i + 1, (j + 1) * 51 + i + 1, (j + 1) * 51 + i
            mid = rnd.randint(1, 100)
            for tri in ([a, b, c], [a, c, d]):
                m['faces'].append(tri)
                m['face_uvs'].append(list(tri))
                m['ids'].append(mid)
    return m


@pytest.mark.parametrize('mode', ['keep', 'fit'])
def test_e2_plane_5000_faces_id_udim_id_round_trip(mode):
    m = plane50()
    assert len(m['ids']) == 5000
    out, scales = impl_layout([m], mode=mode)
    back = uc.ids_from_tiles(out[0]['uvs'], out[0]['face_uvs'])
    assert sum(1 for a, b in zip(back, m['ids']) if a == b) == 5000
    if mode == 'keep':
        assert fractions_kept(m, out[0], range(5000))
        src = source_v92_keep(m)  # RED on the source model: the clamp sends negative UVs to the wrong tile
        assert sum(1 for a, b in zip(uc.ids_from_tiles(src['uvs'], src['face_uvs']), m['ids']) if a == b) < 5000


def test_e2_keep_mode_option_and_cell_rule():
    assert 'keep' in uc.MODES
    assert uc.face_cell([(-0.5, -0.5), (-0.1, -0.5), (-0.1, -0.1)], [0, 1, 2]) == (-1, -1)
    assert uc.face_cell([(0.9, 0.5), (1.1, 0.5), (1.0, 0.6)], [0, 1, 2]) is None
    assert uc.ids_from_tiles([(0.5, 0.5), (0.6, 0.5), (0.5, 0.6), (-0.5, 0.5), (-0.4, 0.5), (-0.5, 0.6)],
                             [[0, 1, 2], [3, 4, 5]]) == [1, None]


def test_e2_d12_glue_reads_the_evaluated_stack_and_collapses_only_the_copy():
    """T02 V4: v9.2 edited the base channel under Unwrap_UVW / UVW_Xform. The glue no longer refuses or edits
    under a stack; it reads a collapsed throwaway copy and collapses the export copy (the native run checks it)."""
    text = (PKG / 'udim_max.py').read_text(encoding='utf-8')
    assert 'has a modifier stack' not in text
    assert '_collapse(c)' in text and '_read_eval(ctx, n)' in text
