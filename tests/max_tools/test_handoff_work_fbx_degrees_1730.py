"""#1730: the handoff work FBX keeps quads - face-degree readback of the exported FBX (no Max, no Blender).

3ds Max 2026.3 (fbxmax.dlu 28.3.0.30732, FBX SDK 2020.3.9) measured 2026-11-21: `exportFile ... #noPrompt` honours
`FBXExporterSetParam "Triangulate" false` for Editable_Poly / Box / Edit_Poly (6 quads), but an Editable_Mesh or
an Edit_Mesh on top of the stack exports 12 triangles, and the interactive FBX dialog applies its saved preset
(Triangulate on) over the script parameters. The Max export cannot run in CI, so the regression sits on the readback:
`handoff_core.fbx_polygon_degrees` + `handoff_core.work_fbx_degree_findings`.
"""
from __future__ import annotations

import importlib.util
import itertools
import math
import os
import random
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters' / 'max' / 'agr_tools'


def _load(name, key):
    spec = importlib.util.spec_from_file_location(key, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load('handoff_core.py', 'agr_tools_handoff_core_1730')

# ---- binary FBX 7400 / 7500 writer (same layout as the Max 2026 exporter: Geometry/Model/Connections) ------------


def _prop(v):
    if isinstance(v, int):
        return b'L' + struct.pack('<q', v)
    raw = v.encode('utf-8')
    return b'S' + struct.pack('<I', len(raw)) + raw


def _array(code, values, compress=True):
    raw = struct.pack('<' + {'d': 'd', 'i': 'i'}[code] * len(values), *values)
    blob = zlib.compress(raw) if compress else raw
    return code.encode() + struct.pack('<III', len(values), 1 if compress else 0, len(blob)) + blob


def _node(name, props=b'', nprops=0, children=(), at=0, v75=False):
    head = (25 if v75 else 13) + len(name)
    kids, pos = b'', at + head + len(props)
    for c in children:
        blob = _node(*c, at=pos, v75=v75)
        kids += blob
        pos += len(blob)
    if children:
        kids += b'\x00' * (25 if v75 else 13)
    end = at + head + len(props) + len(kids)
    fmt = '<QQQ' if v75 else '<III'
    return struct.pack(fmt, end, nprops, len(props)) + bytes([len(name)]) + name.encode() + props + kids


def binary_fbx(meshes, version=7400, compress=True):
    """meshes: [(name, verts flat, polygons [[i, ...]])] -> binary FBX."""
    objects, links = [], []
    for i, (name, verts, polys) in enumerate(meshes):
        gid, mid = 1000 + i, 2000 + i
        index = list(itertools.chain.from_iterable(p[:-1] + [~p[-1]] for p in polys))
        gprops = _prop(gid) + _prop('Geometry::' + name) + _prop('Mesh')
        objects.append(('Geometry', gprops, 3, [('Vertices', _array('d', verts, compress), 1, ()),
                                                ('PolygonVertexIndex', _array('i', index, compress), 1, ())]))
        objects.append(('Model', _prop(mid) + _prop(name + '\x00\x01Model') + _prop('Mesh'), 3, ()))
        links.append(('C', _prop('OO') + _prop(gid) + _prop(mid), 3, ()))
        links.append(('C', _prop('OO') + _prop(mid) + b'L' + struct.pack('<q', 0), 3, ()))
    v75 = version >= 7500
    out = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', version)
    for name, kids in (('Objects', objects), ('Connections', links)):
        out += _node(name, b'', 0, kids, at=len(out), v75=v75)
    return out + b'\x00' * (25 if v75 else 13)


BOX_V = [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1]
BOX_QUADS = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
BOX_TRIS = [t for q in BOX_QUADS for t in ([q[0], q[1], q[2]], [q[0], q[2], q[3]])]
QUAD_SRC = {'4': 6}  # handoff_core.object_facts degrees of the Editable_Poly box in the scene


def quad_ref():
    """Reference quad work FBX: the Max 2026 batch export of an Editable_Poly box (6 quads)."""
    return binary_fbx([('Q_poly', BOX_V, BOX_QUADS)])


def tri_ref():
    """Reference triangulated FBX: the same box as Max writes it from an Editable_Mesh / the dialog (12 tris)."""
    return binary_fbx([('Q_poly', BOX_V, BOX_TRIS)])


# ---- readback -------------------------------------------------------------------------------------------------
def test_readback_quad_and_triangulated_reference():
    assert core.fbx_polygon_degrees(quad_ref()) == {'Q_poly': {'4': 6}}
    assert core.fbx_polygon_degrees(tri_ref()) == {'Q_poly': {'3': 12}}


def test_quad_reference_passes_triangulated_reference_fails():
    assert core.work_fbx_degree_findings({'Q_poly': QUAD_SRC}, core.fbx_polygon_degrees(quad_ref())) == []
    bad = core.work_fbx_degree_findings({'Q_poly': QUAD_SRC}, core.fbx_polygon_degrees(tri_ref()))
    assert [n for n, _d in bad] == ['Q_poly'] and 'triangulated' in bad[0][1]


def test_check_reads_the_fbx_bytes():
    """The export gate: bytes in, findings out; the triangulated file fails with the object name."""
    assert core.check_work_fbx({'Q_poly': QUAD_SRC}, quad_ref()) == []
    assert core.check_work_fbx({'Q_poly': QUAD_SRC}, tri_ref())[0][0] == 'Q_poly'


@pytest.mark.parametrize('version', [7400, 7500])
@pytest.mark.parametrize('compress', [True, False])
def test_versions_and_encodings(version, compress):
    data = binary_fbx([('Q_poly', BOX_V, BOX_QUADS), ('Т_кириллица', BOX_V, BOX_TRIS)], version, compress)
    assert core.fbx_polygon_degrees(data) == {'Q_poly': {'4': 6}, 'Т_кириллица': {'3': 12}}


def test_real_max_2026_reference_files_when_present():
    """The Max 2026.3 FBX files of the PR evidence (AGR_1730_EVIDENCE=<dir with batch/ and gui_dialog/>)."""
    ev = os.environ.get('AGR_1730_EVIDENCE')
    if not ev:
        pytest.skip('AGR_1730_EVIDENCE not set (Max evidence lives outside git)')
    read = lambda rel: core.fbx_polygon_degrees(Path(ev, rel).read_bytes())  # noqa: E731
    assert read('batch/poly_tri0.fbx') == {'Q_poly': {'4': 6}}
    assert read('batch/mesh_tri0.fbx') == {'Q_mesh': {'3': 12}}
    assert read('gui_dialog/poly_tri0.fbx') == {'Q_poly': {'3': 12}}
    assert core.check_work_fbx({'Q_poly': QUAD_SRC}, Path(ev, 'batch/poly_tri0.fbx').read_bytes()) == []
    assert core.check_work_fbx({'Q_poly': QUAD_SRC}, Path(ev, 'gui_dialog/poly_tri0.fbx').read_bytes())


# ---- invariants and fail-closed probes -----------------------------------------------------------------------
def test_probe_random_meshes_roundtrip_and_quad_loss():
    """Invariant: readback histogram == written histogram; a source with any face of degree >= 4 whose FBX holds
    only triangles always fails. 300 seeded random meshes."""
    rng = random.Random(1730)
    for _ in range(300):
        polys = [list(range(rng.choice((3, 3, 4, 4, 5, 6)))) for _f in range(rng.randint(1, 12))]
        verts = [0.0] * 3 * 6
        hist = {}
        for p in polys:
            hist[str(len(p))] = hist.get(str(len(p)), 0) + 1
        got = core.fbx_polygon_degrees(binary_fbx([('M', verts, polys)], rng.choice((7400, 7500))))
        assert got == {'M': hist}
        assert core.work_fbx_degree_findings({'M': hist}, got) == []
        tris = sum((len(p) - 2) for p in polys)
        fan = {'M': {'3': tris}}
        bad = core.work_fbx_degree_findings({'M': hist}, fan)
        if any(int(k) >= 4 for k in hist):
            assert bad and 'triangulated' in bad[0][1]
        else:
            assert bad == []


def test_missing_and_unexpected_meshes_are_named():
    bad = core.work_fbx_degree_findings({'A': {'4': 1}, 'B': {'4': 1}}, {'A': {'4': 1}, 'C': {'4': 1}})
    assert ('B', 'missing from the work FBX') in bad
    assert any(n == 'C' and 'not in the exported set' in d for n, d in bad)


def test_partial_degree_loss_is_a_finding():
    """Mixed quads/tris in the FBX where the scene had only quads: not 'only triangles', still a mismatch."""
    bad = core.work_fbx_degree_findings({'A': {'4': 2}}, {'A': {'3': 2, '4': 1}})
    assert bad and 'differ' in bad[0][1]


def test_all_triangle_source_stays_triangles():
    """A scene object that is triangles already is not a quad loss (D312: triangles are reported, not failed)."""
    assert core.work_fbx_degree_findings({'T': {'3': 12}}, {'T': {'3': 12}}) == []


@pytest.mark.parametrize('src', [{}, None])
def test_empty_source_is_an_error(src):
    with pytest.raises(ValueError):
        core.work_fbx_degree_findings(src, {'A': {'4': 1}})


@pytest.mark.parametrize('hist', [{'four': 1}, {'4': -1}, {'2': 1}, {'4': 1.5}, {'4': math.nan}, {'4': 0}])
def test_bad_histograms_are_errors(hist):
    with pytest.raises(ValueError):
        core.work_fbx_degree_findings({'A': hist}, {'A': {'4': 1}})
    with pytest.raises(ValueError):
        core.work_fbx_degree_findings({'A': {'4': 1}}, {'A': hist})


def test_source_without_faces_is_an_error():
    with pytest.raises(ValueError, match='A'):
        core.work_fbx_degree_findings({'A': {}}, {'A': {}})


@pytest.mark.parametrize('data', [b'', b'garbage', b'; FBX 7.4.0 project file\nObjects: {\n}\n',
                                  b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400)])
def test_unreadable_fbx_is_an_error(data):
    with pytest.raises(ValueError):
        core.fbx_polygon_degrees(data)


def test_truncated_fbx_is_an_error():
    data = quad_ref()
    for cut in (40, len(data) // 2, len(data) - 14):
        with pytest.raises(ValueError):
            core.fbx_polygon_degrees(data[:cut])


def test_fbx_without_meshes_is_an_error():
    with pytest.raises(ValueError, match='no mesh'):
        core.fbx_polygon_degrees(binary_fbx([]))


def test_partial_polygon_is_an_error():
    data = binary_fbx([('A', BOX_V, [[0, 1, 2, 3]])])
    # rewrite the index so the last polygon has no closing ~index
    good = struct.pack('<iiii', 0, 1, 2, ~3)
    assert good in data
    with pytest.raises(ValueError, match='partial polygon'):
        core.fbx_polygon_degrees(data.replace(good, struct.pack('<iiii', 0, 1, 2, 3)))


def test_duplicate_mesh_name_is_an_error():
    with pytest.raises(ValueError, match='duplicate'):
        core.fbx_polygon_degrees(binary_fbx([('A', BOX_V, BOX_QUADS), ('A', BOX_V, BOX_QUADS)]))


def test_export_params_still_ask_for_no_triangulation():
    assert dict(core.FBX_EXPORT_PARAMS)['Triangulate'] is False
    assert dict(core.FBX_EXPORT_PARAMS)['ASCII'] is False  # the readback reads binary FBX only
