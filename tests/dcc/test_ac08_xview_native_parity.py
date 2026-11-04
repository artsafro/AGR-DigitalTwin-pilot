"""new-case: opt-in AC08 native xView parity harness (#766).

Always-run cases use SYNTHETIC native-dump dicts. Real FBX bytes stay outside
the repo: the fixture test skips unless AC08_XVIEW_FIXTURE_ROOT is set, and the
native test also skips unless AC08_XVIEW_NATIVE_DUMP is set. Selecting
``-m native_max`` may ping the bridge, but a live marker with no dump skips:
nothing was measured, and 3ds Max is not launched.
"""
import copy
import importlib.util
import json
import os
import random
import warnings
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
        "geometry_unchanged": True,
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
            "import_ok": True,
            "m_per_unit": 1,
            "tol_v_units": 0.002,
            "tol_f_units": 0.005,
            "failures": [],
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
        pytest.skip(
            "AC08_XVIEW_NATIVE_DUMP unset: live Max is not launched and no native dump was measured"
        )
    dump = json.loads(Path(path).read_text(encoding="utf-8"))
    if dump.get("synthetic") is True:
        pytest.fail("synthetic dump cannot confirm native parity")
    report = lib.confirm_native(dump)
    assert report["status"] == "pass"
    assert report["delivery_passed"] is False
    assert report["synthetic"] is False
    assert report["mesh_import_rows"] == 14
    assert all(row["equal"] for row in report["rows"])


def _separated_node(name, count):
    """SYNTHETIC. ``count`` quads, 10 m apart, so neither 2 mm nor 5 mm fires."""
    vertices = []
    faces = []
    for index in range(count):
        x = index * 10.0
        base = len(vertices)
        vertices.extend([
            [x, 0.0, 0.0], [x + 1.0, 0.0, 0.0], [x + 1.0, 1.0, 0.0], [x, 1.0, 0.0],
        ])
        faces.append([base + 1, base + 2, base + 3, base + 4])
    node = _node(name, vertices, faces)
    node["geometry_unchanged"] = True
    return node


def _pinned_dump(lib, synthetic=True):
    """Fourteen-row stand-in: pinned state/rep/node inventory, empty xView sets."""
    imports = []
    for state, parts in lib.STATES.items():
        nodes = [_separated_node(name, count) for name, count in parts.items()]
        for rep in (1, 2):
            imports.append({
                "state": state,
                "rep": rep,
                "import_ok": True,
                "m_per_unit": 1,
                "tol_v_units": 0.002,
                "tol_f_units": 0.005,
                "failures": [],
                "nodes": copy.deepcopy(nodes),
            })
    return {"synthetic": synthetic, "failures": [], "imports": imports}


def _control_dump(lib):
    """Retained real dump when configured; otherwise the synthetic 14-row stand-in."""
    raw = os.environ.get(lib.NATIVE_DUMP_ENV)
    if raw and Path(raw).is_file():
        dump = json.loads(Path(raw).read_text(encoding="utf-8"))
        if dump.get("synthetic") is True:
            pytest.fail("synthetic dump cannot confirm native parity")
        return dump
    return _pinned_dump(lib, synthetic=True)


def _certify(lib, dump):
    if dump.get("synthetic") is True:
        return lib.evaluate(dump)
    return lib.confirm_native(dump)


def _reject(lib, dump):
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(lib.HarnessError) as caught:
            _certify(lib, dump)
    assert caught.value.status == "fail"
    assert caught.value.status not in ("pass", "not_run")
    return str(caught.value)


_INVENTORY_MUTATIONS = {
    "missing_state", "extra_state", "unknown_state",
    "missing_rep", "unknown_rep",
    "missing_node", "extra_node", "unknown_node",
}


def _both_reps(dump, state, mutate_item):
    for item in dump["imports"]:
        if item["state"] == state:
            mutate_item(item)


def _mutate_top_failures(dump):
    dump["failures"] = ["RuntimeError after final mutation"]


def _mutate_import_ok_false(dump):
    dump["imports"][0]["import_ok"] = False


def _mutate_import_ok_missing(dump):
    del dump["imports"][0]["import_ok"]


def _mutate_geometry_false(dump):
    dump["imports"][0]["nodes"][0]["geometry_unchanged"] = False


def _mutate_geometry_missing(dump):
    del dump["imports"][0]["nodes"][0]["geometry_unchanged"]


def _mutate_duplicate(dump):
    bad = copy.deepcopy(dump["imports"][0])
    bad["nodes"][0]["error"] = "checker failure"
    bad["failures"] = ["checker failure"]
    dump["imports"].insert(0, bad)


def _mutate_class_mesh(dump):
    for item in dump["imports"]:
        for node in item["nodes"]:
            node["class"] = "Editable_Mesh"


def _mutate_tol_1e9(dump):
    for item in dump["imports"]:
        item["tol_v_units"] = 1e-9
        item["tol_f_units"] = 1e-9


def _mutate_missing_state(dump):
    dump["imports"] = [item for item in dump["imports"] if item["state"] != "S00_source"]


def _mutate_extra_state(dump):
    extra = [copy.deepcopy(item) for item in dump["imports"] if item["state"] == "S00_source"]
    for item in extra:
        item["state"] = "S99_extra"
    dump["imports"].extend(extra)


def _mutate_unknown_state(dump):
    for item in dump["imports"]:
        if item["state"] == "S00_source":
            item["state"] = "S99_unknown"


def _mutate_missing_rep(dump):
    dump["imports"] = [
        item for item in dump["imports"]
        if not (item["state"] == "S00_source" and item["rep"] == 2)
    ]


def _mutate_unknown_rep(dump):
    for item in dump["imports"]:
        if item["state"] == "S00_source" and item["rep"] == 2:
            item["rep"] = 9


def _mutate_missing_node(dump):
    def drop(item):
        item["nodes"] = [node for node in item["nodes"] if node["name"] != "AC08_knob"]

    _both_reps(dump, "S00_source", drop)


def _mutate_extra_node(dump):
    extra = _separated_node("AC08_not_in_inventory", 1)

    def add(item):
        item["nodes"].append(copy.deepcopy(extra))

    _both_reps(dump, "S00_source", add)


def _mutate_unknown_node(dump):
    def rename(item):
        for node in item["nodes"]:
            if node["name"] == "AC08_knob":
                node["name"] = "AC08_ghost"

    _both_reps(dump, "S00_source", rename)


def _mutate_tol_nan(dump):
    dump["imports"][0]["tol_v_units"] = float("nan")


def _mutate_tol_inf(dump):
    dump["imports"][0]["tol_f_units"] = float("inf")


def _mutate_coord_nan(dump):
    def poison(item):
        for node in item["nodes"]:
            if node["name"] == "AC08_body":
                node["vertices"][0][2] = float("nan")

    _both_reps(dump, "S00_source", poison)


def _mutate_tol_v_zero(dump):
    dump["imports"][0]["tol_v_units"] = 0.0


def _mutate_tol_v_at_face_threshold(dump):
    dump["imports"][0]["tol_v_units"] = 0.005


def _mutate_tol_f_at_vertex_threshold(dump):
    dump["imports"][0]["tol_f_units"] = 0.002


def _mutate_units_mm(dump):
    dump["imports"][0]["m_per_unit"] = 0.001


def _mutate_units_name(dump):
    dump["imports"][0]["m_per_unit"] = "inches"


def _mutate_vertex_exactly_2mm(dump):
    """Geometry-valid threshold witness (#797): two appended vertices exactly tol_v_units apart.

    No face is touched, so every polygon of the synthetic fixture and of the retained real dump
    stays exactly as recorded (simple). Coordinates 0 and tol_v_units make the kernel's distance
    equal the vertex threshold bit for bit; the recorded native sets stay empty, so a correct
    harness sees a symmetric difference on AC08_body.
    """
    def add_pair(item):
        tol = item["tol_v_units"]
        for node in item["nodes"]:
            if node["name"] == "AC08_body":
                node["vertices"] += [[0.0, 0.0, 0.0], [tol, 0.0, 0.0]]
                node["num_verts"] = len(node["vertices"])

    _both_reps(dump, "S00_source", add_pair)


def _mutate_unsupported_self_intersecting(dump):
    """Bow-tie: swap the middle corners of AC08_body face 0 (a quad on both dumps)."""
    def twist(item):
        for node in item["nodes"]:
            if node["name"] == "AC08_body":
                face = node["faces"][0]
                assert len(face) == 4, face
                node["faces"][0] = [face[0], face[2], face[1], face[3]]

    _both_reps(dump, "S00_source", twist)


_MUTATIONS = {
    "top_failures": (_mutate_top_failures, "RuntimeError after final mutation"),
    "import_ok_false": (_mutate_import_ok_false, "import_ok"),
    "import_ok_missing": (_mutate_import_ok_missing, "import_ok"),
    "geometry_unchanged_false": (_mutate_geometry_false, "geometry_unchanged"),
    "geometry_unchanged_missing": (_mutate_geometry_missing, "geometry_unchanged"),
    "duplicate_state_rep": (_mutate_duplicate, "duplicate state/rep"),
    "class_editable_mesh": (_mutate_class_mesh, "Editable_Mesh"),
    "tolerances_1e-9": (_mutate_tol_1e9, "1e-09"),
    "missing_state": (_mutate_missing_state, "missing state S00_source"),
    "extra_state": (_mutate_extra_state, "extra state S99_extra"),
    "unknown_state": (_mutate_unknown_state, "unknown state S99_unknown"),
    "missing_rep": (_mutate_missing_rep, "missing rep 2"),
    "unknown_rep": (_mutate_unknown_rep, "unknown rep 9"),
    "missing_node": (_mutate_missing_node, "missing node AC08_knob"),
    "extra_node": (_mutate_extra_node, "extra node AC08_not_in_inventory"),
    "unknown_node": (_mutate_unknown_node, "unknown node AC08_ghost"),
    "tol_nan": (_mutate_tol_nan, "non-finite"),
    "tol_inf": (_mutate_tol_inf, "non-finite"),
    "coord_nan": (_mutate_coord_nan, "non-finite"),
    "tol_v_exactly_0": (_mutate_tol_v_zero, "tol_v_units"),
    "tol_v_exactly_5mm": (_mutate_tol_v_at_face_threshold, "tol_v_units"),
    "tol_f_exactly_2mm": (_mutate_tol_f_at_vertex_threshold, "tol_f_units"),
    "units_millimetre": (_mutate_units_mm, "metre"),
    "units_unsupported": (_mutate_units_name, "unsupported"),
    "vertex_exactly_2mm": (_mutate_vertex_exactly_2mm, "AC08_body: symmetric difference"),
    "unsupported_self_intersecting": (_mutate_unsupported_self_intersecting, "self-intersecting"),
}


@pytest.mark.parametrize("mutation_id", list(_MUTATIONS), ids=list(_MUTATIONS))
def test_native_mutation_is_not_certified(lib, mutation_id):
    """Each false-confirmation mutation is named and rejected, never a pass."""
    mutate, cause = _MUTATIONS[mutation_id]
    dump = copy.deepcopy(_control_dump(lib))
    mutate(dump)
    if mutation_id in _INVENTORY_MUTATIONS and dump.get("synthetic") is True:
        dump["synthetic"] = False
    text = _reject(lib, dump)
    assert cause in text
    assert "pass" not in text


def test_vertex_threshold_witness_is_geometry_valid(lib):
    """#797: the 2 mm witness keeps every polygon simple and sits exactly on the vertex threshold."""
    import numpy as np

    from dt_ai.ops import inv_xview

    dump = copy.deepcopy(_control_dump(lib))
    before = copy.deepcopy(dump)
    _mutate_vertex_exactly_2mm(dump)
    touched = 0
    for item, old in zip(dump["imports"], before["imports"]):
        for node, prev in zip(item["nodes"], old["nodes"]):
            assert node["faces"] == prev["faces"]
            if node["name"] != "AC08_body" or item["state"] != "S00_source":
                assert node == prev
                continue
            touched += 1
            m = float(item["m_per_unit"])
            v = np.asarray(node["vertices"], dtype=float) * m
            n = len(prev["vertices"])
            a, b, d = inv_xview.vertex_pairs(v, float(item["tol_v_units"]) * m)
            hit = [(x, y, z) for x, y, z in zip(a.tolist(), b.tolist(), d.tolist()) if (x, y) == (n, n + 1)]
            assert hit and hit[0][2] == float(item["tol_v_units"]) * m
            mesh, _, _ = lib.parity_module()._node(node)
            for k, face in enumerate(mesh.faces):
                assert inv_xview._polygon_triangles(k, face, mesh.vertices * m)
    assert touched == 2


def test_unsupported_polygon_is_named_harness_error_not_value_error(lib):
    dump = copy.deepcopy(_control_dump(lib))
    _mutate_unsupported_self_intersecting(dump)
    dump["synthetic"] = False
    with pytest.raises(lib.HarnessError, match="AC08_body: unsupported geometry: .*self-intersecting"):
        lib.confirm_native(dump)


def test_unmutated_control_yields_fourteen_rows(lib):
    dump = _control_dump(lib)
    report = _certify(lib, dump)
    assert report["status"] == "pass"
    assert report["delivery_passed"] is False
    assert report["mesh_import_rows"] == 14
    assert all(row["equal"] for row in report["rows"])
    if dump.get("synthetic") is True:
        certified = copy.deepcopy(dump)
        certified["synthetic"] = False
        native = lib.confirm_native(certified)
        assert native["status"] == "pass"
        assert native["mesh_import_rows"] == 14
        assert native["delivery_passed"] is False


def test_live_marker_without_measured_dump_never_passes(lib, monkeypatch):
    """Fixtures configured, native_max selected, ping accepted, dump absent."""
    monkeypatch.delenv("AC08_XVIEW_NATIVE_DUMP", raising=False)
    monkeypatch.setattr(lib, "fixture_skip_reason", lambda env=None: None)
    monkeypatch.setattr(lib, "native_skip_reason", lambda *args, **kwargs: None)

    class _Request:
        class config:
            @staticmethod
            def getoption(name):
                return "native_max"

    with pytest.raises((pytest.skip.Exception, pytest.fail.Exception)) as caught:
        test_real_native_parity(lib, _Request())
    assert "AC08_XVIEW_NATIVE_DUMP" in str(caught.value)


def _probe_reject_all(lib, mutations):
    base = _pinned_dump(lib, synthetic=True)
    clean = _certify(lib, copy.deepcopy(base))
    assert clean["status"] == "pass"
    assert clean["mesh_import_rows"] == 14
    rejected = 0
    for change in mutations:
        dump = copy.deepcopy(base)
        change(dump)
        _reject(lib, dump)
        rejected += 1
    assert rejected == len(mutations)
    return rejected


def test_probe_never_certify_failed(lib):
    """Single-field execution failures, including a checker failure, never pass."""
    mutations = [
        _mutate_top_failures,
        _mutate_import_ok_false,
        _mutate_import_ok_missing,
        lambda dump: dump["imports"][0].__setitem__("import_ok", 0),
        lambda dump: dump["imports"][0].__setitem__("import_ok", None),
        _mutate_geometry_false,
        _mutate_geometry_missing,
        lambda dump: dump["imports"][0]["nodes"][0].__setitem__("geometry_unchanged", None),
        lambda dump: dump["imports"][0]["nodes"][0].__setitem__("error", "checker failure"),
        lambda dump: dump["imports"][0].__setitem__("failures", ["RuntimeError after final mutation"]),
    ]
    assert _probe_reject_all(lib, mutations) == 10


def test_probe_never_certify_duplicate(lib):
    """Duplicate (state, rep) identities are rejected before a dict overwrite."""
    def with_failure(item):
        item["nodes"][0]["error"] = "checker failure"
        item["failures"] = ["checker failure"]

    def insert_front(dump, poison=False):
        bad = copy.deepcopy(dump["imports"][0])
        if poison:
            with_failure(bad)
        dump["imports"].insert(0, bad)

    def append(dump, poison=False):
        bad = copy.deepcopy(dump["imports"][0])
        if poison:
            with_failure(bad)
        dump["imports"].append(bad)

    mutations = [
        lambda dump: insert_front(dump, poison=True),
        lambda dump: append(dump, poison=True),
        lambda dump: insert_front(dump, poison=False),
        lambda dump: append(dump, poison=False),
        lambda dump: insert_front(dump, poison=True) or dump["imports"][0].__setitem__("import_ok", False),
    ]
    assert _probe_reject_all(lib, mutations) == 5


def test_probe_never_certify_non_poly(lib):
    """Only Editable_Poly is accepted; every other class is a named rejection."""
    classes = ["Editable_Mesh", "Editable_mesh", "PolyMesh", "", None, "Editable_Poly ", "Editable Poly"]

    def set_class(value):
        def change(dump):
            dump["imports"][0]["nodes"][0]["class"] = value
        return change

    mutations = [set_class(value) for value in classes]
    mutations.append(lambda dump: dump["imports"][0]["nodes"][0].__delitem__("class"))
    assert _probe_reject_all(lib, mutations) == 8


def test_probe_never_certify_wrong_tolerance(lib):
    """Frozen metres / 2 mm / 5 mm only. Other units, NaN/inf and exact boundaries fail."""
    def set_field(key, value, every=False):
        def change(dump):
            items = dump["imports"] if every else dump["imports"][:1]
            for item in items:
                item[key] = value
        return change

    mutations = [
        set_field("tol_v_units", 1e-9),
        set_field("tol_f_units", 1e-9),
        set_field("tol_v_units", 1e-9, every=True),
        set_field("tol_f_units", 1e-9, every=True),
        set_field("m_per_unit", 0.001),
        set_field("m_per_unit", 0.0254),
        set_field("m_per_unit", "inches"),
        set_field("m_per_unit", 0),
        set_field("m_per_unit", 0.0),
        set_field("m_per_unit", float("nan")),
        set_field("m_per_unit", float("inf")),
        set_field("m_per_unit", True),
        set_field("tol_v_units", 0),
        set_field("tol_v_units", 0.0),
        set_field("tol_v_units", float("nan")),
        set_field("tol_v_units", float("inf")),
        set_field("tol_v_units", True),
        set_field("tol_v_units", 0.005),
        set_field("tol_f_units", 0),
        set_field("tol_f_units", 0.0),
        set_field("tol_f_units", float("nan")),
        set_field("tol_f_units", float("inf")),
        set_field("tol_f_units", 0.002),
        _mutate_vertex_exactly_2mm,
    ]
    assert _probe_reject_all(lib, mutations) == 24
