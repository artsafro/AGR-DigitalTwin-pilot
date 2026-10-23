"""Stream-completeness regressions for the research script experiments/tow02-hand-finish-face-diff/face_diff.py.

Pattern: new-case: research FBX reader fails closed on unfinished polygons and partial source UV inventories.
Synthetic only: tiny node-tree doubles for read_fbx and a tiny synthetic atlas; no real TOW02 assets, no DCC.
Acceptance (report docs/research/fbx-polygon-stream-consumption-boundary.md @ 0f26ca5, tasks #1-2):
  [0,1,-3] + UVIndex [0,1,2] + UV [0,0,1,0,0,1] -> 3 vertices, [[0,1,2]], 3 corners, centroid (1/3, 1/3)
  [0,1,-3,0,1] -> ValueError naming 2 trailing entries [0, 1]; [0,1] -> same error, never zero faces
  UVIndex length 2 or 5 -> ValueError "2 ... 3" / "5 ... 3"; UVIndex [0,1,3] / [0,1,-1] -> index-range error
  odd UV length -> incomplete-pair error; every malformed main() case writes nothing into a fresh out dir.
"""
import importlib.util
import json
import math
import pathlib
import re

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "experiments" / "tow02-hand-finish-face-diff" / "face_diff.py"
OBJ = "SM_Vyatskaya_Vl_47_49_013_Main"
VERTS = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
UV = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0]


def load():
    spec = importlib.util.spec_from_file_location("face_diff_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree(pvi, uv=UV, uvi=(0, 1, 2), verts=VERTS):
    geo = ("Geometry", [10, "Geometry::g\x00\x01Geometry", "Mesh"], [
        ("Vertices", [list(verts)], []),
        ("PolygonVertexIndex", [list(pvi)], []),
        ("LayerElementUV", [0], [("UV", [list(uv)], []), ("UVIndex", [list(uvi)], [])]),
    ])
    model = ("Model", [20, OBJ + "\x00\x01Model", "Mesh"], [])
    return [("Objects", [], [geo, model]), ("Connections", [], [("C", ["OO", 10, 20], [])])]


def with_trees(mod, monkeypatch, src, tgt=None):
    trees = {"SRC": src, "TGT": tgt if tgt is not None else tree([0, 1, -3], uv=[], uvi=[])}
    monkeypatch.setattr(mod, "read_fbx", lambda path: trees[path])
    monkeypatch.setattr(mod, "V5", "SRC")
    monkeypatch.setattr(mod, "USER", "TGT")


def run_main(mod, monkeypatch, tmp_path, src, tgt=None):
    # UV centroid (1/3, 1/3) -> atlas px (33.3, 66.7) lies inside fin_a -> "fins"; z = 0 -> not top.
    atlas = {"size": 100, "swatches": {"fin_a": {"rect": [20, 50, 30, 30]}}, "strips": []}
    (tmp_path / "atlas.json").write_text(json.dumps(atlas), encoding="utf-8")
    (tmp_path / "ovl.json").write_text(json.dumps({"pairs": [{"a": 0, "b": 0, "group": "g"}]}), encoding="utf-8")
    monkeypatch.setattr(mod, "ATLAS", str(tmp_path / "atlas.json"))
    monkeypatch.setattr(mod, "OVL", str(tmp_path / "ovl.json"))
    with_trees(mod, monkeypatch, src, tgt)
    out = tmp_path / "out"
    out.mkdir()
    return out, lambda: mod.main(str(out))


def test_mesh_clean_triangle_unchanged(monkeypatch):
    mod = load()
    with_trees(mod, monkeypatch, tree([0, 1, -3]))
    v, p, uv, uvi = mod.mesh("SRC", OBJ)
    assert len(v) == 3 and p == [[0, 1, 2]] and len(uv) == 6 and len(uvi) == 3
    assert sum(len(f) for f in p) == 3


@pytest.mark.parametrize("pvi, tail, where", [([0, 1, -3, 0, 1], "[0, 1]", "3..4"), ([0, 1], "[0, 1]", "0..1")])
def test_mesh_rejects_unfinished_polygon(monkeypatch, pvi, tail, where):
    mod = load()
    with_trees(mod, monkeypatch, tree(pvi))
    with pytest.raises(ValueError, match=r"2 trailing PolygonVertexIndex entries %s at positions %s"
                       % (re.escape(tail), where)):
        mod.mesh("SRC", OBJ)


def test_main_clean_control_end_to_end(monkeypatch, tmp_path):
    mod = load()
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3]))
    go()
    s = json.loads((out / "summary.json").read_text())
    assert s["v005_faces"] == 1 and s["user_tris"] == 1
    assert s["table"]["all:all"] == {"unchanged": 1, "unchanged_tri": 1}
    assert s["table"]["part:fins"] == {"unchanged": 1, "unchanged_tri": 1}  # UV-derived label
    assert s["ovl_pairs_faces"] == {"g:unchanged": 2}
    rows = (out / "faces_v005.tsv").read_text().splitlines()
    assert rows[0] == "face\tpart\tstatus\tmax_move_m\tx\ty\tz"
    f = rows[1].split("\t")
    assert f[:4] == ["0", "fins", "unchanged", "0.0000"]
    assert math.isclose(float(f[4]), 1 / 3, abs_tol=1e-4) and math.isclose(float(f[5]), 1 / 3, abs_tol=1e-4)
    assert (out / "added_user_tris.tsv").read_text().splitlines() == ["tri\tpart\tarea_m2\tx\ty\tz"]
    assert json.loads((out / "ovl_pairs_status.json").read_text())[0]["part"] == "fins"


def test_main_uv_centroid_is_one_third(monkeypatch, tmp_path):
    mod = load()
    seen = []
    real = mod.classify
    monkeypatch.setattr(mod, "classify", lambda fuv, z, atlas: seen.append(fuv) or real(fuv, z, atlas))
    _, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3]))
    go()
    assert len(seen) == 1 and all(math.isclose(c, 1 / 3) for c in seen[0])


@pytest.mark.parametrize("kw, msg", [
    (dict(pvi=[0, 1, -3, 0, 1]), r"2 trailing PolygonVertexIndex entries \[0, 1\]"),
    (dict(pvi=[0, 1]), r"2 trailing PolygonVertexIndex entries \[0, 1\]"),
    (dict(uvi=[0, 1]), r"UVIndex has 2 entries, expected 3 "),
    (dict(uvi=[0, 1, 2, 0, 1]), r"UVIndex has 5 entries, expected 3 "),
    (dict(uvi=[0, 1, 3]), r"UVIndex\[2\] = 3 outside UV pairs 0\.\.2"),
    (dict(uvi=[0, 1, -1]), r"UVIndex\[2\] = -1 outside UV pairs 0\.\.2"),
    (dict(uv=UV + [0.5]), r"UV has 7 values: incomplete \(u, v\) pair"),
])
def test_main_rejects_partial_source_inventory_and_writes_nothing(monkeypatch, tmp_path, kw, msg):
    mod = load()
    pvi = kw.pop("pvi", [0, 1, -3])
    out, go = run_main(mod, monkeypatch, tmp_path, tree(pvi, **kw))
    with pytest.raises(ValueError, match=msg):
        go()
    assert list(out.iterdir()) == []
