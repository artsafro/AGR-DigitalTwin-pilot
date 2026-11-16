"""new-case: #1574 per-face directional texel of the world box UV projection (tools/blender/box_uv.py);
synthetic data only.

Box projection keeps px_per_m along the face's trace on the projection plane and compresses the other
direction by |n_axis| (>= 1/sqrt(3)); both singular values of the UV-px / metre Jacobian must stay inside
512..1706 (reg p.32 §6.2) or the plan raises and nothing is written."""
import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / 'tools/blender/box_uv.py'


@pytest.fixture(scope='module')
def box():
    spec = importlib.util.spec_from_file_location('box_uv_1574', OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def key(p):
    return tuple(round(c, 9) for c in p)


def quad(fid, origin, du, dv, w=1.0, h=1.0):
    """Planar quad: origin + s*w*du + t*h*dv, CCW about du x dv."""
    co = [tuple(origin[i] + a * w * du[i] + b * h * dv[i] for i in range(3))
          for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
    return (fid, [key(c) for c in co], co)


def wall_rotated(deg, fid=0, origin=(0.3, 0.2, 0.1)):
    """Vertical 1 x 1 m wall, horizontal direction rotated `deg` about Z from +X."""
    r = math.radians(deg)
    return quad(fid, origin, (math.cos(r), math.sin(r), 0.0), (0.0, 0.0, 1.0))


def slope(deg, fid=0, origin=(0.3, 0.2, 0.1)):
    """1 x 1 m roof plane: +X horizontal, rising `deg` from horizontal along Y."""
    r = math.radians(deg)
    return quad(fid, origin, (1.0, 0.0, 0.0), (0.0, math.cos(r), math.sin(r)))


def sv_range(coords, uv, texture_px=4096):
    """Independent measurement: min/max singular value (px/m) over fan triangles of one face."""
    lo, hi = math.inf, 0.0
    for i in range(1, len(coords) - 1):
        p0, p1, p2 = coords[0], coords[i], coords[i + 1]
        d1 = [p1[k] - p0[k] for k in range(3)]
        d2 = [p2[k] - p0[k] for k in range(3)]
        g11 = sum(c * c for c in d1)
        g22 = sum(c * c for c in d2)
        g12 = sum(a * b for a, b in zip(d1, d2))
        det_g = g11 * g22 - g12 * g12
        if det_g <= 1e-18:
            continue
        q1 = [(uv[i][k] - uv[0][k]) * texture_px for k in (0, 1)]
        q2 = [(uv[i + 1][k] - uv[0][k]) * texture_px for k in (0, 1)]
        h11 = sum(c * c for c in q1)
        h22 = sum(c * c for c in q2)
        h12 = sum(a * b for a, b in zip(q1, q2))
        # singular values^2 = eigenvalues of G^-1 H (pullback metric)
        a11 = (g22 * h11 - g12 * h12) / det_g
        a22 = (g11 * h22 - g12 * h12) / det_g
        a12 = (g22 * h12 - g12 * h22) / det_g
        a21 = (g11 * h12 - g12 * h11) / det_g
        tr, det = a11 + a22, a11 * a22 - a12 * a21
        disc = math.sqrt(max(tr * tr / 4 - det, 0.0))
        lo = min(lo, math.sqrt(max(tr / 2 - disc, 0.0)))
        hi = max(hi, math.sqrt(tr / 2 + disc))
    return lo, hi


# ------------------------------------------------------------------ issue examples (regression)
def test_rotated_wall_at_600_fails_naming_the_face(box):
    with pytest.raises(box.BoxUVTexelError, match=r"face 'w40'.*459\.6") as exc:
        box.plan_box_uv([wall_rotated(40, fid='w40')], 600, 1001)
    assert '512' in str(exc.value)


def test_slope_50_at_512_fails_naming_the_face(box):
    with pytest.raises(box.BoxUVTexelError, match=r'face 7\b.*392\.2'):
        box.plan_box_uv([slope(50, fid=7)], 512, 1001)


def test_rotated_wall_at_819_reports_real_texel(box):
    face = wall_rotated(40)
    uvs, rep = box.plan_box_uv([face], 819.2, 1001, margin_px=0)
    lo, hi = rep['texel_px_per_m']
    assert abs(lo - 819.2 * math.cos(math.radians(40))) < 1e-4 and abs(lo - 627.5) < 0.1
    assert abs(hi - 819.2) < 1e-4
    mlo, mhi = sv_range(face[2], uvs[0])
    assert abs(mlo - lo) < 1e-4 and abs(mhi - hi) < 1e-4


def test_axis_aligned_report_equals_px(box):
    face = quad(0, (0.1, 0.0, 0.2), (1, 0, 0), (0, 0, 1))
    _, rep = box.plan_box_uv([face], 512, 1001, margin_px=0)
    assert rep['texel_px_per_m'] == [512.0, 512.0]


def test_mixed_list_names_only_bad_faces_and_returns_nothing(box):
    good = [quad(i, (i * 1.0, 0.0, 0.0), (1, 0, 0), (0, 0, 1)) for i in range(3)]
    bad = [wall_rotated(44, fid=10, origin=(9.0, 9.0, 0.0)), slope(55, fid=11, origin=(-9.0, 0.0, 0.0))]
    with pytest.raises(box.BoxUVTexelError) as exc:
        box.plan_box_uv(good + bad, 600, 1001)
    msg = str(exc.value)
    assert '2 face(s)' in msg and 'face 10' in msg and 'face 11' in msg
    assert all(f'face {i} ' not in msg for i in range(3))
    # the remedy names the least legal density at which every listed face passes, and it does pass
    m = float(msg.split('px_per_m >= ')[1].split()[0].rstrip(','))
    assert m <= 1706 and abs(m - 512 / min(math.cos(math.radians(44)), math.sin(math.radians(55)))) < 0.1
    _, rep = box.plan_box_uv(good + bad, m, 1001, margin_px=0)
    assert rep['texel_px_per_m'][0] >= 512


# ------------------------------------------------------------------ thresholds (inclusive regulation)
@pytest.mark.parametrize('deg', [30.0, 40.0, 45.0])
def test_exactly_at_floor_passes_just_below_fails(box, deg):
    ratio = max(math.cos(math.radians(deg)), math.sin(math.radians(deg)))   # dominant axis component
    at = 512 / ratio
    _, rep = box.plan_box_uv([wall_rotated(deg)], at, 1001, margin_px=0)
    assert abs(rep['texel_px_per_m'][0] - 512) < 1e-6
    with pytest.raises(box.BoxUVTexelError):
        box.plan_box_uv([wall_rotated(deg)], at * (1 - 1e-6), 1001, margin_px=0)


def test_non_planar_face_checked_per_triangle(box):
    """Quad whose second fan triangle is steep (|n_y| 0.38): face normal is still -Y, texel of that half fails."""
    co = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 1.0 / math.tan(math.radians(30)), 1.0)]
    face = ('np', [key(c) for c in co], co)
    with pytest.raises(box.BoxUVTexelError, match="face 'np'"):
        box.plan_box_uv([face], 700, 1001, margin_px=0)


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('start', range(4))
def test_warped_quad_rejected_for_every_corner_order(box, start, reverse):
    """#1612: either export diagonal must meet the floor, regardless of loop start/winding."""
    co = [(0.1, 0.1, 0.1), (1.1, 0.1, 0.1), (1.1, 1.1, 0.9), (0.1, 1.1, 0.1)]
    co = co[start:] + co[:start]
    if reverse:
        co.reverse()
    with pytest.raises(box.BoxUVTexelError, match=r"face 'warped'.*463\.6"):
        box.plan_box_uv([('warped', [key(c) for c in co], co)], 700, 1001, margin_px=0)


@pytest.mark.parametrize('height', [0.0, 0.1, 0.4, 0.8, 1.2])
@pytest.mark.parametrize('px', [512.0, 700.0, 1024.0, 1706.0])
@pytest.mark.parametrize('axis_shift', range(3))
def test_generated_warped_quad_diagonal_envelope(box, height, px, axis_shift):
    """Synthetic exhaustive probe: 480 loop orders, both diagonals measured independently from UVs."""
    original = [(0.1, 0.1, 0.1), (1.1, 0.1, 0.1),
                (1.1, 1.1, 0.1 + height), (0.1, 1.1, 0.1)]
    original = [p[axis_shift:] + p[:axis_shift] for p in original]
    expected = px / math.sqrt(1 + 2 * height * height)
    for reverse in (False, True):
        for start in range(4):
            co = original[start:] + original[:start]
            if reverse:
                co.reverse()
            face = ('generated', [key(c) for c in co], co)
            if expected < 512:
                with pytest.raises(box.BoxUVTexelError, match="face 'generated'"):
                    box.plan_box_uv([face], px, 1001, margin_px=0)
            else:
                uvs, report = box.plan_box_uv([face], px, 1001, margin_px=0)
                # Literal diagonal partitions, independent of the production normal enumeration.
                measured = [sv_range([co[i] for i in tri], [uvs['generated'][i] for i in tri])[0]
                            for tri in ((0, 1, 2), (0, 2, 3), (0, 1, 3), (1, 2, 3))]
                assert min(measured) == pytest.approx(expected, abs=1e-4)
                assert report['texel_px_per_m'] == pytest.approx([expected, px], abs=1e-4)


@pytest.mark.parametrize('start', range(4))
def test_warped_quad_floor_is_inclusive_and_reset_is_clean(box, start):
    co = [(0.1, 0.1, 0.1), (1.1, 0.1, 0.1), (1.1, 1.1, 0.9), (0.1, 1.1, 0.1)]
    co = co[start:] + co[:start]
    face = ('threshold', [key(c) for c in co], co)
    at = 512 * math.sqrt(1 + 2 * 0.8 ** 2)
    for _ in range(2):
        with pytest.raises(box.BoxUVTexelError):
            box.plan_box_uv([face], at * (1 - 1e-6), 1001, margin_px=0)
        _, report = box.plan_box_uv([face], at, 1001, margin_px=0)
        assert report['texel_px_per_m'][0] == pytest.approx(512)


def test_collinear_corner_is_not_a_false_failure(box):
    """Pentagon with a collinear corner: a zero-area fan triangle is skipped, the face passes at 512."""
    co = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    face = (0, [key(c) for c in co], co)
    _, rep = box.plan_box_uv([face], 512, 1001, margin_px=0)
    assert rep['texel_px_per_m'] == [512.0, 512.0]


@pytest.mark.parametrize('offset', [0.0, 1e3, 1e4])
def test_collinear_corner_oblique_far_from_origin_threshold(box, offset):
    """Probe: oblique pentagon with a collinear corner far from the origin: the roundoff sliver does not move
    the threshold; 512 / ratio * (1 + 1e-7) passes, * (1 - 1e-6) fails."""
    r = math.radians(37)
    du, dz = (math.cos(r), math.sin(r), 0.0), (0.0, 0.0, 1.0)
    o = (offset + 0.31, offset + 0.17, 0.2)
    pts = [(0, 0), (0.5, 0), (1, 0), (1, 1), (0, 1)]
    co = [tuple(o[i] + a * du[i] + b * dz[i] for i in range(3)) for a, b in pts]
    face = (0, [key(c) for c in co], co)
    at = 512 / max(math.cos(r), math.sin(r))
    _, rep = box.plan_box_uv([face], at * (1 + 1e-7), 1001, margin_px=0)
    assert rep['texel_px_per_m'][0] >= 512
    with pytest.raises(box.BoxUVTexelError):
        box.plan_box_uv([face], at * (1 - 1e-6), 1001, margin_px=0)


# ------------------------------------------------------------------ generated probe
def test_generated_random_planes_fail_iff_texel_below_floor(box):
    """Probe: random orientation + density; raise <=> analytic px*|n_axis| < 512; on pass the independently
    measured singular values of the written UVs lie in 512..1706 and equal the report."""
    rng, n, passed, failed = random.Random(1574), 0, 0, 0
    for _ in range(600):
        px = rng.choice([512, 600, 819.2, 1024, 1706, rng.uniform(512, 1706)])
        d = [rng.gauss(0, 1) for _ in range(3)]
        ln = math.sqrt(sum(c * c for c in d))
        nrm = [c / ln for c in d]
        a = (1.0, 0.0, 0.0) if abs(nrm[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = [a[(i + 1) % 3] * nrm[(i + 2) % 3] - a[(i + 2) % 3] * nrm[(i + 1) % 3] for i in range(3)]
        lu = math.sqrt(sum(c * c for c in u))
        u = [c / lu for c in u]
        v = [nrm[(i + 1) % 3] * u[(i + 2) % 3] - nrm[(i + 2) % 3] * u[(i + 1) % 3] for i in range(3)]
        face = quad(0, (rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-3, 3)), u, v, 0.4, 0.3)
        texel_min = px * max(abs(c) for c in nrm)
        if abs(texel_min - 512) < 1e-6:
            continue
        try:
            uvs, rep = box.plan_box_uv([face], px, 1001, margin_px=0)
        except box.BoxUVOverflow:
            continue
        except box.BoxUVTexelError:
            assert texel_min < 512, (px, nrm)
            failed += 1
            n += 1
            continue
        assert texel_min >= 512, (px, nrm)
        lo, hi = sv_range(face[2], uvs[0])
        assert 512 - 1e-6 <= lo <= hi <= 1706 + 1e-6
        assert abs(lo - texel_min) < 1e-6 * px and abs(hi - px) < 1e-6 * px
        assert abs(rep['texel_px_per_m'][0] - lo) < 1e-4 and abs(rep['texel_px_per_m'][1] - hi) < 1e-4
        passed += 1
        n += 1
    assert n >= 300 and passed > 100 and failed > 100


# ------------------------------------------------------------------ nothing written (Blender wrapper, fake mesh)
class _Loop:
    def __init__(self):
        self.vector = (9.0, 9.0)


class _Layer:
    def __init__(self, n):
        self.name, self.uv, self.writes = 'UVMap', [_Loop() for _ in range(n)], 0


class _Layers:
    def __init__(self, n):
        self.active = _Layer(n)

    def get(self, name):
        return self.active if name == self.active.name else None

    def new(self, **_):
        raise AssertionError('no layer may be created')


class _Poly:
    def __init__(self, verts, start):
        self.vertices, self.loop_start, self.loop_total = verts, start, len(verts)


class _Vert:
    def __init__(self, co):
        self.co = co


class _Mat:
    def __matmul__(self, co):
        return co


@pytest.mark.parametrize('warped', [False, True])
def test_wrapper_writes_nothing_on_texel_error(box, warped):
    _, verts, co = wall_rotated(40)
    if warped:
        co = [(0.1, 0.1, 0.1), (1.1, 0.1, 0.1), (1.1, 1.1, 0.9), (0.1, 1.1, 0.1)]
    mesh = type('M', (), {})()
    mesh.name, mesh.users = 'm', 1
    mesh.vertices = [_Vert(c) for c in co]
    mesh.polygons = [_Poly([0, 1, 2, 3], 0)]
    mesh.uv_layers = _Layers(4)
    mesh.update = lambda: (_ for _ in ()).throw(AssertionError('update after error'))
    obj = type('O', (), {})()
    obj.type, obj.name, obj.data, obj.matrix_world = 'MESH', 'wall40', mesh, _Mat()
    with pytest.raises(box.BoxUVTexelError):
        box.box_project_uv(obj, [0], 600, 1001)
    assert all(lp.vector == (9.0, 9.0) for lp in mesh.uv_layers.active.uv)
