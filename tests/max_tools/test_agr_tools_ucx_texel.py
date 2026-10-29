"""new-case: AGR Tools 0.3.0 UCX collision and texel-readout button seams.

Pattern: new-case. Probes the guarantees for the two new buttons: variant choice
from the measured UCX recommendation, exact piece and triangle parity, texel
min/median within a relative 1e-6, fail-closed inputs, distinct paths, and no
silent default for an unmapped kind or material.
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
RUNTIME = PACKAGE / 'runtime.py'
UCX_CORE = PACKAGE / 'ucx_core.py'
TEXEL_CORE = PACKAGE / 'texel_core.py'
BUILDER = ROOT / 'tools/max/build_agr_tools.py'

BOX_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _box(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]


def _scene(*boxes):
    verts, tris = [], []
    for lo, hi in boxes:
        tris += [tuple(i + len(verts) for i in tri) for tri in BOX_T]
        verts += _box(lo, hi)
    return verts, tris


def _exact_source_hull(verts, tris):
    """Faithful hull of an already-convex source. Not an AABB stand-in."""
    src_v = np.asarray(verts, float)
    src_t = np.asarray(tris, np.int64)

    def hull_fn(points):
        got = np.asarray(points, float)
        if got.shape != src_v.shape or not np.allclose(got, src_v):
            raise AssertionError('hull_fn point set is not the source mesh')
        return src_v, src_t

    return hull_fn


def _clipped_cube():
    """Unit cube clipped by x+y+z <= 2.8. Convex: 10 vertices, 16 triangles."""
    corners = [np.array(p, float) for p in _box((0, 0, 0), (1, 1, 1))]
    polys = []
    for face in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        ring = [corners[i] for i in face]
        out = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            da, db = float(sum(a) - 2.8), float(sum(b) - 2.8)
            if da <= 0:
                out.append(tuple(float(x) for x in a))
            if (da < 0 < db) or (db < 0 < da):
                out.append(tuple(float(x) for x in (a + (b - a) * (-da) / (db - da))))
        polys.append(out)
    polys.append([(1.0, 1.0, 0.8), (1.0, 0.8, 1.0), (0.8, 1.0, 1.0)])
    verts, tris = [], []
    for poly in polys:
        ids = []
        for point in poly:
            point = tuple(round(float(x), 10) for x in point)
            if point not in verts:
                verts.append(point)
            ids.append(verts.index(point))
        for k in range(1, len(ids) - 1):
            tri = [ids[0], ids[k], ids[k + 1]]
            a, b, c = (np.array(verts[i], float) for i in tri)
            if np.dot(np.cross(b - a, c - a), (a + b + c) / 3.0 - np.array((0.5, 0.5, 0.5))) < 0:
                tri.reverse()
            tris.append(tuple(tri))
    return verts, tris


def _quad(z=0.0, size=1.0):
    return {
        'id': 'f1', 'mesh': 'wall', 'material': 'brick',
        'xyz': [(0.0, 0.0, z), (size, 0.0, z), (size, size, z), (0.0, size, z)],
        'uv': [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    }


def test_version_macros_and_ucx_texel_readme():
    runtime = RUNTIME.read_text(encoding='utf-8')
    mcr = (PACKAGE / 'agr_tools.mcr').read_text(encoding='utf-8')
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    startup = (PACKAGE / 'startup.ms').read_text(encoding='utf-8')
    install = (PACKAGE / 'install.ms').read_text(encoding='utf-8')
    assert 'VERSION = "0.4.0"' in runtime
    assert '0.002' in runtime and '0.005' in runtime
    for name in ('AGRToolsUcx', 'AGRToolsUcxApply', 'AGRToolsTexel'):
        assert name in mcr
    assert '0.4.0' in startup and 'Ucx' in startup and 'Texel' in startup
    assert 'AGRTools-0.4.0' in install
    assert 'UCX collision' in readme and 'Texel readout' in readme
    assert 'UCX_name_control_AGR_ucx__01' in readme
    assert 'checked export' in readme.lower()
    assert UCX_CORE.is_file() and TEXEL_CORE.is_file()


def test_ucx_parity_with_python_tool_on_fixed_and_random_meshes():
    core = _load(UCX_CORE, 'agr_ucx_core_parity')
    from tools.methods.ucx import ucx_variants as uv

    clipped = _clipped_cube()
    cases = {
        'box': _scene(((0, 0, 0), (1, 1, 1))),
        'clipped': clipped,
        'passage': _scene(((0, 0, 0), (4, 1, 3)), ((0, 1, 0), (1, 4, 3))),
        'few-levels': _scene(((0, 0, 0), (4, 4, 3)), ((0, 0, 3), (4, 4, 6))),
    }
    expected_kind = {'box': 'near-convex-box', 'clipped': 'near-convex-box',
                     'passage': 'passage', 'few-levels': 'few-levels'}
    expected_tris = {'box': 12, 'clipped': 16}
    matched = 0
    for name, (verts, tris) in cases.items():
        before = (list(map(tuple, verts)), list(map(tuple, tris)))
        got = core.build(verts, tris, mesh='Wall')
        assert (list(map(tuple, verts)), list(map(tuple, tris))) == before
        assert got['kind'] == expected_kind[name]
        exp_pieces, exp = uv.build(got['variant'], np.array(verts, float), np.array(tris, np.int64),
                                    model_triangles=len(tris), hull_fn=_exact_source_hull(verts, tris))
        if name in expected_tris:
            assert got['triangles'] == expected_tris[name] == exp['triangles']
        assert got['pieces_count'] == exp['pieces'] == len(exp_pieces)
        assert got['triangles'] == exp['triangles']
        assert got['names'] == [f'UCX_Wall_AGR_ucx__{i:02d}' for i in range(1, got['pieces_count'] + 1)]
        assert got['triangles'] < got['limit']
        assert got['status'] == 'pass'
        assert got['audit']['collision'] == []
        matched += 1
    assert matched == 4
    assert cases['passage'] and core.build(*cases['passage'], mesh='Wall')['pieces_count'] == 2
    assert core.build(*cases['passage'], mesh='Wall')['triangles'] == 24

    rng = random.Random(728)
    agreed = 0
    for _ in range(12):
        count = rng.randint(1, 3)
        boxes = []
        cursor = 0.0
        for _item in range(count):
            span = rng.uniform(0.6, 2.5)
            height = rng.uniform(0.6, 3.0)
            boxes.append(((cursor, 0.0, 0.0), (cursor + span, span, height)))
            cursor += span + rng.choice((0.0, 2.0))
        verts, tris = _scene(*boxes)
        got = core.build(verts, tris, mesh='Rand')
        exp_pieces, exp = uv.build(got['variant'], np.array(verts, float), np.array(tris, np.int64),
                                    model_triangles=len(tris), hull_fn=_exact_source_hull(verts, tris))
        assert got['pieces_count'] == exp['pieces'] == len(exp_pieces)
        assert got['triangles'] == exp['triangles']
        agreed += 1
    assert agreed == 12


def test_ucx_fail_closed_names_unmapped_kind_and_refuses_alias(tmp_path):
    core = _load(UCX_CORE, 'agr_ucx_core_fail')
    verts, tris = _scene(((0, 0, 0), (1, 1, 1)))
    with pytest.raises(ValueError, match='empty'):
        core.build([], [], mesh='Wall')
    with pytest.raises(ValueError, match='non-finite'):
        core.build([(0.0, math.nan, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)], mesh='Wall')
    with pytest.raises(ValueError, match='non-finite'):
        core.build([(0.0, math.inf, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)], mesh='Wall')
    with pytest.raises(ValueError, match='part-boxes'):
        core.build(verts, tris, mesh='Wall', kind='part-boxes')
    with pytest.raises(ValueError, match='at_threshold'):
        core.kind_from_outside(0.05, bands=1)
    verdict = core.budget_verdict(12, 12)
    assert verdict['status'] == 'fail' and verdict['code'] == 'at_threshold'
    assert core.budget_verdict(12, 15000)['status'] == 'pass'
    with pytest.raises(ValueError, match='exceed'):
        core.budget_verdict(13, 12)
    source = tmp_path / 'in.json'
    source.write_bytes(b'{"keep": true}\n')
    before = source.read_bytes()
    with pytest.raises(ValueError, match='input'):
        core.publish(source, source, {'status': 'fail'})
    assert source.read_bytes() == before
    assert not (tmp_path / 'in.json.partial').exists()
    report = tmp_path / 'report.json'
    core.publish(source, tmp_path / 'out.json', {'status': 'pass'}, report=report)
    assert (tmp_path / 'out.json').is_file() and report.is_file()
    assert source.read_bytes() == before


def test_texel_matches_readout_and_fail_closed(tmp_path):
    core = _load(TEXEL_CORE, 'agr_texel_core_parity')
    from dt_ai.ops.texel_density_readout import readout

    face = _quad()
    payload = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [face]}
    got = core.summarize(payload)
    exp = readout(payload)
    assert exp['status'] == 'pass'
    assert got['meshes'][0]['min_px_per_m'] == pytest.approx(exp['faces'][0]['px_per_m'], rel=1e-9)
    assert got['meshes'][0]['median_px_per_m'] == pytest.approx(exp['faces'][0]['px_per_m'], rel=1e-9)
    assert got['materials'][0]['min_px_per_m'] == pytest.approx(exp['materials'][0]['min_px_per_m'], rel=1e-9)
    assert got['status'] == 'pass'
    small = dict(face)
    small['uv'] = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]
    planted_payload = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [small]}
    planted = core.summarize(planted_payload)
    planted_exp = readout(planted_payload)
    assert planted['status'] == 'fail'
    assert planted['meshes'][0]['min_px_per_m'] == pytest.approx(planted_exp['faces'][0]['px_per_m'], rel=1e-9)
    assert planted_exp['faces'][0]['px_per_m'] < 512

    rng = random.Random(7281)
    agreed = 0
    for index in range(16):
        span = rng.uniform(0.4, 3.0)
        uv = rng.uniform(0.2, 1.5)
        px = rng.choice((512, 1024, 2048))
        sample = {
            'id': f'f{index}', 'mesh': 'M', 'material': 'brick',
            'xyz': [(0.0, 0.0, 0.0), (span, 0.0, 0.0), (span, span, 0.0), (0.0, span, 0.0)],
            'uv': [(0.0, 0.0), (uv, 0.0), (uv, uv), (0.0, uv)],
        }
        body = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': px}], 'faces': [sample]}
        a = core.summarize(body)
        b = readout(body)
        core.assert_texel_close(a['meshes'][0]['min_px_per_m'], b['faces'][0]['px_per_m'])
        core.assert_texel_close(a['materials'][0]['median_px_per_m'], b['faces'][0]['px_per_m'])
        agreed += 1
    assert agreed == 16

    with pytest.raises(ValueError, match='empty'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': []})
    with pytest.raises(ValueError, match='brick'):
        core.summarize({'profile': 'VPM', 'materials': [], 'faces': [face]})
    with pytest.raises(ValueError, match='stone'):
        core.summarize({'profile': 'NPM', 'materials': [{'name': 'stone'}], 'faces': [dict(face, material='stone')]})
    with pytest.raises(ValueError, match='at_threshold'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 0}], 'faces': [face]})
    nan_face = dict(face, uv=[(0.0, math.nan), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    with pytest.raises(ValueError, match='non-finite'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [nan_face]})
    with pytest.raises(ValueError, match='threshold'):
        core.assert_texel_close(1.0 / (1.0 - 1e-6), 1.0)
    core.assert_texel_close(1.0, 1.0 + 1e-9)
    partial = dict(face)
    partial.pop('mesh')
    dropped = core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [partial, face]})
    assert dropped['status'] == 'fail'
    assert any('mesh' in item['reason'] for item in dropped['dropped'])
    assert {item['face'] for item in dropped['faces']} | {item['face'] for item in dropped['dropped']} == {0, 1}

    source = tmp_path / 'faces.json'
    source.write_text('{"faces": 1}\n', encoding='utf-8')
    before = source.read_bytes()
    with pytest.raises(ValueError, match='input'):
        core.publish(source, source, {'status': 'fail'})
    assert source.read_bytes() == before
    assert not Path(str(source) + '.partial').exists()


def _orient(a, b, c, p):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return nx * (p[0] - a[0]) + ny * (p[1] - a[1]) + nz * (p[2] - a[2])


def _record(**overrides):
    row = {
        'handle': 7,
        'name': 'name_control',
        'base_class': 'Editable_Poly',
        'transform': 'tm-identity',
        'object_transform': 'ot-identity',
        'parent': None,
        'properties': '',
        'material': None,
        'vertices': [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
        'faces': [(0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2)],
    }
    row.update(overrides)
    return row


def test_hull_brute_force_probe_and_fail_closed_volume():
    """Every generated cloud stays inside a closed hull. Exactly the flat limit is an error."""
    core = _load(UCX_CORE, 'agr_ucx_core_hull_probe')
    verts, tris = _clipped_cube()
    hull_v, hull_t = core._convex_hull(verts)
    assert len(hull_v) == 10 and len(hull_t) == 16
    assert core._volume(hull_v, hull_t) == pytest.approx(0.9986666666666665, abs=1e-12)
    cube_v, cube_t = _scene(((0, 0, 0), (1, 1, 1)))
    box_v, box_t = core._convex_hull(cube_v)
    assert len(box_t) == 12 and core._volume(box_v, box_t) == pytest.approx(1.0, abs=1e-12)

    rng = random.Random(7282)
    agreed = 0
    for _ in range(16):
        cloud = [(rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-3, 3))
                 for _point in range(rng.randint(5, 14))]
        hv, ht = core._convex_hull(cloud)
        edges = {}
        for a, b, c in ht:
            for edge in ((a, b), (b, c), (c, a)):
                key = tuple(sorted(edge))
                edges[key] = edges.get(key, 0) + 1
        assert set(edges.values()) == {2}
        span = max(max(p[axis] for p in hv) - min(p[axis] for p in hv) for axis in range(3))
        eps = max(span, 1.0) ** 3 * 1e-8
        for point in cloud:
            for face in ht:
                assert _orient(hv[face[0]], hv[face[1]], hv[face[2]], point) <= eps
        assert core._volume(hv, ht) > core.HULL_VOLUME_MIN
        agreed += 1
    assert agreed == 16

    with pytest.raises(ValueError, match='empty'):
        core._convex_hull([])
    with pytest.raises(ValueError, match='partial'):
        core._convex_hull([(0.0, 0.0)])
    with pytest.raises(ValueError, match='non-finite'):
        core._convex_hull([(0.0, math.nan, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])
    with pytest.raises(ValueError, match='non-finite'):
        core._convex_hull([(0.0, math.inf, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])
    with pytest.raises(ValueError, match='flat'):
        core._convex_hull([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.2, 0.2, 0.0)])
    with pytest.raises(ValueError, match='at_threshold'):
        core.accept_hull_volume(core.HULL_VOLUME_MIN)
    assert core.accept_hull_volume(core.HULL_VOLUME_MIN * 0.5) == 'flat'
    assert core.accept_hull_volume(1.0) == 'hull'
    built = core.build(verts, tris, mesh='Clipped')
    assert built['triangles'] == 16 and built['status'] == 'pass'
    assert built['kind'] == 'near-convex-box'
    assert len(built['pieces'][0][0]) == 10
    assert core._volume(*built['pieces'][0]) == pytest.approx(0.9986666666666665, abs=1e-12)
    intact = core.build(*_scene(((0, 0, 0), (1, 1, 1))), mesh='Intact', kind='near-convex-box')
    assert intact['pieces_count'] == 1 and intact['triangles'] == 12
    assert core._volume(*intact['pieces'][0]) == pytest.approx(1.0, abs=1e-12)


# Seed 730, case 2: unit cube, x=1 triangle split around an interior coplanar point.
WITNESS_POINTS = (
    (0, 0, 1), (0, 1, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1), (0, 0, 0), (1, 0, 1),
    (1.0, 0.7393781378034694, 0.3406598426925462), (0, 1, 0),
)
WITNESS_FACES = (
    (5, 3, 2), (5, 8, 3), (0, 6, 4), (0, 4, 1), (5, 2, 6), (5, 6, 0), (2, 4, 6),
    (3, 8, 1), (3, 1, 4), (8, 5, 0), (8, 0, 1), (2, 3, 7), (3, 4, 7), (4, 2, 7),
)


def _hull_closed_convex(core, verts, tris, volume):
    edges = {}
    for a, b, c in tris:
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(edge))
            edges[key] = edges.get(key, 0) + 1
    assert set(edges.values()) == {2}
    span = max(max(p[axis] for p in verts) - min(p[axis] for p in verts) for axis in range(3))
    limit = max(span, 1.0) * 1e-6
    for index, point in enumerate(verts):
        for face in tris:
            assert _orient(verts[face[0]], verts[face[1]], verts[face[2]], point) <= limit
    assert len(tris) == 12 and len(verts) == 8
    assert core._volume(verts, tris) == pytest.approx(volume, abs=1e-9)


def _subdivide_triangle(points, faces, face, rng):
    points = list(points)
    faces = [tuple(face) for face in faces]
    weights = [rng.random() + 0.05 for _ in range(3)]
    total = sum(weights)
    extra = tuple(sum(points[index][axis] * weight / total for index, weight in zip(face, weights))
                  for axis in range(3))
    new = len(points)
    points.append(extra)
    a, b, c = face
    faces.remove(face)
    faces.extend(((a, b, new), (b, c, new), (c, a, new)))
    return points, faces


def test_coplanar_face_point_keeps_the_cube_hull():
    """An interior point of a cube face is the same convex solid: 1 piece, 12 triangles, volume 1."""
    core = _load(UCX_CORE, 'agr_ucx_core_coplanar')
    hull_v, hull_t = core._convex_hull(WITNESS_POINTS)
    _hull_closed_convex(core, hull_v, hull_t, 1.0)
    built = core.build(WITNESS_POINTS, WITNESS_FACES, mesh='subdiv', kind='near-convex-box')
    assert built['pieces_count'] == 1 and built['triangles'] == 12 and built['status'] == 'pass'
    assert built['audit']['closed'] is True and built['audit']['collision'] == [] and built['audit']['unmeasurable'] == []
    assert built['names'] == ['UCX_subdiv_AGR_ucx__01']
    assert core._volume(*built['pieces'][0]) == pytest.approx(1.0, abs=1e-9)

    agreed = 0
    for seed in range(120):
        order = list(range(len(WITNESS_POINTS)))
        random.Random(seed).shuffle(order)
        points = [WITNESS_POINTS[index] for index in order]
        hull_v, hull_t = core._convex_hull(points)
        _hull_closed_convex(core, hull_v, hull_t, 1.0)
        agreed += 1
    assert agreed == 120

    base, faces = _box((0, 0, 0), (1, 1, 1)), list(BOX_T)
    variants = 0
    rng = random.Random(730)
    for face in BOX_T:
        for sample in range(8):
            points, tris = _subdivide_triangle(base, faces, face, rng)
            order = list(range(len(points)))
            random.Random(9000 + variants).shuffle(order)
            remap = {old: new for new, old in enumerate(order)}
            shuffled = [points[index] for index in order]
            hull_v, hull_t = core._convex_hull(shuffled)
            _hull_closed_convex(core, hull_v, hull_t, 1.0)
            built = core.build(shuffled, [tuple(remap[index] for index in tri) for tri in tris],
                               mesh='face', kind='near-convex-box')
            assert built['pieces_count'] == 1 and built['triangles'] == 12 and built['status'] == 'pass'
            variants += 1
    assert variants == 12 * 8

    clipped_v, clipped_t = core._convex_hull(_clipped_cube()[0])
    assert len(clipped_t) == 16 and len(clipped_v) == 10
    assert core._volume(clipped_v, clipped_t) == pytest.approx(0.9986666666666665, abs=1e-12)
    cube_v, cube_t = core._convex_hull(_scene(((0, 0, 0), (1, 1, 1)))[0])
    assert len(cube_t) == 12 and core._volume(cube_v, cube_t) == pytest.approx(1.0, abs=1e-12)


def test_failed_piece_audit_is_not_publishable():
    core = _load(UCX_CORE, 'agr_ucx_core_audit_gate')
    clean = {'collision': [], 'unmeasurable': [], 'mask_bad_count': 1, 'closed': True}
    assert core.assert_emitted_audit(clean) is None
    with pytest.raises(ValueError, match='ucx audit failed'):
        core.assert_emitted_audit({'collision': [], 'unmeasurable': ['non-convex'], 'mask_bad_count': 1, 'closed': False})
    with pytest.raises(ValueError, match='intersect'):
        core.assert_emitted_audit({'collision': ['intersect'], 'unmeasurable': [], 'mask_bad_count': 0, 'closed': True})
    with pytest.raises(ValueError, match='partial ucx audit'):
        core.assert_emitted_audit({'closed': True})


def test_world_metres_brute_force_and_bounds_threshold():
    core = _load(UCX_CORE, 'agr_ucx_core_world')
    rng = random.Random(7283)
    agreed = 0
    for _ in range(24):
        points = [(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-20, 20))
                  for _point in range(rng.randint(1, 8))]
        rows = tuple(
            (rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2))
            for _row in range(3)
        ) + ((rng.uniform(-30, 30), rng.uniform(-30, 30), rng.uniform(-30, 30)),)
        to_m = rng.choice((1.0, 0.01, 0.001))
        got = core.world_metres(points, rows, to_m)
        matrix = np.array([
            [rows[0][0], rows[0][1], rows[0][2]],
            [rows[1][0], rows[1][1], rows[1][2]],
            [rows[2][0], rows[2][1], rows[2][2]],
        ], float)
        origin = np.array(rows[3], float)
        expect = [tuple((np.array(point, float) @ matrix + origin) * to_m) for point in points]
        for left, right in zip(got, expect):
            assert left == pytest.approx(right, abs=1e-9)
        agreed += 1
    assert agreed == 24
    with pytest.raises(ValueError, match='empty'):
        core.world_metres([], ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)), 1.0)
    with pytest.raises(ValueError, match='partial'):
        core.world_metres([(0.0, 1.0)], ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)), 1.0)
    with pytest.raises(ValueError, match='non-finite'):
        core.world_metres([(0.0, math.nan, 0.0)], ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)), 1.0)
    with pytest.raises(ValueError, match='non-finite'):
        core.world_metres([(0.0, 0.0, 0.0)], ((1, 0, 0), (0, 1, math.inf), (0, 0, 1), (0, 0, 0)), 1.0)
    with pytest.raises(ValueError, match='at_threshold'):
        core.world_metres([(0.0, 0.0, 0.0)], ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)), 0.0)
    with pytest.raises(ValueError, match='invalid system units'):
        core.world_metres([(0.0, 0.0, 0.0)], ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)), -1.0)
    same = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    core.assert_world_bounds(same, same)
    moved = ((0.0, 0.0, 0.0), (1.0 + core.BOUNDS_TOL_M, 1.0, 1.0))
    with pytest.raises(ValueError, match='at_threshold'):
        core.assert_world_bounds(same, moved)
    with pytest.raises(ValueError, match='emitted world bounds'):
        core.assert_world_bounds(same, ((0.0, 0.0, 0.0), (2.0, 1.0, 1.0)))
    with pytest.raises(ValueError, match='empty'):
        core.assert_world_bounds((), same)
    with pytest.raises(ValueError, match='partial'):
        core.assert_world_bounds(((0.0, 0.0), (1.0, 1.0, 1.0)), same)
    with pytest.raises(ValueError, match='non-finite'):
        core.assert_world_bounds(((0.0, 0.0, math.nan), (1.0, 1.0, 1.0)), same)


def test_name_reservation_is_before_side_effects_and_bound_to_the_mesh():
    core = _load(UCX_CORE, 'agr_ucx_core_names')
    export, pieces = core.ucx_export_names('name_control', 1)
    assert export == 'name_control_AGR_ucx_'
    assert pieces == ['UCX_name_control_AGR_ucx__01']
    assert core.assert_ucx_names_bound('name_control', pieces) == (export, pieces)
    with pytest.raises(ValueError, match='UCX_other_01'):
        core.assert_ucx_names_bound('name_control', ['UCX_other_01'])
    with pytest.raises(ValueError, match='unmapped mesh name'):
        core.ucx_export_names('  ', 1)
    with pytest.raises(ValueError, match='empty'):
        core.ucx_export_names('name_control', 0)

    existing = ['name_control', 'keep_me']
    snapshot = list(existing)
    with pytest.raises(ValueError, match='occupied name UCX_name_control_AGR_ucx__01'):
        core.reserve_ucx_names(existing + ['UCX_name_control_AGR_ucx__01'], [(export, pieces)])
    assert existing == snapshot
    with pytest.raises(ValueError, match='occupied name twin_AGR_ucx_'):
        core.reserve_ucx_names([], [( 'twin_AGR_ucx_', ['UCX_twin_01']), ('twin_AGR_ucx_', ['UCX_twin_01'])])
    reserved = core.reserve_ucx_names(['name_control'], [(export, pieces)])
    assert reserved == [export, *pieces]
    assert existing == snapshot

    rng = random.Random(7284)
    agreed = 0
    for _ in range(12):
        mesh = 'm' + str(rng.randrange(1000))
        export_name, piece_names = core.ucx_export_names(mesh, rng.randint(1, 4))
        occupied = rng.choice([export_name, *piece_names])
        scene = [mesh, 'other', occupied]
        before = list(scene)
        with pytest.raises(ValueError, match='occupied name ' + occupied):
            core.reserve_ucx_names(scene, [(export_name, piece_names)])
        assert scene == before
        agreed += 1
    assert agreed == 12
    with pytest.raises(ValueError, match='empty'):
        core.reserve_ucx_names([], [])
    with pytest.raises(ValueError, match='unmapped mesh name'):
        core.reserve_ucx_names([''], [(export, pieces)])
    with pytest.raises(ValueError, match='unmapped mesh name'):
        core.reserve_ucx_names(['ok'], [('', pieces)])


def test_preview_digest_binds_geometry_transform_identity_and_properties():
    core = _load(UCX_CORE, 'agr_ucx_core_digest')
    original = [_record()]
    assert core.geometry_digest(original) == core.geometry_digest([_record()])
    core.assert_preview_current(original, [_record()])
    moved = [_record(vertices=[(0.0, 0.0, 10.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])]
    with pytest.raises(ValueError, match='stale'):
        core.assert_preview_current(original, moved)
    assert core.geometry_digest(original) != core.geometry_digest(moved)
    exact = [_record(vertices=[(core.DIGEST_TOL_M, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])]
    with pytest.raises(ValueError, match='at_threshold'):
        core.assert_preview_current(original, exact)
    for key, value in (
        ('handle', 8), ('name', 'other'), ('base_class', 'Editable_Mesh'),
        ('transform', 'tm-moved'), ('object_transform', 'ot-moved'), ('parent', 3),
        ('properties', 'AGR_UCX_KIND=passage'), ('material', 'brick'),
    ):
        changed = [_record(**{key: value})]
        with pytest.raises(ValueError, match='stale'):
            core.assert_preview_current(original, changed)
    with pytest.raises(ValueError, match='empty'):
        core.geometry_digest([])
    with pytest.raises(ValueError, match='unmapped key material'):
        row = _record()
        row.pop('material')
        core.geometry_digest([row])
    with pytest.raises(ValueError, match='unmapped key extra'):
        core.geometry_digest([{**_record(), 'extra': 1}])
    with pytest.raises(ValueError, match='partial'):
        core.geometry_digest([_record(vertices=[(0.0, 1.0)])])
    with pytest.raises(ValueError, match='non-finite'):
        core.geometry_digest([_record(vertices=[(0.0, math.nan, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])])
    with pytest.raises(ValueError, match='non-finite'):
        core.geometry_digest([_record(transform='nan')]) is None or True
    rng = random.Random(7285)
    agreed = 0
    for index in range(8):
        vertex = (rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(-5, 5))
        left = [_record(name=f'n{index}', vertices=[vertex, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])]
        right = [_record(name=f'n{index}', vertices=[vertex, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])]
        assert core.geometry_digest(left) == core.geometry_digest(right)
        nudged = [_record(name=f'n{index}', vertices=[(vertex[0] + 0.25, vertex[1], vertex[2]),
                                                      (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])]
        with pytest.raises(ValueError, match='stale'):
            core.assert_preview_current(left, nudged)
        agreed += 1
    assert agreed == 8


class _P:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __mul__(self, tm):
        x, y, z = self.x, self.y, self.z
        r1, r2, r3, r4 = tm.rows
        return _P(
            x * r1[0] + y * r2[0] + z * r3[0] + r4[0],
            x * r1[1] + y * r2[1] + z * r3[1] + r4[1],
            x * r1[2] + y * r2[2] + z * r3[2] + r4[2],
        )


class _Matrix:
    def __init__(self, rows):
        self.rows = tuple(tuple(float(c) for c in row) for row in rows)

    def __str__(self):
        return 'tm:' + repr(self.rows)


class _Kind:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, _Kind) and self.name == other.name

    def __repr__(self):
        return self.name


class _Face:
    def __init__(self, indexes):
        self._indexes = tuple(indexes)
        self.count = len(self._indexes)
        self.x = self._indexes[0] if self.count > 0 else 0
        self.y = self._indexes[1] if self.count > 1 else 0
        self.z = self._indexes[2] if self.count > 2 else 0

    def __getitem__(self, index):
        return self._indexes[index]


class _Tri:
    def __init__(self, verts, faces):
        self.verts = [tuple(v) for v in verts]
        self.faces = [tuple(f) for f in faces]
        self.numverts = len(self.verts)
        self.numfaces = len(self.faces)


class _Base:
    def __init__(self, kind, verts, faces):
        self.kind = kind
        self.local = [tuple(v) for v in verts]
        self.faces = [tuple(f) for f in faces]


class _Node:
    def __init__(self, name, handle, kind, verts, faces, world=None, modifiers=(), rows=None):
        self.name = name
        self.handle = handle
        self.baseObject = _Base(kind, verts, faces)
        self.local = self.baseObject.local
        self.faces = self.baseObject.faces
        self.world = [tuple(v) for v in (world if world is not None else verts)]
        self.world_faces = [tuple(f) for f in faces]
        self.modifiers = list(modifiers)
        self.material = None
        self.parent = None
        self.props = {}
        self.buffer = ''
        identity = rows or ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0))
        self.transform = _Matrix(identity)
        self.objectTransform = _Matrix(identity)


class _Runtime:
    def __init__(self):
        self.Editable_Poly = _Kind('Editable_Poly')
        self.Editable_Mesh = _Kind('Editable_Mesh')
        self.objects = []
        self.selection = []
        self._handles = 10
        self.units = self

    def decodeValue(self, text):
        if text != '1m':
            raise ValueError('unmapped unit ' + text)
        return 1.0

    def isValidNode(self, node):
        return isinstance(node, _Node)

    def canConvertTo(self, node, kind):
        return isinstance(node, _Node)

    def classOf(self, obj):
        return obj.kind

    def getHandleByAnim(self, node):
        return int(node.handle)

    def getUserProp(self, node, key):
        return node.props.get(key)

    def getUserPropBuffer(self, node):
        return node.buffer

    def select(self, nodes):
        self.selection = list(nodes)

    def point3(self, x, y, z):
        return _P(x, y, z)

    def snapshotAsMesh(self, node):
        return _Tri(node.world, node.world_faces)

    def getVert(self, mesh, index):
        # Max 2024: polyop.getVert(node) is world space; meshop.getVert(base) is object space.
        if isinstance(mesh, _Node) and getattr(mesh.baseObject, 'kind', None) == self.Editable_Poly:
            return _P(*mesh.world[index - 1])
        verts = mesh.verts if hasattr(mesh, 'verts') else mesh.local
        return _P(*verts[index - 1])

    def getFace(self, mesh, index):
        return _Face([i + 1 for i in mesh.faces[index - 1]])

    def getNumVerts(self, target):
        return len(target.local)

    def getNumFaces(self, target):
        return len(target.faces)

    def getFaceVerts(self, target, index):
        return _Face([i + 1 for i in target.faces[index - 1]])

    def convertToPoly(self, node):
        return node

    def copy(self, node):
        self._handles += 1
        clone = _Node(node.name, self._handles, node.baseObject.kind, node.local, node.faces,
                      node.world, node.modifiers, node.objectTransform.rows)
        clone.world_faces = list(node.world_faces)
        clone.buffer = node.buffer
        clone.props = dict(node.props)
        self.objects.append(clone)
        return clone

    def mesh(self, name, vertices, faces):
        self._handles += 1
        verts = [(v.x, v.y, v.z) for v in vertices]
        tris = []
        for face in faces:
            tris.append((int(face.x) - 1, int(face.y) - 1, int(face.z) - 1))
        node = _Node(name, self._handles, self.Editable_Poly, verts, tris, verts)
        self.objects.append(node)
        return node

    def delete(self, nodes):
        if isinstance(nodes, _Node):
            nodes = [nodes]
        for node in list(nodes):
            if node in self.objects:
                self.objects.remove(node)

    def getNodeByName(self, name):
        for node in self.objects:
            if node.name == name:
                return node
        return None

    polyop = None
    meshop = None


def _bind_runtime():
    rt = _Runtime()
    rt.polyop = rt
    rt.meshop = rt
    agr = _load(RUNTIME, 'agr_runtime_ucx_review')
    agr._rt = lambda: rt
    return agr, rt


def _add_box(rt, name, kind, world=None, rows=None, modifiers=()):
    verts = _box((-0.5, -0.5, 0.0), (0.5, 0.5, 1.0))
    rt._handles += 1
    node = _Node(name, rt._handles, rt.Editable_Mesh if kind == 'mesh' else rt.Editable_Poly,
                 verts, BOX_T, world if world is not None else verts, modifiers, rows)
    rt.objects.append(node)
    return node


def _bounds(points):
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def test_runtime_read_world_uses_evaluated_metres_for_mesh_poly_and_modifiers():
    agr, rt = _bind_runtime()
    rows = ((2, 0, 0), (0, 2, 0), (0, 0, 2), (20, 30, 40))
    local = _box((-0.5, -0.5, 0.0), (0.5, 0.5, 1.0))
    world = [(20 + 2 * x, 30 + 2 * y, 40 + 2 * z) for x, y, z in local]
    expected = ((19.0, 29.0, 40.0), (21.0, 31.0, 42.0))
    for kind in ('mesh', 'poly'):
        node = _add_box(rt, 'mesh_transform_' + kind, kind, world, rows)
        before = len(rt.objects)
        verts, _tris = agr._read_world(node)
        assert _bounds(verts) == expected
        assert len(rt.objects) == before
        preview = agr.ucx_preview([node])
        created, report = agr.ucx_apply([node], preview)
        assert report['status'] == 'pass'
        emitted = [item for item in created if str(item.name).startswith('UCX_')]
        assert len(emitted) == 1
        got = _bounds(emitted[0].world)
        for corner, exp in zip(got, expected):
            assert corner == pytest.approx(exp, abs=1e-9)
        assert _bounds(node.world) == expected
    plain_rows = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (5, 6, 7))
    plain_world = [(5 + x, 6 + y, 7 + z) for x, y, z in local]
    plain = _add_box(rt, 'plain_transform', 'poly', plain_world, plain_rows)
    assert _bounds(agr._read_world(plain)[0]) == ((4.5, 5.5, 7.0), (5.5, 6.5, 8.0))
    shifted = [(10 + x, y, z) for x, y, z in local]
    modifier = _add_box(rt, 'modifier_stack', 'poly', shifted, modifiers=['XForm'])
    assert _bounds(agr._read_world(modifier)[0]) == ((9.5, -0.5, 0.0), (10.5, 0.5, 1.0))
    bad = _add_box(rt, 'non_finite', 'mesh')
    bad.world = [(0.0, 0.0, math.nan)] + bad.world[1:]
    with pytest.raises(ValueError, match='non-finite'):
        agr._read_world(bad)
    empty = _add_box(rt, 'empty_world', 'poly')
    empty.world = []
    empty.world_faces = []
    with pytest.raises(ValueError, match='empty'):
        agr._read_world(empty)
    partial = _add_box(rt, 'partial_world', 'mesh')
    partial.world_faces = [(0, 1)]
    with pytest.raises(ValueError, match='partial'):
        agr._read_world(partial)


def test_runtime_stale_preview_and_occupied_names_create_no_nodes():
    agr, rt = _bind_runtime()
    node = _add_box(rt, 'stale', 'poly')
    preview = agr.ucx_preview([node])
    before = len(rt.objects)
    node.world = [(10 + x, y, z) for x, y, z in node.world]
    node.transform = _Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1), (10, 0, 0)))
    node.objectTransform = node.transform
    with pytest.raises(ValueError, match='stale'):
        agr.ucx_apply([node], preview)
    assert len(rt.objects) == before

    agr, rt = _bind_runtime()
    node = _add_box(rt, 'name_control', 'poly')
    preview = agr.ucx_preview([node])
    first, report = agr.ucx_apply([node], preview)
    assert [item.name for item in first] == ['name_control_AGR_ucx_', 'UCX_name_control_AGR_ucx__01']
    assert report['status'] == 'pass'
    again = agr.ucx_preview([node])
    before = len(rt.objects)
    with pytest.raises(ValueError, match='occupied name'):
        agr.ucx_apply([node], again)
    assert len(rt.objects) == before
    assert sorted(item.name for item in rt.objects if str(item.name).startswith('UCX_name_control')) == [
        'UCX_name_control_AGR_ucx__01']

    agr, rt = _bind_runtime()
    node = _add_box(rt, 'name_control', 'poly')
    planted = _add_box(rt, 'UCX_name_control_AGR_ucx__01', 'mesh')
    preview = agr.ucx_preview([node])
    before = len(rt.objects)
    with pytest.raises(ValueError, match='occupied name UCX_name_control_AGR_ucx__01'):
        agr.ucx_apply([node], preview)
    assert len(rt.objects) == before
    assert planted in rt.objects

    agr, rt = _bind_runtime()
    node = _add_box(rt, 'audit_fail', 'poly')
    real_preview = agr.ucx_preview

    def failed(nodes=None):
        got = real_preview(nodes)
        for plan in got['plans']:
            plan['audit']['closed'] = False
            plan['audit']['unmeasurable'] = ['non-convex']
            plan['status'] = 'fail'
        got['report']['plan']['audit']['closed'] = False
        got['report']['plan']['audit']['unmeasurable'] = ['non-convex']
        got['report']['status'] = 'fail'
        got['report']['objects'][0]['findings'].append(
            {'code': 'ucx_unmeasurable', 'ids': [1], 'detail': 'non-convex'})
        return got

    agr.ucx_preview = failed
    preview = failed([node])
    before = list(rt.objects)
    with pytest.raises(ValueError, match='ucx audit failed'):
        agr.ucx_apply([node], preview)
    assert rt.objects == before

    agr, rt = _bind_runtime()
    left = _add_box(rt, 'twin', 'poly')
    right = _add_box(rt, 'twin', 'mesh')
    preview = agr.ucx_preview([left, right])
    before = len(rt.objects)
    with pytest.raises(ValueError, match='occupied name twin_AGR_ucx_'):
        agr.ucx_apply([left, right], preview)
    assert len(rt.objects) == before
