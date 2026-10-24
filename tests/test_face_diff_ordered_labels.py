"""Ordered face-to-part characterization for experiments/tow02-hand-finish-face-diff/face_diff.py.

new-case: synthetic ordered face-to-part witnesses for face_diff.py.
Synthetic only: one read_fbx node-tree double, a synthetic atlas, empty overlap
JSON (``{"pairs": []}``), and a fully triangulated target. No private assets, no DCC.

Acceptance table (literal oracle; labels and centroids are not produced by classify):

    face_id  part               status      centroid xyz                 rule
    0        fins               unchanged   1.0000  1.0000  0.0000       fin_* swatch, z=0 (below Z_TOP)
    1        ac_railing_glass   unchanged   11.5000 1.5000  0.0000       glass_solid swatch
    2        ac_basket          unchanged   21.0000 1.0000  0.0000       ac_coping swatch
    3        body               unchanged   31.5000 1.5000  0.0000       window strip, z=0 (below Z_TOP)
    4        top_glass          unchanged   41.0000 1.0000  100.0000     window strip, z=100 (above Z_TOP)
    5        body               unchanged   51.5000 1.5000  0.0000       no swatch/strip hit, z=0
    6        TOW02_top          unchanged   61.0000 1.0000  100.0000     no swatch/strip hit, z=100

One heterogeneous source holds triangles and quads. UVIndex is nonsequential and
shares a pair id. UV means sit well inside nonoverlapping atlas rectangles, or
clear of every padded rectangle on the two misses. Heights 0 and 100 stay far
from Z_TOP 64.7. Reordering source faces together with their UVIndex blocks
renumbers face ids and keeps each geometry->label pair. Reordering target
triangles keeps every source row and status. A process-local label swap keeps
the part histogram and breaks this order. A process-local UV cursor advance of
3 is caught by the mixed triangle/quad stream. face_diff.py on disk is not modified.
"""
import collections
import copy
import hashlib
import importlib.util
import json
import pathlib
import types

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "experiments" / "tow02-hand-finish-face-diff" / "face_diff.py"
SOURCE_SHA = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
OBJ = "SM_Vyatskaya_Vl_47_49_013_Main"
CANON = (0, 1, 2, 3, 4, 5, 6)
SOURCE_PERM = (1, 0, 2, 3, 4, 5, 6)  # quad block moves ahead of the opening triangle
HEADER = "face\tpart\tstatus\tmax_move_m\tx\ty\tz"

# Literal (face_id, part, status) oracle. Status is unchanged on every row.
ORDERED = (
    ("0", "fins", "unchanged"),
    ("1", "ac_railing_glass", "unchanged"),
    ("2", "ac_basket", "unchanged"),
    ("3", "body", "unchanged"),
    ("4", "top_glass", "unchanged"),
    ("5", "body", "unchanged"),
    ("6", "TOW02_top", "unchanged"),
)

EXPECTED_TSV = """\
face\tpart\tstatus\tmax_move_m\tx\ty\tz
0\tfins\tunchanged\t0.0000\t1.0000\t1.0000\t0.0000
1\tac_railing_glass\tunchanged\t0.0000\t11.5000\t1.5000\t0.0000
2\tac_basket\tunchanged\t0.0000\t21.0000\t1.0000\t0.0000
3\tbody\tunchanged\t0.0000\t31.5000\t1.5000\t0.0000
4\ttop_glass\tunchanged\t0.0000\t41.0000\t1.0000\t100.0000
5\tbody\tunchanged\t0.0000\t51.5000\t1.5000\t0.0000
6\tTOW02_top\tunchanged\t0.0000\t61.0000\t1.0000\t100.0000
"""

EXPECTED_TABLE = {
    "all:all": {"unchanged": 7, "unchanged_tri": 10},
    "band:00-05": {"unchanged": 5, "unchanged_tri": 8},
    "band:z>=64.7": {"unchanged": 2, "unchanged_tri": 2},
    "part:TOW02_top": {"unchanged": 1, "unchanged_tri": 1},
    "part:ac_basket": {"unchanged": 1, "unchanged_tri": 1},
    "part:ac_railing_glass": {"unchanged": 1, "unchanged_tri": 2},
    "part:body": {"unchanged": 2, "unchanged_tri": 4},
    "part:fins": {"unchanged": 1, "unchanged_tri": 1},
    "part:top_glass": {"unchanged": 1, "unchanged_tri": 1},
}

# Hand-placed (u, v) pairs. Array order is not face order; UVIndex selects them.
# Pixel comments are (100*u, 100*(1-v)), checked again by the witness test.
PAIRS = (
    (0.82, 0.22),  # 0  top miss (82, 78)
    (0.50, 0.84),  # 1  glass (50, 16)
    (0.46, 0.54),  # 2  window, shared (46, 46)
    (0.18, 0.78),  # 3  fins (18, 22)
    (0.20, 0.54),  # 4  coping (20, 46)
    (0.78, 0.84),  # 5  body miss (78, 16)
    (0.16, 0.84),  # 6  fins (16, 16)
    (0.49, 0.53),  # 7  window tri (49, 47)
    (0.46, 0.80),  # 8  glass (46, 20)
    (0.18, 0.48),  # 9  coping (18, 52)
    (0.82, 0.84),  # 10 body miss (82, 16)
    (0.20, 0.84),  # 11 fins (20, 16)
    (0.50, 0.54),  # 12 window (50, 46)
    (0.78, 0.22),  # 13 top miss (78, 78)
    (0.50, 0.80),  # 14 glass (50, 20)
    (0.16, 0.54),  # 15 coping (16, 46)
    (0.82, 0.80),  # 16 body miss (82, 20)
    (0.48, 0.50),  # 17 window tri (48, 50)
    (0.50, 0.50),  # 18 window (50, 50)
    (0.80, 0.16),  # 19 top miss (80, 84)
    (0.46, 0.84),  # 20 glass (46, 16)
    (0.78, 0.80),  # 21 body miss (78, 20)
    (0.46, 0.50),  # 22 window (46, 50)
)

# verts, UVIndex block, literal part, literal centroid. Parts are not computed.
FACES = (
    (((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 3.0, 0.0)), (6, 11, 3), "fins", (1.0, 1.0, 0.0)),
    (((10.0, 0.0, 0.0), (13.0, 0.0, 0.0), (13.0, 3.0, 0.0), (10.0, 3.0, 0.0)),
     (20, 1, 14, 8), "ac_railing_glass", (11.5, 1.5, 0.0)),
    (((20.0, 0.0, 0.0), (23.0, 0.0, 0.0), (20.0, 3.0, 0.0)), (15, 4, 9), "ac_basket", (21.0, 1.0, 0.0)),
    (((30.0, 0.0, 0.0), (33.0, 0.0, 0.0), (33.0, 3.0, 0.0), (30.0, 3.0, 0.0)),
     (2, 12, 18, 22), "body", (31.5, 1.5, 0.0)),
    (((40.0, 0.0, 100.0), (43.0, 0.0, 100.0), (40.0, 3.0, 100.0)), (2, 7, 17), "top_glass", (41.0, 1.0, 100.0)),
    (((50.0, 0.0, 0.0), (53.0, 0.0, 0.0), (53.0, 3.0, 0.0), (50.0, 3.0, 0.0)),
     (5, 10, 16, 21), "body", (51.5, 1.5, 0.0)),
    (((60.0, 0.0, 100.0), (63.0, 0.0, 100.0), (60.0, 3.0, 100.0)), (13, 0, 19), "TOW02_top", (61.0, 1.0, 100.0)),
)

# Intended atlas rectangle for each face mean, or None for a deliberate miss.
HITS = (
    (12, 12, 12, 12),
    (42, 12, 12, 12),
    (12, 42, 12, 12),
    (42, 42, 12, 12),
    (42, 42, 12, 12),
    None,
    None,
)

ALL_RECTS = (
    (12, 12, 12, 12),  # fin_south
    (42, 12, 12, 12),  # glass_solid
    (12, 42, 12, 12),  # ac_coping
    (42, 42, 12, 12),  # window strip
)

ATLAS = {
    "size": 100,
    "swatches": {
        "fin_south": {"rect": [12, 12, 12, 12]},
        "glass_solid": {"rect": [42, 12, 12, 12]},
        "ac_coping": {"rect": [12, 42, 12, 12]},
    },
    "strips": [{"pieces": [{"rect": [42, 42, 12, 12]}]}],
}


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_text(name, text):
    before = SCRIPT.read_bytes()
    mod = types.ModuleType(name)
    mod.__file__ = str(SCRIPT)
    exec(compile(text, str(SCRIPT), "exec"), mod.__dict__)
    assert SCRIPT.read_bytes() == before
    return mod


def tree(verts, polys, uv, uvi):
    pvi = []
    for poly in polys:
        ids = list(poly)
        ids[-1] = ~ids[-1]
        pvi.extend(ids)
    flat = []
    for x, y, z in verts:
        flat.extend((float(x), float(y), float(z)))
    geo = ("Geometry", [10, "Geometry::g\x00\x01Geometry", "Mesh"], [
        ("Vertices", [flat], []),
        ("PolygonVertexIndex", [pvi], []),
        ("LayerElementUV", [0], [("UV", [list(uv)], []), ("UVIndex", [list(uvi)], [])]),
    ])
    model = ("Model", [20, OBJ + "\x00\x01Model", "Mesh"], [])
    return [("Objects", [], [geo, model]), ("Connections", [], [("C", ["OO", 10, 20], [])])]


def _prop(node_tree, name):
    for kid in node_tree[0][2][0][2]:
        if kid[0] == name:
            return kid[1][0]
        for grand in kid[2]:
            if grand[0] == name:
                return grand[1][0]
    raise AssertionError(name)


def vertex_buffer():
    verts, polys = [], []
    for verts_f, _uv, _part, _cen in FACES:
        start = len(verts)
        verts.extend(verts_f)
        polys.append(tuple(range(start, start + len(verts_f))))
    return verts, polys


def flat_uv():
    out = []
    for u, v in PAIRS:
        out.extend((u, v))
    return out


def source_mesh(order):
    verts, polys = vertex_buffer()
    uvi = []
    for i in order:
        uvi.extend(FACES[i][1])
    return tree(verts, [polys[i] for i in order], flat_uv(), uvi)


def target_mesh(tri_order=None):
    verts, polys = vertex_buffer()
    tris = []
    for poly in polys:
        if len(poly) == 3:
            tris.append(poly)
        else:
            a, b, c, d = poly
            tris.append((a, b, c))
            tris.append((a, c, d))
    if tri_order is not None:
        tris = [tris[i] for i in tri_order]
    return tree(verts, tris, [], [])


def run_case(mod, monkeypatch, tmp_path, src, tgt):
    atlas_path = tmp_path / "atlas.json"
    ovl_path = tmp_path / "ovl.json"
    src_path = tmp_path / "src.fbx"
    tgt_path = tmp_path / "tgt.fbx"
    atlas_path.write_text(json.dumps(ATLAS), encoding="utf-8")
    ovl_path.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    src_path.write_bytes(b"unread-source-double")
    tgt_path.write_bytes(b"unread-target-double")
    files = (atlas_path, ovl_path, src_path, tgt_path)
    digest = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    src_snap, tgt_snap = copy.deepcopy(src), copy.deepcopy(tgt)
    monkeypatch.setattr(mod, "ATLAS", str(atlas_path))
    monkeypatch.setattr(mod, "OVL", str(ovl_path))
    monkeypatch.setattr(mod, "V5", str(src_path))
    monkeypatch.setattr(mod, "USER", str(tgt_path))
    trees = {str(src_path): src, str(tgt_path): tgt}
    monkeypatch.setattr(mod, "read_fbx", lambda path: trees[path])
    out = tmp_path / "out"
    out.mkdir()
    mod.main(str(out))
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert after == digest
    assert src == src_snap and tgt == tgt_snap
    assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() == SOURCE_SHA
    return out


def sequence(text):
    return tuple(tuple(line.split("\t")[:3]) for line in text.splitlines()[1:])


def tsv_for(order):
    """Reindex the literal TSV rows. Does not call classify."""
    body = EXPECTED_TSV.splitlines()[1:]
    lines = [HEADER]
    for new_id, old in enumerate(order):
        part, status, move, x, y, z = body[old].split("\t")[1:]
        lines.append("%d\t%s\t%s\t%s\t%s\t%s\t%s" % (new_id, part, status, move, x, y, z))
    return "\n".join(lines) + "\n"


def _pixel(uv_ids):
    n = len(uv_ids)
    u = sum(PAIRS[i][0] for i in uv_ids) / n
    v = sum(PAIRS[i][1] for i in uv_ids) / n
    return (u * 100.0, (1.0 - v) * 100.0)


def _padded(rect, pad):
    rx, ry, rw, rh = rect
    return (rx - pad, ry - pad, rx + rw + pad, ry + rh + pad)


def _inside_box(px, box):
    x, y = px
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _well_inside(px, rect):
    rx, ry, rw, rh = rect
    x, y = px
    return rx + 2 <= x <= rx + rw - 2 and ry + 2 <= y <= ry + rh - 2


def test_witness_is_mixed_nonsequential_and_literal():
    """Fixture lock: shape, shared UVIndex, and hand-checked means. No classify call."""
    assert [len(face[0]) for face in FACES] == [3, 4, 3, 4, 3, 4, 3]
    stream = [i for face in FACES for i in face[1]]
    assert stream != list(range(len(stream)))
    assert len(stream) != len(set(stream)) and stream.count(2) == 2
    assert len(stream) == sum(len(face[0]) for face in FACES)
    assert all(0 <= i < len(PAIRS) for i in stream)
    for face in FACES:
        assert len({PAIRS[i] for i in face[1]}) >= 2
        z = face[0][0][2]
        assert all(v[2] == z for v in face[0])
        assert abs(z - 64.7) >= 30
        n = len(face[0])
        avg = tuple(sum(v[a] for v in face[0]) / n for a in range(3))
        assert "%.4f\t%.4f\t%.4f" % avg == "%.4f\t%.4f\t%.4f" % face[3]
    parsed = sequence(EXPECTED_TSV)
    assert parsed == ORDERED
    body = EXPECTED_TSV.splitlines()[1:]
    assert len(body) == len(FACES) == len(ORDERED) == len(HITS)
    for face, line, ordered in zip(FACES, body, ORDERED):
        cols = line.split("\t")
        assert (cols[0], cols[1], cols[2]) == ordered
        assert cols[1] == face[2]
        assert cols[3] == "0.0000"
        assert "\t".join(cols[4:]) == "%.4f\t%.4f\t%.4f" % face[3]
    for i, rect in enumerate(ALL_RECTS):
        for other in ALL_RECTS[i + 1:]:
            assert not _boxes_overlap(_padded(rect, 1), _padded(other, 1))
    swatch_rects = [tuple(s["rect"]) for s in ATLAS["swatches"].values()]
    strip_rect = tuple(ATLAS["strips"][0]["pieces"][0]["rect"])
    assert tuple(swatch_rects + [strip_rect]) == ALL_RECTS
    assert any(name.startswith("fin_") for name in ATLAS["swatches"])
    assert "glass_solid" in ATLAS["swatches"] and "ac_coping" in ATLAS["swatches"]
    for face, hit in zip(FACES, HITS):
        px = _pixel(face[1])
        hits = [rect for rect in ALL_RECTS if _inside_box(px, _padded(rect, 1))]
        if hit is None:
            assert hits == []
        else:
            assert hits == [hit] and _well_inside(px, hit)


def _boxes_overlap(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _assert_artifacts(out, text):
    assert sorted(p.name for p in out.iterdir()) == [
        "added_user_tris.tsv", "faces_v005.tsv", "ovl_pairs_status.json", "summary.json",
    ]
    rows = text.splitlines()
    assert rows[0] == HEADER and len(rows) == 8
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["v005_faces"] == 7 and summary["user_tris"] == 10
    assert summary["table"] == EXPECTED_TABLE and summary["ovl_pairs_faces"] == {}
    assert json.loads((out / "ovl_pairs_status.json").read_text(encoding="utf-8")) == []
    added = (out / "added_user_tris.tsv").read_text(encoding="utf-8").splitlines()
    assert added == ["tri\tpart\tarea_m2\tx\ty\tz"]


def test_ordered_labels_match_literal_tsv(monkeypatch, tmp_path):
    mod = load("face_diff_ordered_labels")
    out = run_case(mod, monkeypatch, tmp_path, source_mesh(CANON), target_mesh())
    text = (out / "faces_v005.tsv").read_text(encoding="utf-8")
    assert sequence(text) == ORDERED
    assert text == EXPECTED_TSV
    _assert_artifacts(out, text)


def test_reordered_source_faces_follow_new_ids(monkeypatch, tmp_path):
    canon = source_mesh(CANON)
    moved = source_mesh(SOURCE_PERM)
    assert _prop(canon, "Vertices") == _prop(moved, "Vertices")
    assert _prop(canon, "PolygonVertexIndex") != _prop(moved, "PolygonVertexIndex")
    assert _prop(canon, "UVIndex") != _prop(moved, "UVIndex")
    mod = load("face_diff_ordered_source_perm")
    out = run_case(mod, monkeypatch, tmp_path, moved, target_mesh())
    text = (out / "faces_v005.tsv").read_text(encoding="utf-8")
    assert text == tsv_for(SOURCE_PERM)
    assert sequence(text) != ORDERED
    assert [row[0] for row in sequence(text)] == [str(i) for i in range(7)]

    def identity(tsv):
        return sorted(tuple(line.split("\t")[1:]) for line in tsv.splitlines()[1:])

    assert identity(text) == identity(EXPECTED_TSV)
    _assert_artifacts(out, text)


def test_reordered_target_triangles_keep_source_rows(monkeypatch, tmp_path):
    n = sum(1 if len(face[0]) == 3 else 2 for face in FACES)
    assert n == 10
    tri_order = tuple(reversed(range(n)))
    canon_tgt, moved_tgt = target_mesh(), target_mesh(tri_order)
    assert _prop(canon_tgt, "PolygonVertexIndex") != _prop(moved_tgt, "PolygonVertexIndex")
    assert all(len(poly) == 3 for poly in _triangles(moved_tgt))
    mod = load("face_diff_ordered_target_perm")
    out = run_case(mod, monkeypatch, tmp_path, source_mesh(CANON), moved_tgt)
    text = (out / "faces_v005.tsv").read_text(encoding="utf-8")
    assert text == EXPECTED_TSV and sequence(text) == ORDERED
    _assert_artifacts(out, text)


def _triangles(node_tree):
    """Closed polygons from a target double, used only to prove the reorder is triangulated."""
    pvi = _prop(node_tree, "PolygonVertexIndex")
    polys, cur = [], []
    for i in pvi:
        cur.append(~i if i < 0 else i)
        if i < 0:
            polys.append(cur)
            cur = []
    assert cur == []
    return polys


def test_label_swap_mutant_keeps_histogram_and_breaks_order(monkeypatch, tmp_path):
    text = SCRIPT.read_text(encoding="utf-8")
    marker = "    # pass 1: unchanged (every triangle of one diagonal found within 1 mm, same normal)"
    assert text.count(marker) == 1
    swap = "    faces[0]['part'], faces[2]['part'] = faces[2]['part'], faces[0]['part']\n"
    mutated = text.replace(marker, swap + marker, 1)
    assert mutated != text
    mod = load_text("face_diff_label_swap_mutant", mutated)
    out = run_case(mod, monkeypatch, tmp_path, source_mesh(CANON), target_mesh())
    got = (out / "faces_v005.tsv").read_text(encoding="utf-8")
    rows = sequence(got)
    assert rows != ORDERED
    assert (rows[0][1], rows[2][1]) == (ORDERED[2][1], ORDERED[0][1])
    assert collections.Counter(row[1] for row in rows) == collections.Counter(row[1] for row in ORDERED)
    assert [row[2] for row in rows] == ["unchanged"] * 7
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["table"] == EXPECTED_TABLE
    assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() == SOURCE_SHA


def test_cursor_offset_mutant_breaks_mixed_tri_quad_order(monkeypatch, tmp_path):
    text = SCRIPT.read_text(encoding="utf-8")
    needle = "k += len(p)"
    assert text.count(needle) == 1
    mutated = text.replace(needle, "k += 3", 1)
    assert mutated != text and "k += 3" in mutated
    mod = load_text("face_diff_cursor_mutant", mutated)
    out = run_case(mod, monkeypatch, tmp_path, source_mesh(CANON), target_mesh())
    rows = sequence((out / "faces_v005.tsv").read_text(encoding="utf-8"))
    # Advance 3 matches the opening triangle, then slips after the first quad.
    assert rows != ORDERED
    assert rows[0] == ORDERED[0]
    assert rows[2][1] != ORDERED[2][1]
    assert [row[2] for row in rows] == ["unchanged"] * 7
    assert len(rows) == 7
    assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() == SOURCE_SHA
