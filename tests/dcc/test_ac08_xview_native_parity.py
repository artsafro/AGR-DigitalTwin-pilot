"""Opt-in AC08 native xView parity harness (#766).

Always-run cases use SYNTHETIC native-dump dicts. Real FBX bytes stay outside
the repo: the fixture test skips unless AC08_XVIEW_FIXTURE_ROOT is set, and the
native test also skips unless AC08_XVIEW_NATIVE_DUMP is set or pytest is
selected with -m native_max and a live ping succeeds.
"""
import copy
import importlib.util
import json
import os
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "experiments" / "ac08-xview-native-parity" / "run.py"
README = ROOT / "experiments" / "ac08-xview-native-parity" / "README.md"

S00 = "2142e12af1f2f97f51a09dd58e98496eba6d74ff0bd4913706f3128654cccba1"
S12 = "8d119ed3e077f1f4a7a1d394fa955a664fa4474fc7da6fab9417eca3b06b0195"
S14 = "b1177ac2079f388dad1283a87c201b39353db7a4263d0f294e3f587fc07b24a9"
S00_JSON = "fbf6eb6c94d506a3d627f3c152755136fdb720c09c88a6858de35f451ecb589f"
S12_JSON = "363c2465fa5c12704242f5f264155c7a2409a7520fb168eae3f6bee9be9f1882"
S14_JSON = "a1f5de678cb2ade9fd4a78a6568d953a21ac6dd0c8f3156447d3408463cc2b60"
DEFAULT_MARKEXPR = "not blender and not dcc and not acad and not perf and not max and not panel_texture"


@pytest.fixture
def lib():
    if not MODULE.is_file():
        raise FileNotFoundError(MODULE)
    spec = importlib.util.spec_from_file_location("ac08_xview_native_parity", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _node(name, vertices, faces, overlap_vertices=None, overlap_faces=None, **overrides):
    node = {
        "name": name,
        "class": "Editable_Poly",
        "verts_type": "#vertices",
        "faces_type": "#faces",
        "vertices": vertices,
        "faces": faces,
        "num_verts": len(vertices),
        "num_faces": len(faces),
        "overlap_vertices": [] if overlap_vertices is None else list(overlap_vertices),
        "overlap_faces": [] if overlap_faces is None else list(overlap_faces),
    }
    node.update(overrides)
    if "verts_count" not in overrides:
        node["verts_count"] = len(node["overlap_vertices"])
    if "faces_count" not in overrides:
        node["faces_count"] = len(node["overlap_faces"])
    if "num_verts" not in overrides:
        node["num_verts"] = len(node["vertices"])
    if "num_faces" not in overrides:
        node["num_faces"] = len(node["faces"])
    return node


def _quad(name="quad", x0=0.0, **overrides):
    vertices = [[x0, 0.0, 0.0], [x0 + 1.0, 0.0, 0.0], [x0 + 1.0, 1.0, 0.0], [x0, 1.0, 0.0]]
    faces = overrides.pop("faces", [[1, 2, 3, 4]])
    return _node(name, vertices, faces, **overrides)


def _dump(nodes, state="synthetic-quad", reps=(1, 2), synthetic=True):
    imports = []
    for rep in reps:
        imports.append({
            "state": state,
            "rep": rep,
            "m_per_unit": 1,
            "tol_v_units": 0.002,
            "tol_f_units": 0.005,
            "nodes": copy.deepcopy(nodes),
        })
    return {"synthetic": synthetic, "imports": imports}


def _area_cross(name="cross", **overrides):
    """Edge-crossing quads: area overlap, contact set empty (SYNTHETIC)."""
    vertices = [
        [0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0],
        [1, -1, 0.001], [2, -1, 0.001], [2, 2, 0.001], [1, 2, 0.001],
    ]
    return _node(name, vertices, [[1, 2, 3, 4], [5, 6, 7, 8]], **overrides)


def _touch(name="touch", **overrides):
    """Two quads welded along an edge in index space only: contact pair (SYNTHETIC)."""
    vertices = [
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [1, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0],
    ]
    return _node(name, vertices, [[1, 2, 3, 4], [5, 6, 7, 8]], **overrides)


def _raises(lib, dump):
    with pytest.raises(lib.HarnessError) as caught:
        lib.evaluate(dump)
    assert caught.value.status == "fail"
    assert caught.value.status not in ("pass", "not_run")
    return caught.value


def test_readme_and_marker_registered(pytestconfig):
    assert README.is_file()
    markers = [str(item) for item in pytestconfig.getini("markers")]
    assert any(item.split(":", 1)[0].strip() == "native_max" for item in markers)


def test_module_docstring_and_pinned_table(lib):
    assert "new-case: opt-in native real-fixture parity harness" in (lib.__doc__ or "")
    table = lib.pinned_table()
    assert len(table["hashes"]) == 6
    assert len(table["meshes"]) == 7
    assert table["hashes"]["fbx/S00_source.fbx"] == S00
    assert table["hashes"]["fbx/S12_join_parts_AC08_body_AC08_plate.fbx"] == S12
    assert table["hashes"]["fbx/S14_join_parts_AC08_body_AC08_knob.fbx"] == S14
    assert table["hashes"]["readback/S00_source.json"] == S00_JSON
    assert table["hashes"]["readback/S12_join_parts_AC08_body_AC08_plate.json"] == S12_JSON
    assert table["hashes"]["readback/S14_join_parts_AC08_body_AC08_knob.json"] == S14_JSON
    counts = {(row["state"], row["mesh"]): row["polygons"] for row in table["meshes"]}
    assert counts == {
        ("S00_source", "AC08_body"): 143,
        ("S00_source", "AC08_knob"): 24,
        ("S00_source", "AC08_plate"): 13,
        ("S12_join_parts_AC08_body_AC08_plate", "AC08_body_J_AC08_plate"): 156,
        ("S12_join_parts_AC08_body_AC08_plate", "AC08_knob"): 24,
        ("S14_join_parts_AC08_body_AC08_knob", "AC08_body_J_AC08_knob"): 167,
        ("S14_join_parts_AC08_body_AC08_knob", "AC08_plate"): 13,
    }
    assert lib.DELIVERY_PASSED is False


def test_equal_synthetic_sets_pass(lib):
    report = lib.evaluate(_dump([_quad()]))
    assert report["status"] == "pass"
    assert report["delivery_passed"] is False
    assert report["synthetic"] is True
    assert report["rows"] and all(row["equal"] for row in report["rows"])


def test_vertex_symmetric_difference_names_the_mesh(lib):
    err = _raises(lib, _dump([_quad(overlap_vertices=[1])]))
    assert err.mesh == "quad"


def test_face_symmetric_difference_names_the_mesh(lib):
    err = _raises(lib, _dump([_quad(overlap_faces=[1])]))
    assert err.mesh == "quad"


def test_wrong_checker_type_names_the_mesh(lib):
    err = _raises(lib, _dump([_quad(verts_type="#failed")]))
    assert err.mesh == "quad"
    err = _raises(lib, _dump([_quad(faces_type="faces")]))
    assert err.mesh == "quad"


def test_out_of_range_id_names_the_mesh(lib):
    err = _raises(lib, _dump([_quad(overlap_vertices=[5])]))
    assert err.mesh == "quad"
    err = _raises(lib, _dump([_quad(faces=[[0, 1, 2, 3]])]))
    assert err.mesh == "quad"


def test_count_inconsistent_with_list_names_the_mesh(lib):
    err = _raises(lib, _dump([_quad(verts_count=3)]))
    assert err.mesh == "quad"
    err = _raises(lib, _dump([_quad(num_faces=9)]))
    assert err.mesh == "quad"


def test_missing_mesh_names_the_mesh(lib):
    knob = _quad("AC08_knob")
    knob["faces"] = [[1, 2, 3, 4]] * 24
    knob["num_faces"] = 24
    plate = _quad("AC08_plate")
    plate["faces"] = [[1, 2, 3, 4]] * 13
    plate["num_faces"] = 13
    err = _raises(lib, _dump([knob, plate], state="S00_source"))
    assert err.mesh == "AC08_body"


def test_wrong_polygon_count_names_the_mesh(lib):
    body = _quad("AC08_body")
    knob = _quad("AC08_knob")
    knob["faces"] = [[1, 2, 3, 4]] * 24
    knob["num_faces"] = 24
    plate = _quad("AC08_plate")
    plate["faces"] = [[1, 2, 3, 4]] * 13
    plate["num_faces"] = 13
    err = _raises(lib, _dump([body, knob, plate], state="S00_source"))
    assert err.mesh == "AC08_body"


def test_hash_mismatch_fails(lib, tmp_path):
    lib.require_pinned_hash("fbx/S00_source.fbx", S00)
    with pytest.raises(lib.HarnessError, match="hash mismatch"):
        lib.require_pinned_hash("fbx/S00_source.fbx", "0" * 64)
    root = tmp_path / "root"
    for rel in lib.pinned_table()["hashes"]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic-bytes")
    with pytest.raises(lib.HarnessError, match="hash mismatch"):
        lib.verify_hashes(root)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_coordinate_names_the_mesh(lib, bad):
    node = _quad()
    node["vertices"][0][2] = bad
    err = _raises(lib, _dump([node]))
    assert err.mesh == "quad"


def test_incomplete_dump_fails(lib):
    broken = _dump([_quad()])
    del broken["imports"][0]["nodes"][0]["vertices"]
    err = _raises(lib, broken)
    assert err.mesh == "quad"
    empty_nodes = _dump([])
    err = _raises(lib, empty_nodes)
    assert err.status == "fail"


def test_empty_input_fails_closed(lib, tmp_path):
    err = _raises(lib, {})
    assert err.status == "fail"
    assert err.status not in ("pass", "not_run")
    src = tmp_path / "native.json"
    src.write_text("{}", encoding="utf-8")
    out = tmp_path / "out.json"
    code = lib.write_report([src], out, {})
    assert code != 0
    assert not out.exists()


def test_repeat_mismatch_names_the_mesh(lib):
    dump = _dump([_quad()])
    dump["imports"][1]["nodes"][0]["overlap_vertices"] = [1]
    dump["imports"][1]["nodes"][0]["verts_count"] = 1
    err = _raises(lib, dump)
    assert err.mesh == "quad"


def test_compare_uses_contact_xview_faces_only(lib):
    """SYNTHETIC. Area-only overlap is not an xView face hit; contact ids are."""
    report = lib.evaluate(_dump([_area_cross()]))
    assert report["status"] == "pass"
    assert all(row["ours_contact_faces"] == 0 for row in report["rows"])
    assert any(row["ours_all_faces"] > row["ours_contact_faces"] for row in report["rows"])
    err = _raises(lib, _dump([_area_cross(overlap_faces=[1, 2])]))
    assert err.mesh == "cross"


def test_output_path_equal_to_input_writes_nothing(lib, tmp_path):
    dump = _dump([_quad()])
    src = tmp_path / "native.json"
    src.write_text(json.dumps({"keep": True}), encoding="utf-8")
    before = src.read_bytes()
    code = lib.write_report([src], src, dump)
    assert code != 0
    assert src.read_bytes() == before
    assert list(tmp_path.iterdir()) == [src]


def test_failed_compare_writes_nothing(lib, tmp_path):
    src = tmp_path / "native.json"
    src.write_text("{}", encoding="utf-8")
    out = tmp_path / "report.json"
    code = lib.write_report([src], out, _dump([_quad(overlap_faces=[1])]))
    assert code != 0
    assert not out.exists()


def test_probe_zero_symmetric_difference_random_id_sets(lib):
    """SYNTHETIC brute force: a row passes only when both id sets match."""
    import numpy as np

    node = _touch()
    parity = lib.parity_module()
    mesh = parity.PolyMesh(
        np.asarray(node["vertices"], dtype=float),
        tuple(tuple(i - 1 for i in face) for face in node["faces"]),
    )
    produced = parity.part_report(node["name"], mesh, parity.XviewTolerance())
    node["overlap_vertices"] = list(produced.vertices)
    node["overlap_faces"] = list(produced.xview_faces)
    node["verts_count"] = len(node["overlap_vertices"])
    node["faces_count"] = len(node["overlap_faces"])
    report = lib.evaluate(_dump([node]))
    assert report["status"] == "pass"
    ours_v = set(report["rows"][0]["ours_vertex_ids"])
    ours_f = set(report["rows"][0]["ours_contact_ids"])
    assert ours_v and ours_f
    rng = random.Random(766)
    trials = 64
    matched = 0
    for index in range(trials):
        if index == 0:
            guess_v, guess_f = set(ours_v), set(ours_f)
        else:
            guess_v = {i for i in range(1, 9) if rng.random() < 0.5}
            guess_f = {i for i in range(1, 3) if rng.random() < 0.5}
        probe = _touch(overlap_vertices=sorted(guess_v), overlap_faces=sorted(guess_f))
        if guess_v == ours_v and guess_f == ours_f:
            got = lib.evaluate(_dump([probe]))
            assert got["status"] == "pass"
            matched += 1
        else:
            err = _raises(lib, _dump([probe]))
            assert err.mesh == "touch"
            matched += 1
    assert matched == trials


def test_probe_id_conversion_exactly_once(lib, monkeypatch):
    """SYNTHETIC. Faces reach compare still 1-based; the last vertex id is nv."""
    rng = random.Random(7661)
    seen = []

    def spy(dump, real=lib._compare):
        seen.append(copy.deepcopy(dump["nodes"][0]["faces"]))
        return real(dump)

    monkeypatch.setattr(lib, "_compare", spy)
    trials = 32
    passed = 0
    for _ in range(trials):
        seen.clear()
        nv = rng.randint(3, 7)
        vertices = [[rng.random(), rng.random(), rng.random() * 0.01] for _ in range(nv)]
        # Index 1 is always present, so a second decrement produces a 0 id.
        corners = [1, rng.choice(range(2, nv)), nv]
        rng.shuffle(corners)
        node = _node("rand", vertices, [corners])
        parity = lib.parity_module()
        mesh = parity.PolyMesh(
            __import__("numpy").asarray(vertices, dtype=float),
            (tuple(i - 1 for i in corners),),
        )
        produced = parity.part_report("rand", mesh, parity.XviewTolerance())
        node["overlap_vertices"] = list(produced.vertices)
        node["overlap_faces"] = list(produced.xview_faces)
        node["verts_count"] = len(node["overlap_vertices"])
        node["faces_count"] = len(node["overlap_faces"])
        report = lib.evaluate(_dump([node]))
        assert report["status"] == "pass"
        assert seen[0] == [corners]
        assert max(seen[0][0]) == nv
        shifted = _node("rand", vertices, [[i - 1 for i in corners]])
        err = _raises(lib, _dump([shifted]))
        assert err.mesh == "rand"
        passed += 1
    assert passed == trials


def test_native_ms_holds_and_restores(lib, tmp_path, monkeypatch):
    monkeypatch.delenv("AC08_XVIEW_FIXTURE_ROOT", raising=False)
    text = lib.render_native_ms(tmp_path / "work")
    assert text.startswith("holdMaxFile()\n")
    assert "fetchMaxFile quiet:true" in text
    assert "native" in text
    with pytest.raises(lib.HarnessError):
        lib.prepare(tmp_path / "fresh", source=None)


def test_native_marker_skip_reason(lib, tmp_path):
    assert lib.native_max_selected(DEFAULT_MARKEXPR) is False
    assert lib.native_max_selected("native_max") is True
    assert lib.native_max_selected("not native_max") is False
    reason = lib.native_skip_reason(DEFAULT_MARKEXPR, {})
    assert reason and "native marker missing" in reason
    calls = []

    def ping():
        calls.append("ping")
        return False, "max down"

    failed = lib.native_skip_reason("native_max", {}, ping=ping)
    assert calls == ["ping"]
    assert failed and "ping" in failed
    dump = tmp_path / "native.json"
    dump.write_text("{}", encoding="utf-8")
    assert lib.native_skip_reason(DEFAULT_MARKEXPR, {"AC08_XVIEW_NATIVE_DUMP": str(dump)}, ping=ping) is None
    assert calls == ["ping"]
    absent = lib.fixture_skip_reason({})
    assert absent and "AC08_XVIEW_FIXTURE_ROOT" in absent


def test_real_fixture_hashes_and_baseline(lib, capsys):
    reason = lib.fixture_skip_reason()
    if reason:
        pytest.skip(reason)
    root = lib.fixture_root()
    hashes = lib.verify_hashes(root)
    baseline = lib.python_baseline(root)
    print("REAL_HASHES", len(hashes))
    for row in baseline:
        print("REAL_BASELINE", row["state"], row["node"], row["polygons"], row["vertex_ids"], row["xview_faces"])
    assert len(hashes) == 6
    assert len(baseline) == 7
    assert all(row["synthetic"] is False and row["delivery_passed"] is False for row in baseline)
    captured = capsys.readouterr()
    assert "REAL_BASELINE" in captured.out


@pytest.mark.native_max
def test_real_native_parity(lib, request):
    reason = lib.fixture_skip_reason()
    if reason:
        pytest.skip(reason)
    native = lib.native_skip_reason(request.config.getoption("markexpr") or "", os.environ)
    if native:
        pytest.skip(native)
    path = os.environ.get("AC08_XVIEW_NATIVE_DUMP")
    if not path:
        err = _raises(lib, {})
        assert err.status == "fail"
        return
    dump = json.loads(Path(path).read_text(encoding="utf-8"))
    if dump.get("synthetic") is True:
        pytest.fail("synthetic dump cannot confirm native parity")
    report = lib.confirm_native(dump)
    assert report["status"] == "pass"
    assert report["delivery_passed"] is False
    assert report["synthetic"] is False
    assert report["mesh_import_rows"] == 14
    assert all(row["equal"] for row in report["rows"])
