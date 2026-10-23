"""Hypothesis #603 adoption: corner audit of the TOW02 face-diff centroid/normal matcher."""
import importlib.util
import itertools
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "experiments" / "tow02-hand-finish-face-diff" / "audit_correspondence.py"
spec = importlib.util.spec_from_file_location("audit_correspondence", MOD)
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)

T = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]


@pytest.mark.parametrize("perm", list(itertools.permutations(range(3))))
def test_six_permutations_are_equivalent(perm):
    assert ac.bottleneck(T, [T[i] for i in perm]) == 0.0
    assert ac.triangle_passes(T, [T[i] for i in perm])


def test_exactly_1mm_passes_just_above_fails():
    at = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.001)]
    above = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0010001)]
    assert ac.bottleneck(T, at) == 0.001
    assert ac.triangle_passes(T, at)
    assert not ac.triangle_passes(T, above)


def test_equal_centroid_different_shape_fails():
    other = [(-0.5, 0.0, 0.0), (1.5, 0.0, 0.0), (0.0, 1.0, 0.0)]  # same centroid, same normal, other corners
    c = lambda t: tuple(sum(p[k] for p in t) / 3 for k in range(3))
    assert c(other) == c(T)
    assert ac.bottleneck(T, other) == pytest.approx(0.5)
    assert not ac.triangle_passes(T, other)


def test_face_passes_only_if_all_triangles_pass():
    bad = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.002)]
    assert ac.face_audit([(T, T), (T, T)]) == (True, 0.0, 0)
    ok, worst, idx = ac.face_audit([(T, T), (T, bad)])
    assert (ok, idx) == (False, 1) and worst == pytest.approx(0.002)


@pytest.mark.parametrize("bad", [
    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],                       # partial triangle
    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, math.nan, 0.0)],  # NaN
    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, math.inf, 0.0)],  # inf
])
def test_malformed_triangles_raise(bad):
    with pytest.raises(ac.AuditError):
        ac.bottleneck(T, bad)


@pytest.mark.parametrize("limit", [math.nan, math.inf, -0.001])
def test_bad_limit_raises(limit):
    with pytest.raises(ac.AuditError):
        ac.triangle_passes(T, T, limit)
    with pytest.raises(ac.AuditError):
        ac.face_audit([(T, T)], limit)


def test_empty_face_and_empty_mesh_raise():
    with pytest.raises(ac.AuditError):
        ac.face_audit([])
    with pytest.raises(ac.AuditError):
        ac.audit_meshes([], [], [], [])


def _quad_mesh(dz):
    """Unit quad as source; target = its two first-diagonal triangles with one corner lifted by dz."""
    AV = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    BV = list(AV) + [(1.0, 1.0, dz)]
    BP = [[0, 1, 4], [0, 4, 3]]
    return AV, [[0, 1, 2, 3]], BV, BP


def test_audit_meshes_catches_corner_offset_the_centroid_matcher_accepts():
    # 1.5 mm corner lift moves each centroid by 0.5 mm: pass 1 accepts the face, the corner audit rejects it.
    res = ac.audit_meshes(*_quad_mesh(0.0015))
    assert res["accepted"] == 1 and res["over_limit"] == 1 and res["pass_fraction"] == 0.0
    assert not res["passes_fraction"] and res["delivery_passed"] is False
    assert res["worst_m"] == pytest.approx(0.0015)
    good = ac.audit_meshes(*_quad_mesh(0.0))
    assert (good["accepted"], good["over_limit"], good["passes_fraction"]) == (1, 0, True)


def test_unsupported_polygons_raise():
    AV, AP, BV, BP = _quad_mesh(0.0)
    with pytest.raises(ac.AuditError):
        ac.audit_meshes(AV, AP, BV, [[0, 1, 2, 3]])          # target not triangulated
    with pytest.raises(ac.AuditError):
        ac.audit_meshes(AV + [(2.0, 0.0, 0.0)], [[0, 1, 2, 3, 4]], BV, BP)  # n-gon source


def _cli(*args):
    return subprocess.run([sys.executable, str(MOD), *map(str, args)], capture_output=True, text=True)


def test_cli_refuses_output_that_is_an_input_and_missing_input(tmp_path):
    src = tmp_path / "a.fbx"; src.write_bytes(b"not an fbx")
    before = src.read_bytes()
    r = _cli(src, src, src)
    assert r.returncode == 2 and "resolves to input" in r.stderr
    assert src.read_bytes() == before
    r = _cli(src, src, tmp_path / ".." / tmp_path.name / "a.fbx")   # alias of the input
    assert r.returncode == 2 and src.read_bytes() == before
    out = tmp_path / "o.json"
    r = _cli(tmp_path / "missing.fbx", src, out)
    assert r.returncode == 2 and not out.exists() and not Path(str(out) + ".partial").exists()
    r = _cli(src, src, out)                                              # not an FBX -> error, nothing written
    assert r.returncode == 2 and not out.exists()


SRC_V5 = Path("C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/export-v005/"
              "SM_Vyatskaya_Vl_47_49_013_Main.fbx")
SRC_USER = Path("C:/Users/artsafro/Desktop/!3D viz/NTR/26_Vyatskoe/001 - Моделирование НПМ с нуля/"
                "001 - Моделирование НПМ с нуля/for_placement/0213_Vyatskaya_Vl_47_49_05.fbx")


@pytest.mark.skipif(not (SRC_V5.is_file() and SRC_USER.is_file()), reason="TOW02 real inputs not on this machine")
def test_real_tow02_inputs_reproduce_report(tmp_path):
    v5, user, out = tmp_path / "v5.fbx", tmp_path / "user.fbx", tmp_path / "audit.json"
    shutil.copyfile(SRC_V5, v5); shutil.copyfile(SRC_USER, user)
    r = _cli(v5, user, out)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["inputs"]["sha256"][str(v5)].startswith("ff8994dc")
    assert d["inputs"]["sha256"][str(user)].startswith("2fd80081")
    assert (d["accepted"], d["over_limit"]) == (33256, 5)
    assert [(f["face"], f["target_tri"]) for f in d["over_limit_faces"]] == \
        [(35321, 29005), (35336, 29029), (35380, 29038), (33613, 63297), (33614, 63300)]
    assert d["worst_m"] == pytest.approx(0.001986, abs=1e-6)



# --- R1/R2 (PR #609 review round 1): synthetic binary FBX (synthetic data, not a real object) ---
def _prop(v):
    import struct
    if isinstance(v, str):
        b = v.encode(); return b"S" + struct.pack("<I", len(b)) + b
    if isinstance(v, int):
        return b"L" + struct.pack("<q", v)
    kind, vals = v; b = struct.pack("<%d%s" % (len(vals), kind), *vals)
    return kind.encode() + struct.pack("<III", len(vals), 0, len(b)) + b


def _node(n, start):
    import struct
    name, props, kids = n; name = name.encode(); p = b"".join(_prop(v) for v in props)
    pos = start + 13 + len(name) + len(p); body = b""
    for k in kids:
        b = _node(k, pos); body += b; pos += len(b)
    body += b"\0" * 13; pos += 13
    return struct.pack("<IIIB", pos, len(props), len(p), len(name)) + name + p + body


def _fbx(path, indices):
    import struct
    uv = ("LayerElementUV", [], [("UV", [("d", [0, 0, 1, 0, 0, 1])], []), ("UVIndex", [("i", [0, 1, 2])], [])])
    geo = ("Geometry", [1], [("Vertices", [("d", [0, 0, 0, 1, 0, 0, 0, 1, 0])], []),
                             ("PolygonVertexIndex", [("i", indices)], []), uv])
    model = ("Model", [2, "SM_Vyatskaya_Vl_47_49_013_Main"], [])
    top = [("Objects", [], [geo, model]), ("Connections", [], [("C", ["OO", 1, 2], [])])]
    b = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400)
    for n in top:
        b += _node(n, len(b))
    path.write_bytes(b + b"\0" * 240)


def test_cli_complete_triangle_control_passes(tmp_path):
    a, b, out = tmp_path / "a.fbx", tmp_path / "b.fbx", tmp_path / "o.json"
    _fbx(a, [0, 1, -3]); _fbx(b, [0, 1, -3])
    r = _cli(a, b, out)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text(encoding="utf-8"))
    assert (d["source_faces"], d["target_tris"], d["accepted"], d["over_limit"]) == (1, 1, 1, 0)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.fbx", "b.fbx", "o.json"]   # no temp left


def test_cli_preserves_unrelated_partial_sentinel(tmp_path):
    a, b, out = tmp_path / "a.fbx", tmp_path / "b.fbx", tmp_path / "o.json"
    _fbx(a, [0, 1, -3]); _fbx(b, [0, 1, -3])
    sentinel = Path(str(out) + ".partial"); sentinel.write_bytes(b"UNRELATED USER DATA")
    r = _cli(a, b, out)
    assert r.returncode == 0, r.stderr
    assert sentinel.read_bytes() == b"UNRELATED USER DATA"
    assert json.loads(out.read_text(encoding="utf-8"))["accepted"] == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.fbx", "b.fbx", "o.json", "o.json.partial"]


@pytest.mark.parametrize("side", ["source", "target"])
def test_cli_unterminated_polygon_fails_closed(tmp_path, side):
    a, b, out = tmp_path / "a.fbx", tmp_path / "b.fbx", tmp_path / "o.json"
    _fbx(a, [0, 1, -3, 0, 1] if side == "source" else [0, 1, -3])
    _fbx(b, [0, 1, -3, 0, 1] if side == "target" else [0, 1, -3])
    sentinel = Path(str(out) + ".partial"); sentinel.write_bytes(b"UNRELATED USER DATA")
    before = (a.read_bytes(), b.read_bytes())
    r = _cli(a, b, out)
    assert r.returncode == 2 and "incomplete polygon data" in r.stderr
    assert str(a if side == "source" else b) in r.stderr
    assert not out.exists() and sentinel.read_bytes() == b"UNRELATED USER DATA"
    assert (a.read_bytes(), b.read_bytes()) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.fbx", "b.fbx", "o.json.partial"]


def test_cli_out_of_range_vertex_index_fails_closed(tmp_path):
    a, b, out = tmp_path / "a.fbx", tmp_path / "b.fbx", tmp_path / "o.json"
    _fbx(a, [0, 1, -4]); _fbx(b, [0, 1, -3])
    r = _cli(a, b, out)
    assert r.returncode == 2 and "names vertex 3 of 3" in r.stderr and not out.exists()
