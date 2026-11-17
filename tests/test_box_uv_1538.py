"""new-case: #1538 world box UV projection of a tiling trim (tools/blender/box_uv.py); synthetic data only."""
import ast
import importlib.util
import json
import math
import random
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / 'tools/blender/box_uv.py'
RUNNER = ROOT / 'tests/blender/run_box_uv_1538.py'


def load():
    spec = importlib.util.spec_from_file_location('box_uv_1538', OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def box():
    return load()


def l_facade(origin=(100.37, -54.6, 5.3), na=3, pa=1.5, nb=2, pb=1.5, nr=3, ph=1.0):
    """Synthetic welded L facade: wall A outward -Y, wall B outward +X, shared corner column."""
    ox, oy, oz = origin
    faces, xa = [], na * pa

    def key(p):
        return tuple(round(c, 9) for c in p)

    for j in range(nr):
        z0, z1 = oz + j * ph, oz + (j + 1) * ph
        for i in range(na):
            x0, x1 = ox + i * pa, ox + (i + 1) * pa
            co = [(x0, oy, z0), (x1, oy, z0), (x1, oy, z1), (x0, oy, z1)]
            faces.append((len(faces), [key(c) for c in co], co))
        for i in range(nb):
            y0, y1 = oy + i * pb, oy + (i + 1) * pb
            co = [(ox + xa, y0, z0), (ox + xa, y1, z0), (ox + xa, y1, z1), (ox + xa, y0, z1)]
            faces.append((len(faces), [key(c) for c in co], co))
    return faces


def seams(box, faces, uvs, tol=1e-6):
    """(interior coplanar edges, edges whose UV jump is not a whole number of periods)."""
    corner, owners = {}, {}
    axis = {fid: box.axis_key(box.newell_normal(co)) for fid, _, co in faces}
    for fid, verts, _ in faces:
        for k, v in enumerate(verts):
            corner[(fid, v)] = uvs[fid][k]
        for a, b in zip(verts, verts[1:] + verts[:1]):
            owners.setdefault(frozenset((a, b)), []).append(fid)
    interior = broken = 0
    for edge, fs in owners.items():
        if len(fs) != 2 or axis[fs[0]] != axis[fs[1]]:
            continue
        interior += 1
        f, g = fs
        jumps = [corner[(f, v)][i] - corner[(g, v)][i] for v in edge for i in (0, 1)]
        broken += any(abs(j - round(j)) > tol for j in jumps)
    return interior, broken


def texels(faces, uvs, texture_px=4096):
    out = []
    for fid, _, co in faces:
        uv = uvs[fid]
        a_uv = abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(uv, uv[1:] + uv[:1]))) / 2
        e1 = [co[1][i] - co[0][i] for i in range(3)]
        e2 = [co[3][i] - co[0][i] for i in range(3)]
        area = math.sqrt(sum((e1[(i + 1) % 3] * e2[(i + 2) % 3] - e1[(i + 2) % 3] * e2[(i + 1) % 3]) ** 2
                             for i in range(3)))
        out.append(math.sqrt(a_uv * texture_px ** 2 / area))
    return out


def per_tile_snap(uvs, margin=8 / 4096):
    """The rejected v1: every face snapped into the tile on its own."""
    out = {}
    for fid, uv in uvs.items():
        umin, vmin = min(u for u, _ in uv), min(v for _, v in uv)
        out[fid] = [(u - umin + margin, v - vmin + margin) for u, v in uv]
    return out


# ------------------------------------------------------------------ acceptance: seams, texel, negative witness
def test_corner_facade_seams_whole_periods_and_texel(box):
    faces = l_facade()
    uvs, rep = box.plan_box_uv(faces, 819.2, 1001)
    interior, broken = seams(box, faces, uvs)
    assert interior == 19 and broken == 0   # 12 on wall A + 7 on wall B
    assert rep['period_m'] == 5.0 and len(rep['islands']) == 2
    assert all(abs(t - 819.2) < 1e-6 for t in texels(faces, uvs))
    assert all(512 <= t <= 1706 for t in texels(faces, uvs))
    assert all(0 <= c <= 1 for uv in uvs.values() for p in uv for c in p)   # tile 1001


def test_per_tile_snapping_fails_the_same_seam_test(box):
    faces = l_facade()
    uvs, _ = box.plan_box_uv(faces, 819.2, 1001)
    interior, broken = seams(box, faces, per_tile_snap(uvs))
    assert interior == 19 and broken > 0


def test_no_operator_in_the_owner():
    tree = ast.parse(OWNER.read_text(encoding='utf-8'))
    attrs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ('ops', 'select_set',
                                                                                       'mode_set')]
    assert not attrs
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and 'bpy' in ast.unparse(n) for n in ast.walk(tree))


def test_tile_offset_and_no_mirror(box):
    faces = l_facade()
    uvs, _ = box.plan_box_uv(faces, 819.2, 1012)    # tile 1012 = cell (1, 1)
    assert all(1 <= c <= 2 for uv in uvs.values() for p in uv for c in p)
    for fid, _, _ in faces:
        uv = uvs[fid]
        assert sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(uv, uv[1:] + uv[:1])) > 0   # winding kept


# ------------------------------------------------------------------ fail-closed
@pytest.mark.parametrize('px,tile,msg', [
    (math.nan, 1001, 'finite'), (math.inf, 1001, 'finite'), (-math.inf, 1001, 'finite'), (True, 1001, 'finite'),
    ('819', 1001, 'finite'), (511.999, 1001, 'outside'), (1706.001, 1001, 'outside'), (0, 1001, 'outside'),
    (819.2, 1000, '1001'), (819.2, 1101, '1001..1100'), (819.2, 1001.0, '1001'), (819.2, True, '1001'),
    (819.2, None, '1001')])
def test_invalid_params_raise(box, px, tile, msg):
    with pytest.raises(box.BoxUVError, match=msg):
        box.plan_box_uv(l_facade(), px, tile)


@pytest.mark.parametrize('px', [512, 1706])
def test_inclusive_regulation_bounds(box, px):
    faces = l_facade(origin=(0.1, 0.1, 0.1), na=2, pa=0.5, nb=2, pb=0.5, nr=2, ph=0.5)
    uvs, _ = box.plan_box_uv(faces, px, 1001)
    assert seams(box, faces, uvs)[1] == 0


@pytest.mark.parametrize('kw,msg', [({'texture_px': 0}, 'texture_px'), ({'texture_px': 4096.0}, 'texture_px'),
                                    ({'margin_px': -1}, 'margin_px'), ({'margin_px': 2048}, 'margin_px'),
                                    ({'margin_px': math.nan}, 'finite')])
def test_invalid_texture_or_margin(box, kw, msg):
    with pytest.raises(box.BoxUVError, match=msg):
        box.plan_box_uv(l_facade(), 819.2, 1001, **kw)


def test_bad_faces_raise(box):
    good = l_facade()
    with pytest.raises(box.BoxUVError, match='no faces'):
        box.plan_box_uv([], 819.2, 1001)
    with pytest.raises(box.BoxUVError, match='duplicate face 0'):
        box.plan_box_uv(good + good[:1], 819.2, 1001)
    with pytest.raises(box.BoxUVError, match='non-finite'):
        box.plan_box_uv([(0, [1, 2, 3], [(0, 0, 0), (1, 0, 0), (1, 0, math.nan)])], 819.2, 1001)
    with pytest.raises(box.BoxUVError, match='degenerate'):
        box.plan_box_uv([(0, [1, 2, 3], [(0, 0, 0), (1, 0, 0), (2, 0, 0)])], 819.2, 1001)
    with pytest.raises(box.BoxUVError, match='>= 3'):
        box.plan_box_uv([(0, [1, 2], [(0, 0, 0), (1, 0, 0)])], 819.2, 1001)


def test_overflow_raises_naming_island(box):
    with pytest.raises(box.BoxUVOverflow, match=r'axis -y faces \[0, 1, 2'):
        box.plan_box_uv(l_facade(na=5), 819.2, 1001)   # 7.5 m wall, 5 m period


# ------------------------------------------------------------------ generated probes
def test_generated_overflow_iff_no_whole_period_shift_fits(box):
    """Brute force: plan raises BoxUVOverflow exactly when no integer shift puts the island in the tile."""
    rng, n, fits = random.Random(15381), 0, 0
    for _ in range(400):
        px = rng.uniform(512, 1706)
        w, h = rng.uniform(0.05, 1.2) * 4096 / px, rng.uniform(0.05, 1.2) * 4096 / px
        x, z = rng.uniform(-300, 300), rng.uniform(-50, 50)
        co = [(x, 0.0, z), (x + w, 0.0, z), (x + w, 0.0, z + h), (x, 0.0, z + h)]
        s, m = px / 4096, 8 / 4096
        ok = [any(m - 1e-9 <= lo - k and hi - k <= 1 - m + 1e-9 for k in range(math.floor(lo) - 2, math.floor(lo) + 3))
              for lo, hi in ((x * s, (x + w) * s), (z * s, (z + h) * s))]
        try:
            box.plan_box_uv([(0, [0, 1, 2, 3], co)], px, 1001)
            raised = False
        except box.BoxUVOverflow:
            raised = True
        assert raised == (not all(ok)), (px, co)
        n += 1
        fits += all(ok)
    assert n == 400 and 0 < fits < 400


# ------------------------------------------------------------------ #1573: world period lines are island borders
def strip_wall(cuts_x, cuts_z=(0.0, 3.0), y=0.0):
    """Wall outward -Y, loop-cut at every x in cuts_x and z in cuts_z; quads CCW in (x, z)."""
    faces = []

    def key(p):
        return tuple(round(c, 9) for c in p)

    for z0, z1 in zip(cuts_z, cuts_z[1:]):
        for x0, x1 in zip(cuts_x, cuts_x[1:]):
            co = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
            faces.append((len(faces), [key(c) for c in co], co))
    return faces


def in_tile(uvs, tile=(0, 0)):
    return all(tile[i] <= c <= tile[i] + 1 for uv in uvs.values() for p in uv for i, c in enumerate(p))


@pytest.mark.parametrize('xs', [[0.0, 1.25, 2.5, 5.0, 6.25, 7.5], [-12.5, -11.0, -10.0, -7.0, -5.0],
                                [97.5, 99.0, 100.0, 102.5, 105.0]])
def test_loop_cut_wall_at_period_line_is_two_islands(box, xs):
    """#1573: 7.5 m wall loop-cut on the world period line (5 m at 819.2 px/m) projects in one call."""
    faces = strip_wall(xs)
    uvs, rep = box.plan_box_uv(faces, 819.2, 1001, margin_px=0)
    assert len(rep['islands']) == 2
    assert all(isl['span'][0] <= 1.0 + 1e-9 for isl in rep['islands'])
    interior, broken = seams(box, faces, uvs)
    assert interior > 0 and broken == 0
    assert in_tile(uvs) and all(abs(t - 819.2) < 1e-6 for t in texels(faces, uvs))


def test_loop_cut_wall_horizontal_period_line(box):
    faces = strip_wall([0.3, 2.0, 4.0], cuts_z=[0.0, 2.5, 5.0, 7.5])
    uvs, rep = box.plan_box_uv(faces, 819.2, 1001, margin_px=0)
    assert len(rep['islands']) == 2 and seams(box, faces, uvs)[1] == 0 and in_tile(uvs)


def test_one_world_aligned_period_strip_margin_zero(box):
    uvs, rep = box.plan_box_uv(strip_wall([0.0, 2.5, 5.0]), 819.2, 1001, margin_px=0)
    assert len(rep['islands']) == 1 and in_tile(uvs)


def test_cut_off_the_period_line_stays_one_island(box):
    with pytest.raises(box.BoxUVOverflow, match='period line'):
        box.plan_box_uv(strip_wall([0.0, 4.9, 7.5]), 819.2, 1001, margin_px=0)


def test_edge_touching_period_line_at_one_end_is_not_a_border(box):
    """A diagonal edge with one endpoint on x = 5 m keeps both triangles in one island (it crosses the line)."""
    def key(p):
        return tuple(round(c, 9) for c in p)
    t1 = [(4.5, 0.0, 0.0), (5.0, 0.0, 0.0), (4.5, 0.0, 3.0)]
    t2 = [(5.0, 0.0, 0.0), (5.5, 0.0, 3.0), (4.5, 0.0, 3.0)]
    faces = [(0, [key(c) for c in t1], t1), (1, [key(c) for c in t2], t2)]
    with pytest.raises(box.BoxUVOverflow, match=r'faces \[0, 1\]'):
        box.plan_box_uv(faces, 819.2, 1001, margin_px=0)


def test_period_cut_with_tile_margin_overflows_naming_the_conflict(box):
    """With margin > 0 no island can touch a period line; the error says so instead of 'split by texel cuts'."""
    with pytest.raises(box.BoxUVOverflow, match='margin_px=0') as exc:
        box.plan_box_uv(strip_wall([0.0, 1.25, 5.0, 6.25, 7.5]), 819.2, 1001)
    assert 'conflicts.md' in str(exc.value)


def test_generated_period_cut_walls_fit_with_margin_zero(box):
    """Probe: random density, origin, period cuts + random extra cuts; every piece between period lines is
    one island, all fit the tile, seams whole periods, texel exact."""
    rng, n = random.Random(1573), 0
    for _ in range(300):
        px = rng.choice([512, 819.2, 1024, 1706, rng.uniform(512, 1706)])
        period = 4096 / px
        k0, nper = rng.randint(-60, 60), rng.randint(1, 4)
        x0, x1 = (k0 + rng.uniform(0.0, 0.9)) * period, (k0 + nper + rng.uniform(0.1, 1.0)) * period
        lines = [(k0 + i) * period for i in range(1, nper + 1)]
        xs = sorted({x0, x1, *lines, *(rng.uniform(x0, x1) for _ in range(rng.randint(0, 4)))})
        if any(b - a < 1e-3 for a, b in zip(xs, xs[1:])):
            continue
        faces = strip_wall(xs, cuts_z=[0.1, 0.3 * period, 0.6 * period])
        uvs, rep = box.plan_box_uv(faces, px, 1001, margin_px=0)
        assert len(rep['islands']) == nper + 1, (px, xs)
        assert in_tile(uvs) and seams(box, faces, uvs)[1] == 0
        assert all(abs(t - px) < 1e-6 for t in texels(faces, uvs))
        n += 1
    assert n >= 250


def test_generated_seams_and_texel(box):
    rng, done = random.Random(1538), 0
    for _ in range(300):
        px = rng.uniform(512, 1706)
        period = 4096 / px
        pa, ph = rng.uniform(0.2, 0.6), rng.uniform(0.2, 0.5)
        faces = l_facade(origin=(rng.uniform(-500, 500), rng.uniform(-500, 500), rng.uniform(-20, 80)),
                         na=max(2, int(0.3 * period / pa)), pa=pa, nb=2, pb=pa, nr=max(2, int(0.3 * period / ph)), ph=ph)
        try:
            uvs, _ = box.plan_box_uv(faces, px, 1001)
        except box.BoxUVOverflow:
            continue
        interior, broken = seams(box, faces, uvs)
        assert interior > 0 and broken == 0
        assert all(abs(t - px) < 1e-6 for t in texels(faces, uvs))
        assert seams(box, faces, per_tile_snap(uvs))[1] > 0
        done += 1
    assert done >= 50


# ------------------------------------------------------------------ #1600: Blender float32 world coordinates

def float32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


@pytest.mark.parametrize('px', [1000, 1706])
@pytest.mark.parametrize('offset', [0, 3, 2000, -2000])
@pytest.mark.parametrize('horizontal', [False, True])
def test_float32_period_cut_fits(box, px, offset, horizontal):
    period = 4096 / px
    cuts = [float32((offset + f) * period) for f in (0.1, 1, 1.5)]
    small = [float32(0.1 * period), float32(0.6 * period)]
    faces = strip_wall(small, cuts_z=cuts) if horizontal else strip_wall(cuts, cuts_z=small)
    uvs, rep = box.plan_box_uv(faces, px, 1012, margin_px=0)
    assert len(rep['islands']) == 2 and rep['period_cut_edges'] == 1
    assert set(uvs) == {0, 1} and in_tile(uvs, (1, 1))
    assert seams(box, faces, uvs) == (1, 0)
    # Float32 source quantization is corrected by less than half a texel.
    for fid, _, coords in faces:
        shift = next(i['shift'] for i in rep['islands'] if fid in i['faces'])
        for co, uv in zip(coords, uvs[fid]):
            expected = box.axis_uv(co, '-y')
            assert all(abs((uv[i] - 1 + shift[i]) * 4096 - expected[i] * px) <= 0.5 + 1e-6
                       for i in (0, 1))


@pytest.mark.parametrize('px', [1000, 1706])
@pytest.mark.parametrize('offset', [0, 3, 2000, -2000])
def test_float32_cut_just_off_line_stays_connected(box, px, offset):
    period = 4096 / px
    # At small origins even 0.01 pixel is distinguishable; at 2000 periods use
    # one pixel (larger than float32 uncertainty, still a sub-mm cut offset).
    delta_px = 0.01 if abs(offset) < 10 else 1.0
    cuts = [float32((offset + f) * period + (delta_px / px if f == 1 else 0))
            for f in (0.1, 1, 1.5)]
    faces = strip_wall(cuts, cuts_z=[0.1 * period, 0.6 * period])
    with pytest.raises(box.BoxUVOverflow, match=r'faces \[0, 1\]'):
        box.plan_box_uv(faces, px, 1001, margin_px=0)


@pytest.mark.parametrize('offset', [0, 3])
def test_float32_translation_plus_local_period_cut(box, offset):
    px = 1706
    period = 4096 / px
    location = (offset + 0.37) * period
    cuts = [float32(float32(location) + float32((offset + f) * period - location))
            for f in (0.1, 1, 1.5)]
    faces = strip_wall(cuts, cuts_z=[0.1 * period, 0.6 * period])
    uvs, rep = box.plan_box_uv(faces, px, 1001, margin_px=0)
    assert len(rep['islands']) == 2 and rep['period_cut_edges'] == 1
    assert in_tile(uvs) and seams(box, faces, uvs) == (1, 0)


def test_period_snap_half_texel_cap_boundary(box):
    px, line = 1024, 1048576.0  # float32 uncertainty here exceeds half a texel
    at = line + 0.5 / px
    for cut, fits in [(at, True), (math.nextafter(at, math.inf), False)]:
        faces = strip_wall([line - 2, cut, line + 2], cuts_z=[0.1, 1.0])
        if fits:
            uvs, rep = box.plan_box_uv(faces, px, 1001, margin_px=0)
            assert len(rep['islands']) == 2 and in_tile(uvs)
        else:
            with pytest.raises(box.BoxUVOverflow, match=r'faces \[0, 1\]'):
                box.plan_box_uv(faces, px, 1001, margin_px=0)


def test_generated_float32_period_cuts_and_off_line_controls(box):
    """Synthetic seed 1600: both signs, all projection axes, varying density and resolution."""
    rng = random.Random(1600)
    for n in range(240):
        px = rng.uniform(512, 1706)
        texture = rng.choice([1024, 2048, 4096])
        period = texture / px
        offset = rng.randint(-2000, 2000)
        for delta in (0, 1.0 / px):
            cuts = [float32((offset + f) * period + (delta if f == 1 else 0))
                    for f in (0.1, 1, 1.5)]
            faces = strip_wall(cuts, cuts_z=[float32(0.1 * period), float32(0.6 * period)])
            # Cycle coordinate axes and reverse winding: six dominant signed axes.
            mapped = []
            for fid, _, co in faces:
                co = [tuple(p[(i + n % 3) % 3] for i in range(3)) for p in co]
                if n % 2:
                    co.reverse()
                mapped.append((fid, list(co), co))
            if delta:
                with pytest.raises(box.BoxUVOverflow, match=r'faces \[0, 1\]'):
                    box.plan_box_uv(mapped, px, 1001, texture_px=texture, margin_px=0)
            else:
                uvs, rep = box.plan_box_uv(mapped, px, 1001, texture_px=texture, margin_px=0)
                assert len(rep['islands']) == 2 and set(uvs) == {0, 1}
                assert in_tile(uvs) and seams(box, mapped, uvs) == (1, 0)
                with pytest.raises(box.BoxUVOverflow):
                    box.plan_box_uv(mapped, px, 1001, texture_px=texture, margin_px=0.25)


# ------------------------------------------------------------------ real Blender
def _blender():
    from dt_ai.core.blender_runner import blender_executable
    return blender_executable()


@pytest.mark.skipif(not Path(_blender()).is_file(), reason='pinned Blender not installed')
def test_real_blender_target_object_only(tmp_path, monkeypatch):
    from dt_ai.core.blender_runner import run_blender
    monkeypatch.chdir(tmp_path)
    out = tmp_path / 'report.json'
    rep = run_blender(str(RUNNER), [str(out)], output_json=out, timeout=600)
    rep = rep or json.loads(out.read_text(encoding='utf-8'))
    main = rep['main']
    assert main['measure']['interior_edges'] == 20 and main['measure']['broken_edges'] == 0
    assert main['measure']['texel_min'] == main['measure']['texel_max'] == 819.2
    assert main['violations'] == [] and main['selection_unchanged'] and main['tiles'] == [[0, 0]]
    assert main['ucx_layers'] == 0 and main['other_layers'] == 0
    assert len(rep['period_float32']) == 16 and all(c['ok'] for c in rep['period_float32'])
    assert rep['per_tile_snap']['broken_edges'] > 0
    bare = rep['bare']
    assert bare['created'] and bare['violations'] == [] and bare['ucx_layers'] == bare['other_layers'] == 0
    assert bare['measure']['broken_edges'] == 0
    fail = rep['fail_closed']
    assert fail.pop('px_512') == 'ok' and fail.pop('px_1706') == 'ok'
    assert fail['texel_rot40_px600'] == fail['texel_slope50_px512'] == 'error'   # #1574
    assert set(fail.values()) == {'error'}, fail
    gen = rep['generated']
    assert gen['fail'] == [] and gen['pass'] + gen['overflow_nothing_written'] == gen['n'] == 100
    assert gen['pass'] >= 20
