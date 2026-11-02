"""Finite-domain UV preflight regressions for the research script experiments/tow02-hand-finish-face-diff/face_diff.py.

Pattern: new-case: finite-domain UV preflight regressions for the face_diff research helper
Synthetic one-triangle fixtures plus a seeded probe. One real-input test skips when export-v005 is absent.
Malformed inventories must raise ValueError before any part label or out_dir artifact.
"""
import collections
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import re
import shutil

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "experiments" / "tow02-hand-finish-face-diff" / "face_diff.py"
OBJ = "SM_Vyatskaya_Vl_47_49_013_Main"
VERTS = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
WALL = {"size": 100, "swatches": {"wall": {"rect": [40, 40, 20, 20]}}, "strips": []}
TRI = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
REAL_LABELS = {
    "body": 20427,
    "fins": 8458,
    "TOW02_top": 3421,
    "ac_basket": 2283,
    "ac_railing_glass": 732,
    "top_glass": 86,
}


def load():
    spec = importlib.util.spec_from_file_location("face_diff_uv_numeric_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree(pvi, uv, uvi=(0, 1, 2), verts=VERTS):
    geo = ("Geometry", [10, "Geometry::g\x00\x01Geometry", "Mesh"], [
        ("Vertices", [list(verts)], []),
        ("PolygonVertexIndex", [list(pvi)], []),
        ("LayerElementUV", [0], [("UV", [list(uv)], []), ("UVIndex", [list(uvi)], [])]),
    ])
    model = ("Model", [20, OBJ + "\x00\x01Model", "Mesh"], [])
    return [("Objects", [], [geo, model]), ("Connections", [], [("C", ["OO", 10, 20], [])])]


def with_trees(mod, monkeypatch, src, tgt=None):
    trees = {"SRC": src, "TGT": tgt if tgt is not None else tree([0, 1, -3], uv=[0.0, 0.0, 1.0, 0.0, 0.0, 1.0], uvi=[0, 1, 2])}
    monkeypatch.setattr(mod, "read_fbx", lambda path: trees[path])
    monkeypatch.setattr(mod, "V5", "SRC")
    monkeypatch.setattr(mod, "USER", "TGT")


def run_main(mod, monkeypatch, tmp_path, src, tgt=None, name="out"):
    (tmp_path / "atlas.json").write_text(json.dumps(WALL), encoding="utf-8")
    (tmp_path / "ovl.json").write_text(json.dumps({"pairs": [{"a": 0, "b": 0, "group": "g"}]}), encoding="utf-8")
    monkeypatch.setattr(mod, "ATLAS", str(tmp_path / "atlas.json"))
    monkeypatch.setattr(mod, "OVL", str(tmp_path / "ovl.json"))
    with_trees(mod, monkeypatch, src, tgt)
    out = tmp_path / name
    out.mkdir()
    return out, lambda: mod.main(str(out))


def forbid_labels(mod, monkeypatch):
    def classify(*_args, **_kwargs):
        raise AssertionError("part label assigned")

    monkeypatch.setattr(mod, "classify", classify)


def arithmetic_quantities(uv, uvi, verts, atlas, n=3):
    """Independent sum, divide, product walk. Corner i reads UVIndex i, not the vertex id."""
    su = sum(uv[2 * uvi[i]] for i in range(n))
    u = su / n
    sv = sum(uv[2 * uvi[i] + 1] for i in range(n))
    v = sv / n
    z = sum(verts[i][2] for i in range(n)) / n
    return (
        ("su", su),
        ("sv", sv),
        ("uvc[0]", u),
        ("uvc[1]", v),
        ("z", z),
        ("uvc[0]*size", u * atlas["size"]),
        ("(1-uvc[1])*size", (1 - v) * atlas["size"]),
    )


def referenced_nonfinite(uv, uvi, n=3):
    for i in range(n):
        idx = uvi[i]
        if not math.isfinite(uv[2 * idx]) or not math.isfinite(uv[2 * idx + 1]):
            return True
    return False


def baseline_rejects(uv, uvi, verts, atlas, n=3):
    if referenced_nonfinite(uv, uvi, n):
        return True
    return any(not math.isfinite(value) for _name, value in arithmetic_quantities(uv, uvi, verts, atlas, n))


def first_bad_quantity(uv, uvi, verts, atlas, n=3):
    for name, value in arithmetic_quantities(uv, uvi, verts, atlas, n):
        if not math.isfinite(value):
            return name
    return None


def code_rejects(mod, uv, uvi, verts, atlas):
    poly = [0, 1, 2]
    try:
        mod.check_uv("SRC", [poly], uv, uvi)
        checker = getattr(mod, "check_face_numeric", None)
        if checker is None:
            return False
        checker("SRC", 0, poly, 0, verts, uv, uvi, atlas)
    except ValueError:
        return True
    return False


def part_of(out):
    rows = (out / "faces_v005.tsv").read_text(encoding="utf-8").splitlines()
    face_id, part = rows[1].split("\t")[:2]
    return int(face_id), part


@pytest.mark.parametrize("slot,value,comp", [
    pytest.param(0, float("nan"), "u", id="u-nan"),
    pytest.param(0, float("inf"), "u", id="u+inf"),
    pytest.param(0, float("-inf"), "u", id="u-inf"),
    pytest.param(1, float("nan"), "v", id="v-nan"),
    pytest.param(1, float("inf"), "v", id="v+inf"),
    pytest.param(1, float("-inf"), "v", id="v-inf"),
])
def test_referenced_nonfinite_component_rejects_before_artifact(monkeypatch, tmp_path, slot, value, comp):
    mod = load()
    uv = [0.5] * 6
    uv[slot] = value
    forbid_labels(mod, monkeypatch)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv))
    with pytest.raises(ValueError, match=r"SRC: UVIndex\[0\] %s is not finite" % comp):
        go()
    assert list(out.iterdir()) == []


@pytest.mark.parametrize("comp,quantity", [(0, "su"), (1, "sv")])
def test_sum_overflow_rejects_before_artifact(monkeypatch, tmp_path, comp, quantity):
    mod = load()
    uv = [0.5] * 6
    for i in range(3):
        uv[2 * i + comp] = 1e308
    forbid_labels(mod, monkeypatch)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv))
    with pytest.raises(ValueError, match=r"SRC: face 0 %s is not finite" % quantity):
        go()
    assert list(out.iterdir()) == []


@pytest.mark.parametrize("comp,quantity", [(0, r"uvc\[0\]\*size"), (1, r"\(1-uvc\[1\]\)\*size")])
def test_pixel_overflow_rejects_before_artifact(monkeypatch, tmp_path, comp, quantity):
    mod = load()
    uv = [0.5] * 6
    for i in range(3):
        uv[2 * i + comp] = 1e307
    forbid_labels(mod, monkeypatch)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv))
    with pytest.raises(ValueError, match=r"SRC: face 0 %s is not finite" % quantity):
        go()
    assert list(out.iterdir()) == []


@pytest.mark.parametrize("kind", ["in-swatch-0.5", "six-zeros", "six-2.0", "unreferenced-nan"])
def test_finite_controls_keep_unchanged_walk_label(monkeypatch, tmp_path, kind):
    mod = load()
    if kind == "in-swatch-0.5":
        uv = [0.5] * 6
    elif kind == "six-zeros":
        uv = [0.0] * 6
    elif kind == "six-2.0":
        uv = [2.0] * 6
    else:
        uv = [0.5] * 6 + [float("nan"), float("nan")]
    uvi = [0, 1, 2]
    mod.check_uv("SRC", [[0, 1, 2]], uv, uvi)
    uvc = (sum(uv[2 * uvi[i]] for i in range(3)) / 3, sum(uv[2 * uvi[i] + 1] for i in range(3)) / 3)
    expected = mod.classify(uvc, 0.0, WALL)
    assert expected == "body"
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv, uvi=uvi))
    go()
    assert part_of(out) == (0, expected)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["table"]["part:body"]["unchanged"] == 1


def test_max_finite_float_matches_baseline_and_sum_overflow_is_not_silent(monkeypatch, tmp_path):
    mod = load()
    ceiling = 1.7976931348623157e308
    assert math.isfinite(ceiling)
    uv = [ceiling, 0.0, 0.0, 0.0, 0.0, 0.0]
    uvi = [0, 1, 2]
    mod.check_uv("SRC", [[0, 1, 2]], uv, uvi)
    bad = first_bad_quantity(uv, uvi, TRI, WALL)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv))
    if bad is None:
        go()
        assert part_of(out) == (0, mod.classify((ceiling / 3, 0.0), 0.0, WALL))
    else:
        forbid_labels(mod, monkeypatch)
        with pytest.raises(ValueError, match=r"SRC: face 0 %s is not finite" % re.escape(bad)):
            go()
        assert list(out.iterdir()) == []

    uv3 = [ceiling, 0.0, ceiling, 0.0, ceiling, 0.0]
    assert first_bad_quantity(uv3, uvi, TRI, WALL) == "su"
    forbid_labels(mod, monkeypatch)
    out3, go3 = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=uv3), name="out-sum")
    with pytest.raises(ValueError, match=r"SRC: face 0 su is not finite"):
        go3()
    assert list(out3.iterdir()) == []


def test_empty_uv_with_indices_keeps_structural_error(monkeypatch, tmp_path):
    mod = load()
    forbid_labels(mod, monkeypatch)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3], uv=[], uvi=[0, 1, 2]))
    with pytest.raises(ValueError, match=r"SRC: UVIndex\[0\] = 0 outside UV pairs 0\.\.-1"):
        go()
    assert list(out.iterdir()) == []


def test_later_face_is_rejected_before_any_label(monkeypatch, tmp_path):
    mod = load()
    uv = [0.5] * 6 + [1e308, 0.5, 1e308, 0.5, 1e308, 0.5]
    uvi = [0, 1, 2, 3, 4, 5]
    forbid_labels(mod, monkeypatch)
    out, go = run_main(mod, monkeypatch, tmp_path, tree([0, 1, -3, 0, 1, -3], uv=uv, uvi=uvi))
    with pytest.raises(ValueError, match=r"SRC: face 1 su is not finite"):
        go()
    assert list(out.iterdir()) == []


def test_seeded_probe_matches_baseline_arithmetic():
    mod = load()
    rng = random.Random(626)
    specials = (float("nan"), float("inf"), float("-inf"), 1e308, -1e308, 1e307, -1e307, 1e309)
    agreements = 0
    for case_i in range(200):
        uv = [rng.uniform(-2.0, 2.0) for _ in range(6)]
        if rng.random() < 0.25:
            uv.extend((float("nan"), float("nan")))
        uvi = [0, 1, 2]
        z = 0.0
        roll = rng.randrange(10)
        if roll < 6:
            uv[roll] = specials[rng.randrange(len(specials))]
        elif roll < 8:
            val = specials[rng.randrange(len(specials))]
            for i in range(3):
                uv[2 * i + (roll - 6)] = val
        elif roll == 8:
            z = specials[rng.randrange(len(specials))]
        verts = ((0.0, 0.0, z), (1.0, 0.0, z), (0.0, 1.0, z))
        expect = baseline_rejects(uv, uvi, verts, WALL)
        assert code_rejects(mod, uv, uvi, verts, WALL) == expect, case_i
        agreements += 1
    assert agreements == 200


def test_real_export_v005_labels_unchanged(tmp_path):
    mod = load()
    v5 = pathlib.Path(mod.V5)
    atlas_path = pathlib.Path(mod.ATLAS)
    if not v5.is_file() or not atlas_path.is_file():
        pytest.skip("face_diff.V5 / face_diff.ATLAS missing")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (v5, atlas_path)}
    v5_copy = tmp_path / v5.name
    atlas_copy = tmp_path / atlas_path.name
    shutil.copyfile(v5, v5_copy)
    shutil.copyfile(atlas_path, atlas_copy)
    verts, polys, uv, uvi = mod.mesh(str(v5_copy), OBJ)
    mod.check_uv(str(v5_copy), polys, uv, uvi)
    atlas = json.loads(atlas_copy.read_text(encoding="utf-8"))
    checker = getattr(mod, "check_face_numeric", None)
    assert checker is not None
    counts = collections.Counter()
    k = 0
    for fi, poly in enumerate(polys):
        uvc, cen = checker(str(v5_copy), fi, poly, k, verts, uv, uvi, atlas)
        k += len(poly)
        counts[mod.classify(uvc, cen[2], atlas)] += 1
    assert len(polys) == 35407
    assert k == 141492 == len(uvi)
    assert sum(len(poly) for poly in polys) == 141492
    assert dict(counts) == REAL_LABELS
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (v5, atlas_path)}
    assert after == before
